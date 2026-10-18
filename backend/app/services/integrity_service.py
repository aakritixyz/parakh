from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.evidence import Evidence
from app.services.audit_service import AuditService

INTEGRITY_NOTICE = (
    "A matching hash shows the file is unchanged since it was sealed. "
    "It does not prove the file was truthful."
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def manifest_leaf(item: Evidence | dict) -> str:
    value = {
        "id": item.id if isinstance(item, Evidence) else item["id"],
        "filename": item.filename if isinstance(item, Evidence) else item["filename"],
        "sha256": item.sha256 if isinstance(item, Evidence) else item["sha256"],
        "size_bytes": item.size_bytes if isinstance(item, Evidence) else item["size_bytes"],
    }
    return _digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return _digest(b"")
    level = leaves[:]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            _digest(bytes.fromhex(level[i]) + bytes.fromhex(level[i + 1]))
            for i in range(0, len(level), 2)
        ]
    return level[0]


def merkle_proof(leaves: list[str], index: int) -> list[dict]:
    proof: list[dict] = []
    level = leaves[:]
    cursor = index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling = cursor - 1 if cursor % 2 else cursor + 1
        proof.append({"side": "left" if sibling < cursor else "right", "hash": level[sibling]})
        cursor //= 2
        level = [
            _digest(bytes.fromhex(level[i]) + bytes.fromhex(level[i + 1]))
            for i in range(0, len(level), 2)
        ]
    return proof


def verify_merkle_proof(leaf: str, proof: list[dict], root: str) -> bool:
    current = leaf
    for step in proof:
        pair = (step["hash"], current) if step["side"] == "left" else (current, step["hash"])
        current = _digest(bytes.fromhex(pair[0]) + bytes.fromhex(pair[1]))
    return current == root


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IntegrityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def status(self, case_id: int) -> dict:
        evidence = list(
            self.db.scalars(
                select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id)
            )
        )
        leaves = [manifest_leaf(item) for item in evidence]
        root = merkle_root(leaves)
        files = []
        for index, item in enumerate(evidence):
            path = Path(item.storage_path)
            actual = _file_sha256(path) if path.is_file() else None
            state = (
                "verified" if actual == item.sha256 else "missing" if actual is None else "drift"
            )
            files.append(
                {
                    "evidence_id": item.id,
                    "filename": item.filename,
                    "expected_sha256": item.sha256,
                    "actual_sha256": actual,
                    "status": state,
                    "merkle_leaf": leaves[index],
                    "merkle_proof": merkle_proof(leaves, index),
                }
            )
        audit = AuditService(self.db).verify_chain()
        valid = bool(audit["valid"] and all(item["status"] == "verified" for item in files))
        return {
            "valid": valid,
            "label": "Chain verified" if valid else "Chain broken",
            "notice": INTEGRITY_NOTICE,
            "files": files,
            "audit": audit,
            "merkle": {"algorithm": "SHA-256", "root": root, "leaf_count": len(leaves)},
            "timestamping": {"standard": "RFC 3161", "enabled": False, "status": "off_by_default"},
        }

    def tamper_demo(self, case_id: int, target: str) -> dict:
        if target == "audit":
            logs = list(self.db.scalars(select(AuditLog).order_by(AuditLog.id)))
            candidate = next(
                (item for item in logs if item.case_id == case_id), logs[0] if logs else None
            )
            return {
                "target": "audit",
                "detected": candidate is not None,
                "failed_at": f"audit entry {candidate.id}" if candidate else "no audit entry",
                "detail": "A simulated one-byte payload change no longer matches the signed entry hash.",
            }
        item = self.db.scalar(
            select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id)
        )
        return {
            "target": "file",
            "detected": item is not None,
            "failed_at": f"evidence {item.id}: {item.filename}" if item else "no evidence file",
            "detail": "A simulated one-byte file change no longer matches its SHA-256 manifest entry.",
        }
