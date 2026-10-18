import hashlib
import json
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.models.investigation import Extraction, Job
from app.parsers.registry import ParserRegistry
from app.services.audit_service import AuditService
from app.storage.content_addressed import ContentAddressedStorage


class EvidenceService:
    def __init__(self, db: Session, storage: ContentAddressedStorage | None = None) -> None:
        self.db = db
        self.storage = storage or ContentAddressedStorage()

    async def ingest(
        self, case_id: int, upload: UploadFile, actor: str, idempotency_key: str | None
    ) -> Evidence:
        if idempotency_key:
            existing = self.db.scalar(
                select(Evidence).where(
                    Evidence.case_id == case_id, Evidence.idempotency_key == idempotency_key
                )
            )
            if existing:
                return existing
        blob = self.storage.put_fileobj(upload.file)
        parser = ParserRegistry.detect(upload.filename or "", upload.content_type or "", blob.path)
        evidence = Evidence(
            case_id=case_id,
            filename=upload.filename or "upload.bin",
            content_type=upload.content_type or "application/octet-stream",
            mime=upload.content_type or "application/octet-stream",
            source_type=parser.source_type,
            sha256=blob.sha256,
            md5=blob.md5,
            size_bytes=blob.size_bytes,
            storage_path=str(blob.path),
            storage_key=blob.sha256,
            acquired_by=actor,
            idempotency_key=idempotency_key,
            metadata_json=parser.metadata(blob.path),
        )
        self.db.add(evidence)
        self.db.flush()
        job = Job(
            case_id=case_id,
            type="ingest_extraction",
            status="running",
            progress=35,
            logs=[
                f"Stored evidence {evidence.filename}",
                f"Detected parser {parser.__class__.__name__}",
            ],
        )
        self.db.add(job)
        self.db.flush()
        extraction = Extraction(
            case_id=case_id,
            evidence_id=evidence.id,
            extraction_type=parser.source_type,
            source_name=upload.filename or "upload.bin",
            parse_status="running",
            parser_name=parser.__class__.__name__,
            parser_version=getattr(parser, "version", "1"),
        )
        self.db.add(extraction)
        self.db.flush()
        for parsed in parser.parse(blob.path, case_id=case_id, evidence_id=evidence.id):
            event_data = parsed.model_dump()
            event_data["extraction_id"] = extraction.id
            event_data["source_app"] = parser.source_type
            event_data["event_type"] = _event_type_for_action(str(event_data.get("action", "")))
            event_data["parser_name"] = parser.__class__.__name__
            event_data["parser_version"] = getattr(parser, "version", "1")
            event_data["dedupe_hash"] = _dedupe_hash(event_data)
            self.db.add(Event(**event_data))
        extraction.warnings = list(getattr(parser, "warnings", []))
        extraction.parse_status = "needs_review" if extraction.warnings else "complete"
        extraction.parser_name = parser.__class__.__name__
        extraction.parser_version = getattr(parser, "version", "1")
        if extraction.warnings:
            evidence.metadata_json = {**evidence.metadata_json, "warnings": extraction.warnings}
        job.status = "completed"
        job.progress = 100
        job.logs = [*job.logs, "Extraction completed", *extraction.warnings]
        AuditService(self.db).log(
            action="evidence.uploaded",
            actor=actor,
            case_id=case_id,
            target_type="evidence",
            target_id=str(evidence.id),
            payload={
                "sha256": blob.sha256,
                "filename": evidence.filename,
                "parser": parser.source_type,
                "extraction_id": extraction.id,
                "job_id": job.id,
            },
        )
        return evidence

    def reparse(self, evidence_id: int, actor: str = "system") -> dict:
        evidence = self.db.get(Evidence, evidence_id)
        if not evidence:
            raise ValueError("Evidence not found")
        stored_path = Path(evidence.storage_path)
        parser = ParserRegistry.detect(evidence.filename, evidence.content_type, stored_path)
        extraction = self.db.scalar(
            select(Extraction)
            .where(Extraction.evidence_id == evidence.id)
            .order_by(Extraction.id.desc())
        )
        if not extraction:
            extraction = Extraction(
                case_id=evidence.case_id,
                evidence_id=evidence.id,
                extraction_type=parser.source_type,
                source_name=evidence.filename,
                parser_name=parser.__class__.__name__,
                parser_version=getattr(parser, "version", "1"),
            )
            self.db.add(extraction)
            self.db.flush()
        extraction.parse_status = "running"
        deleted = (
            self.db.query(Event)
            .filter(Event.extraction_id == extraction.id)
            .delete(synchronize_session=False)
        )
        self.db.expire_all()
        inserted = 0
        for parsed in parser.parse(stored_path, case_id=evidence.case_id, evidence_id=evidence.id):
            event_data = parsed.model_dump()
            event_data["extraction_id"] = extraction.id
            event_data["source_app"] = parser.source_type
            event_data["event_type"] = _event_type_for_action(str(event_data.get("action", "")))
            event_data["parser_name"] = parser.__class__.__name__
            event_data["parser_version"] = getattr(parser, "version", "1")
            event_data["dedupe_hash"] = _dedupe_hash(event_data)
            self.db.add(Event(**event_data))
            inserted += 1
        extraction.warnings = list(getattr(parser, "warnings", []))
        extraction.parse_status = "needs_review" if extraction.warnings else "complete"
        extraction.parser_name = parser.__class__.__name__
        extraction.parser_version = getattr(parser, "version", "1")
        if extraction.warnings:
            evidence.metadata_json = {**evidence.metadata_json, "warnings": extraction.warnings}
        self.db.flush()
        AuditService(self.db).log(
            action="evidence.reparsed",
            actor=actor,
            case_id=evidence.case_id,
            target_type="evidence",
            target_id=str(evidence.id),
            payload={
                "extraction_id": extraction.id,
                "deleted_events": deleted,
                "inserted_events": inserted,
            },
        )
        return {
            "evidence_id": evidence.id,
            "extraction_id": extraction.id,
            "deleted": deleted,
            "inserted": inserted,
        }

    def verify_integrity(self, evidence: Evidence) -> dict:
        ok = self.storage.verify(evidence.storage_path, evidence.sha256)
        return {"evidence_id": evidence.id, "sha256": evidence.sha256, "valid": ok}


def _event_type_for_action(action: str) -> str:
    action_lower = action.lower()
    if "message" in action_lower:
        return "message"
    if "call" in action_lower:
        return "call"
    if "email" in action_lower:
        return "email"
    if "transaction" in action_lower or "debit" in action_lower or "credit" in action_lower:
        return "transaction"
    if "location" in action_lower or "gps" in action_lower:
        return "location"
    if "visit" in action_lower or "browser" in action_lower:
        return "web_visit"
    if "media" in action_lower or "image" in action_lower:
        return "media"
    return "other"


def _dedupe_hash(event_data: dict) -> str:
    stable = {
        "evidence_id": event_data.get("evidence_id"),
        "source_type": event_data.get("source_type"),
        "timestamp_utc": str(event_data.get("timestamp_utc") or ""),
        "action": event_data.get("action") or "",
        "content": event_data.get("content") or "",
        "raw_ref": event_data.get("raw_ref") or "",
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()
