from datetime import UTC, datetime
from itertools import islice
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.evidence import Event, Evidence
from app.models.investigation import Extraction, Job
from app.parsers.registry import ParserRegistry
from app.services.audit_service import AuditService
from app.services.document_extraction_service import DocumentExtractionService, index_ocr_event
from app.services.evidence_service import _event_from_parsed, _parse_status


def run_intake_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or not job.evidence_id:
            return
        evidence = db.get(Evidence, job.evidence_id)
        if not evidence:
            return
        if job.cancel_requested:
            _cancel(job)
            db.commit()
            return
        job.status = "running"
        job.stage = "Parsing"
        job.progress = 55
        job.started_at = datetime.now(UTC)
        db.commit()

        stored_path = Path(evidence.storage_path)
        parser, detection_confidence, detection_reasons = ParserRegistry.detect_with_confidence(
            evidence.filename,
            evidence.mime,
            stored_path,
            options=evidence.metadata_json.get("parser_options", {}),
        )
        evidence.metadata_json = {
            **evidence.metadata_json,
            "format_detection": {
                "confidence": detection_confidence,
                "reasons": detection_reasons,
                "parser": parser.name,
                "version": parser.version,
            },
        }
        extraction = db.scalar(
            select(Extraction)
            .where(Extraction.evidence_id == evidence.id)
            .order_by(Extraction.id.desc())
        )
        if not extraction:
            extraction = Extraction(
                case_id=evidence.case_id,
                evidence_id=evidence.id,
                device_id=evidence.device_id,
                owner_id=evidence.owner_id,
                extraction_type=evidence.source_type,
                source_name=evidence.filename,
            )
            db.add(extraction)
            db.flush()
        extraction.parse_status = "running"
        extraction.parser_name = parser.__class__.__name__
        extraction.parser_version = getattr(parser, "version", "1")
        db.query(Event).filter(Event.extraction_id == extraction.id).delete(
            synchronize_session=False
        )
        job.stage = "Indexing"
        job.progress = 85
        db.commit()
        inserted = 0
        stream = parser.parse(stored_path, case_id=evidence.case_id, evidence_id=evidence.id)
        while batch := list(islice(stream, 5000)):
            db.add_all(
                [_event_from_parsed(item, evidence, extraction.id, parser) for item in batch]
            )
            db.flush()
            inserted += len(batch)
            db.refresh(job)
            if job.cancel_requested:
                _cancel(job)
                extraction.parse_status = "cancelled"
                db.commit()
                return
        document, document_warnings = DocumentExtractionService(db).extract(evidence)
        inserted += index_ocr_event(db, evidence, extraction.id, document)
        parser.warnings.extend(document_warnings)
        warnings = list(getattr(parser, "warnings", []))
        evidence.metadata_json = {**evidence.metadata_json, "warnings": warnings}
        extraction.warnings = warnings
        extraction.parse_status = _parse_status(warnings)
        job.stage = "Done"
        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        warning_logs = [
            item if isinstance(item, str) else item.get("message", str(item)) for item in warnings
        ]
        job.logs = [*job.logs, f"Parsed {inserted} records", *warning_logs]
        AuditService(db).log(
            action="evidence.indexed",
            actor="background-worker",
            case_id=evidence.case_id,
            target_type="evidence",
            target_id=str(evidence.id),
            payload={"job_id": job.id, "events": inserted},
        )
        db.commit()
    except Exception as exc:  # pragma: no cover - exercised through API failure tests
        db.rollback()
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.stage = "Failed"
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def _cancel(job: Job) -> None:
    job.status = "cancelled"
    job.stage = "Cancelled"
    job.finished_at = datetime.now(UTC)
    job.logs = [*job.logs, "Cancelled by investigator"]
