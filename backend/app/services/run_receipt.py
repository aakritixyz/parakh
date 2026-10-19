"""Store reproducibility metadata without changing existing analysis response contracts."""
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.models.ml import ModelRecord
from app.services.audit_service import AuditService


def record_run(db: Session, case_id: int, actor: str, name: str, inputs: dict, result: dict) -> dict:
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()

    settings = []

    def collect(value, path="result"):
        if isinstance(value, dict):
            metadata = {key: item for key, item in value.items() if key in {
                "seed", "samples", "time_limit_seconds", "complete", "incomplete", "fallback", "assumptions", "method", "engine", "status", "fdr_alpha", "version"
            } and not isinstance(item, dict | list)}
            if metadata:
                settings.append({"path": path, **metadata})
            for key, item in value.items():
                collect(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                collect(item, f"{path}[{index}]")

    collect(result)
    dependencies = {}
    for package in ("numpy", "scikit-learn", "ortools", "networkx"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "unavailable; use declared fallback"
    sources = [(item.id, item.sha256) for item in db.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id))]
    events = [(event.id, event.content, event.timestamp_utc, event.raw_ref) for event in db.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.id))]
    code = Path(__file__).with_name(f"{name}_service.py")
    AuditService(db).log(action="analysis.run_recorded", actor=actor, case_id=case_id, payload={
        "analysis": name, "inputs": inputs, "settings": settings,
        "version": "step18-1", "implementation_sha256": hashlib.sha256(code.read_bytes()).hexdigest(),
        "evidence_snapshot_sha256": digest(sources), "events_snapshot_sha256": digest(events),
        "result_sha256": digest(result), "dependencies": dependencies,
        "models": [{"name": m.name, "version": m.version, "artifact_sha256": m.artifact_sha256} for m in db.scalars(select(ModelRecord).order_by(ModelRecord.id))],
        "limits": "Same sealed inputs, settings, model artifacts and implementation are required. Time-limited runs may return incomplete output; no completion claim is inferred.",
    })
    db.commit()
    return result
