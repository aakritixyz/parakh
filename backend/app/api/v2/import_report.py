from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.evidence import DocumentExtraction, Event, Evidence
from app.models.investigation import Extraction, Job
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.intake_worker import run_intake_job

router = APIRouter(tags=["v2 import report"])


class ReparseDecision(BaseModel):
    date_order: str


def _write_access(db: Session, user: User, case_id: int) -> None:
    require_case_access(db, user, case_id, write=True)


@router.get("/cases/{case_id}/import-report")
def import_report(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    evidence_items = list(
        db.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id))
    )
    counts: dict[int, int] = {
        evidence_id: event_count
        for evidence_id, event_count in db.execute(
            select(Event.evidence_id, func.count(Event.id))
            .where(Event.case_id == case_id)
            .group_by(Event.evidence_id)
        )
    }
    files: list[dict] = []
    decisions: list[dict] = []
    for evidence in evidence_items:
        extraction = db.scalar(
            select(Extraction)
            .where(Extraction.evidence_id == evidence.id)
            .order_by(Extraction.id.desc())
        )
        warnings = (extraction.warnings if extraction else []) or evidence.metadata_json.get(
            "warnings", []
        )
        for warning in warnings:
            warning_data = (
                warning if isinstance(warning, dict) else {"type": warning, "message": warning}
            )
            if warning_data.get("type") in {
                "ambiguous_date",
                "unparsed_line",
                "clock_offset_hint",
                "masked_aadhaar",
                "ocr_required",
                "ocr_engine_unavailable",
            }:
                decisions.append(
                    {
                        **warning_data,
                        "evidence_id": evidence.id,
                        "filename": evidence.filename,
                    }
                )
        document = db.scalar(
            select(DocumentExtraction).where(DocumentExtraction.evidence_id == evidence.id)
        )
        files.append(
            {
                "evidence_id": evidence.id,
                "filename": evidence.filename,
                "event_count": counts.get(evidence.id, 0),
                "parser_name": extraction.parser_name if extraction else None,
                "parser_version": extraction.parser_version if extraction else None,
                "parse_status": extraction.parse_status if extraction else "queued",
                "format_confidence": evidence.metadata_json.get("format_detection", {}).get(
                    "confidence"
                ),
                "warnings": warnings,
                "document_extraction": {
                    "engine": document.engine,
                    "engine_version": document.engine_version,
                    "languages": document.languages,
                    "fields": document.fields,
                    "boxes": document.boxes,
                }
                if document
                else None,
            }
        )
    return {
        "case_id": case_id,
        "files_imported": len(evidence_items),
        "total_events": sum(counts.values()),
        "files": files,
        "decisions": decisions,
        "status": "needs_review" if decisions else "ready",
    }


@router.post("/cases/{case_id}/import-report/confirm")
def confirm_import_report(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _write_access(db, user, case_id)
    AuditService(db).log(
        action="evidence.import_report_confirmed",
        actor=user.username,
        case_id=case_id,
        target_type="case",
        target_id=str(case_id),
    )
    db.commit()
    return {"case_id": case_id, "confirmed": True}


@router.post("/cases/{case_id}/evidence/{evidence_id}/reparse", status_code=202)
def reparse_with_decision(
    case_id: int,
    evidence_id: int,
    payload: ReparseDecision,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _write_access(db, user, case_id)
    if payload.date_order not in {"day_first", "month_first"}:
        raise HTTPException(422, "date_order must be day_first or month_first")
    evidence = db.get(Evidence, evidence_id)
    if not evidence or evidence.case_id != case_id:
        raise HTTPException(404, "Evidence not found")
    evidence.metadata_json = {
        **evidence.metadata_json,
        "parser_options": {
            **evidence.metadata_json.get("parser_options", {}),
            "date_order": payload.date_order,
        },
    }
    job = Job(
        case_id=case_id,
        evidence_id=evidence_id,
        type="ingest_extraction",
        status="queued",
        stage="Stored",
        progress=35,
        logs=[f"Re-parse requested with date order {payload.date_order}"],
    )
    db.add(job)
    db.flush()
    AuditService(db).log(
        action="evidence.parse_decision",
        actor=user.username,
        case_id=case_id,
        target_type="evidence",
        target_id=str(evidence_id),
        payload={"date_order": payload.date_order, "job_id": job.id},
    )
    db.commit()
    background.add_task(run_intake_job, job.id)
    return {"job_id": job.id, "status": job.status, "date_order": payload.date_order}
