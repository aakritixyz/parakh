from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.evidence import Event, Evidence
from app.models.investigation import Extraction, Job
from app.parsers.registry import ParserRegistry
from app.services.audit_service import AuditService
from app.services.evidence_service import _dedupe_hash, _event_type_for_action


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
        parser = ParserRegistry.detect(evidence.filename, evidence.content_type, stored_path)
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
        parsed_items = list(
            parser.parse(stored_path, case_id=evidence.case_id, evidence_id=evidence.id)
        )
        db.refresh(job)
        if job.cancel_requested:
            _cancel(job)
            extraction.parse_status = "cancelled"
            db.commit()
            return
        job.stage = "Indexing"
        job.progress = 85
        db.commit()
        for parsed in parsed_items:
            event_data = parsed.model_dump()
            event_data.update(
                extraction_id=extraction.id,
                owner_id=evidence.owner_id,
                source_app=evidence.source_type,
                event_type=_event_type_for_action(str(event_data.get("action", ""))),
                parser_name=parser.__class__.__name__,
                parser_version=getattr(parser, "version", "1"),
            )
            event_data["dedupe_hash"] = _dedupe_hash(event_data)
            db.add(Event(**event_data))
        warnings = list(getattr(parser, "warnings", []))
        extraction.warnings = warnings
        extraction.parse_status = "needs_review" if warnings else "complete"
        job.stage = "Done"
        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        job.logs = [*job.logs, f"Parsed {len(parsed_items)} records", *warnings]
        AuditService(db).log(
            action="evidence.indexed",
            actor="background-worker",
            case_id=evidence.case_id,
            target_type="evidence",
            target_id=str(evidence.id),
            payload={"job_id": job.id, "events": len(parsed_items)},
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
