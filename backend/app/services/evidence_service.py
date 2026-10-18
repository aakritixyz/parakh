import hashlib
import json
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.evidence import Event, Evidence
from app.models.investigation import Extraction, Job
from app.parsers.registry import ParserRegistry
from app.services.audit_service import AuditService
from app.services.file_types import extension_mismatch, sniff_type
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
        evidence, job, duplicate = self.seal(
            case_id=case_id,
            fileobj=upload.file,
            filename=upload.filename or "upload.bin",
            content_type=upload.content_type or "application/octet-stream",
            actor=actor,
            idempotency_key=idempotency_key,
        )
        if not duplicate and job:
            self.reparse(evidence.id, actor)
            job.status = "completed"
            job.stage = "Done"
            job.progress = 100
            job.logs = [*job.logs, "Extraction completed"]
        return evidence

    def seal(
        self,
        *,
        case_id: int,
        fileobj,
        filename: str,
        content_type: str,
        actor: str,
        idempotency_key: str | None,
        source_type: str | None = None,
        owner_id: int | None = None,
        device_id: int | None = None,
        acquisition_note: str = "",
        acquired_by: str | None = None,
        received_at=None,
        parent_evidence_id: int | None = None,
        archive_path: str | None = None,
    ) -> tuple[Evidence, Job | None, bool]:
        if idempotency_key:
            existing = self.db.scalar(select(Evidence).where(Evidence.case_id == case_id, Evidence.idempotency_key == idempotency_key))
            if existing:
                prior_job = self.db.scalar(select(Job).where(Job.evidence_id == existing.id).order_by(Job.id.desc()))
                return existing, prior_job, True
        blob = self.storage.put_fileobj(fileobj, get_settings().max_upload_bytes)
        existing = self.db.scalar(select(Evidence).where(Evidence.case_id == case_id, Evidence.sha256 == blob.sha256))
        if existing:
            prior_job = self.db.scalar(select(Job).where(Job.evidence_id == existing.id).order_by(Job.id.desc()))
            return existing, prior_job, True
        detected = sniff_type(blob.path)
        mismatch = extension_mismatch(filename, detected)
        parser = ParserRegistry.detect(filename, detected, blob.path)
        selected_type = source_type or parser.source_type
        evidence = Evidence(
            case_id=case_id,
            filename=filename,
            content_type=content_type,
            mime=detected,
            source_type=selected_type,
            sha256=blob.sha256,
            md5=blob.md5,
            size_bytes=blob.size_bytes,
            storage_path=str(blob.path),
            storage_key=blob.sha256,
            acquired_by=acquired_by or actor,
            acquisition_note=acquisition_note,
            received_at=received_at,
            owner_id=owner_id,
            device_id=device_id,
            parent_evidence_id=parent_evidence_id,
            archive_path=archive_path,
            idempotency_key=idempotency_key,
            metadata_json={
                **parser.metadata(blob.path),
                "detected_mime": detected,
                "declared_mime": content_type,
                "magic_byte_warning": mismatch,
            },
        )
        self.db.add(evidence)
        self.db.flush()
        job = Job(
            case_id=case_id,
            evidence_id=evidence.id,
            type="ingest_extraction",
            status="queued",
            stage="Stored",
            progress=35,
            logs=[
                f"Hashed and sealed {evidence.filename}",
                f"Detected parser {parser.__class__.__name__}",
            ],
        )
        self.db.add(job)
        self.db.flush()
        AuditService(self.db).log(
            action="evidence.sealed",
            actor=actor,
            case_id=case_id,
            target_type="evidence",
            target_id=str(evidence.id),
            payload={
                "sha256": blob.sha256,
                "filename": evidence.filename,
                "md5": blob.md5,
                "size_bytes": blob.size_bytes,
                "detected_mime": detected,
                "source_type": selected_type,
                "owner_id": owner_id,
                "device_id": device_id,
                "parent_evidence_id": parent_evidence_id,
                "archive_path": archive_path,
                "job_id": job.id,
            },
        )
        return evidence, job, False

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
