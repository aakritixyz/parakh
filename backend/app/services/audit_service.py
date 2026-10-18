import hashlib
import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.session import AuditHead


def _entry_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


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
        self.db.execute(update(AuditHead).where(AuditHead.id == 1).values(sequence=AuditHead.sequence + 1))
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
        return entry

    def verify_chain(self) -> dict:
        logs = list(self.db.scalars(select(AuditLog).order_by(AuditLog.id)))
        previous_hash = "GENESIS"
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
            previous_hash = entry.entry_hash
        return {"valid": True, "entries": len(logs), "tip_hash": previous_hash}
