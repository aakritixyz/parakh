import hashlib
import json
import os
from base64 import b64decode, b64encode
from collections import defaultdict
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit import AuditLog
from app.models.investigation import AuditCheckpoint
from app.models.session import AuditHead


def _entry_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _signing_key() -> tuple[Ed25519PrivateKey, dict]:
    path = Path(get_settings().audit_signing_key_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError("Audit signing key is not Ed25519")
    else:
        key = Ed25519PrivateKey.generate()
        path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        os.chmod(path, 0o600)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return key, {
        "algorithm": "Ed25519",
        "key_id": hashlib.sha256(public).hexdigest()[:16],
        "public_key": b64encode(public).decode(),
    }


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        action: str,
        actor: str = "system",
        case_id: int | None = None,
        target_type: str = "",
        target_id: str = "",
        payload: dict | None = None,
    ) -> AuditLog:
        # Serialize appends across workers (including SQLite) before reading the tip.
        if not self.db.get(AuditHead, 1):
            self.db.add(AuditHead(id=1, sequence=0))
            self.db.flush()
        self.db.execute(
            update(AuditHead).where(AuditHead.id == 1).values(sequence=AuditHead.sequence + 1)
        )
        previous = self.db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
        previous_hash = previous.entry_hash if previous else "GENESIS"
        base = {
            "case_id": case_id,
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload or {},
            "previous_hash": previous_hash,
        }
        entry = AuditLog(**base, entry_hash=_entry_hash(base))
        self.db.add(entry)
        self.db.flush()
        key, metadata = _signing_key()
        signed = {
            **metadata,
            "kind": "entry_signature",
            "signature": b64encode(key.sign(entry.entry_hash.encode())).decode(),
        }
        self.db.add(
            AuditCheckpoint(
                audit_log_id=entry.id,
                tip_hash=entry.entry_hash,
                signature=json.dumps(signed, sort_keys=True),
            )
        )
        if entry.id % 25 == 0:
            periodic = {**signed, "kind": "periodic_checkpoint"}
            self.db.add(
                AuditCheckpoint(
                    audit_log_id=entry.id,
                    tip_hash=entry.entry_hash,
                    signature=json.dumps(periodic, sort_keys=True),
                )
            )
        return entry

    def verify_chain(self) -> dict:
        logs = list(self.db.scalars(select(AuditLog).order_by(AuditLog.id)))
        checkpoints: defaultdict[int, list[AuditCheckpoint]] = defaultdict(list)
        for checkpoint in self.db.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id)):
            checkpoints[checkpoint.audit_log_id].append(checkpoint)
        previous_hash = "GENESIS"
        signed_entries = 0
        for entry in logs:
            base = {
                "case_id": entry.case_id,
                "actor": entry.actor,
                "action": entry.action,
                "target_type": entry.target_type,
                "target_id": entry.target_id,
                "payload": entry.payload,
                "previous_hash": entry.previous_hash,
            }
            expected = _entry_hash(base)
            if entry.previous_hash != previous_hash or entry.entry_hash != expected:
                return {
                    "valid": False,
                    "failed_at": entry.id,
                    "expected_previous_hash": previous_hash,
                    "actual_previous_hash": entry.previous_hash,
                }
            entry_signatures = []
            for checkpoint in checkpoints.get(entry.id, []):
                if not checkpoint.signature:
                    continue
                try:
                    signed = json.loads(checkpoint.signature)
                    if signed.get("kind") != "entry_signature":
                        continue
                    Ed25519PublicKey.from_public_bytes(b64decode(signed["public_key"])).verify(
                        b64decode(signed["signature"]), entry.entry_hash.encode()
                    )
                    entry_signatures.append(signed)
                except (ValueError, KeyError, json.JSONDecodeError, InvalidSignature):
                    return {"valid": False, "signature_failed_at": entry.id}
            if entry_signatures:
                signed_entries += 1
            previous_hash = entry.entry_hash
        return {
            "valid": True,
            "entries": len(logs),
            "signed_entries": signed_entries,
            "unsigned_legacy_entries": len(logs) - signed_entries,
            "tip_hash": previous_hash,
        }
