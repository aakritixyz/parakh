from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.evidence import Evidence
from app.models.investigation import Device, Job, Owner
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.evidence_service import EvidenceService
from app.services.file_types import sniff_type
from app.services.intake_worker import run_intake_job

router = APIRouter(tags=["v2 evidence intake"])


class OwnerInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)


class DeviceInput(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    make: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    os: str | None = Field(default=None, max_length=120)
    serial: str | None = Field(default=None, max_length=120)


def _case_write(db: Session, user: User, case_id: int) -> None:
    require_case_access(db, user, case_id, write=True)


def _job_out(job: Job) -> dict:
    return {
        "id": job.id,
        "evidence_id": job.evidence_id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "attempt": job.attempt,
        "error": job.error,
        "logs": job.logs,
    }


def _evidence_out(evidence: Evidence, job: Job | None, duplicate: bool) -> dict:
    return {
        "id": evidence.id,
        "filename": evidence.filename,
        "archive_path": evidence.archive_path,
        "parent_evidence_id": evidence.parent_evidence_id,
        "sha256": evidence.sha256,
        "md5": evidence.md5,
        "size_bytes": evidence.size_bytes,
        "source_type": evidence.source_type,
        "mime": evidence.mime,
        "magic_byte_warning": evidence.metadata_json.get("magic_byte_warning"),
        "duplicate": duplicate,
        "job": _job_out(job) if job else None,
    }


@router.get("/cases/{case_id}/owners")
def list_owners(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    return [{"id": item.id, "display_name": item.display_name, "notes": item.notes} for item in db.scalars(select(Owner).where(Owner.case_id == case_id).order_by(Owner.display_name))]


@router.post("/cases/{case_id}/owners", status_code=201)
def create_owner(case_id: int, payload: OwnerInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _case_write(db, user, case_id)
    owner = Owner(case_id=case_id, display_name=payload.display_name.strip(), notes=payload.notes)
    db.add(owner)
    db.flush()
    AuditService(db).log(action="owner.created", actor=user.username, case_id=case_id, target_type="owner", target_id=str(owner.id), payload={"display_name": owner.display_name})
    db.commit()
    return {"id": owner.id, "display_name": owner.display_name, "notes": owner.notes}


@router.get("/cases/{case_id}/devices")
def list_devices(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    return [{"id": item.id, "label": item.label, "make": item.make, "model": item.model, "os": item.os, "serial": item.serial} for item in db.scalars(select(Device).where(Device.case_id == case_id).order_by(Device.label))]


@router.post("/cases/{case_id}/devices", status_code=201)
def create_device(case_id: int, payload: DeviceInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _case_write(db, user, case_id)
    device = Device(case_id=case_id, **payload.model_dump())
    db.add(device)
    db.flush()
    AuditService(db).log(action="device.created", actor=user.username, case_id=case_id, target_type="device", target_id=str(device.id), payload={"label": device.label})
    db.commit()
    return {"id": device.id, **payload.model_dump()}


@router.post("/cases/{case_id}/intake", status_code=202)
def import_evidence(
    case_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    owner_id: int = Form(...),
    device_id: int | None = Form(default=None),
    handed_over_by: str = Form(..., min_length=1, max_length=200),
    acquired_at: datetime = Form(...),
    acquisition_method: str = Form(..., min_length=1, max_length=200),
    note: str = Form(default="", max_length=4000),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _case_write(db, user, case_id)
    owner = db.get(Owner, owner_id)
    if not owner or owner.case_id != case_id:
        raise HTTPException(422, "Owner does not belong to this case")
    if device_id is not None:
        device = db.get(Device, device_id)
        if not device or device.case_id != case_id:
            raise HTTPException(422, "Device does not belong to this case")
    service = EvidenceService(db)
    acquisition_note = f"Handed over by: {handed_over_by}\nMethod: {acquisition_method}\nNotes: {note}".strip()
    try:
        evidence, job, duplicate = service.seal(
            case_id=case_id, fileobj=file.file, filename=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream", actor=user.username,
            idempotency_key=idempotency_key, source_type=source_type, owner_id=owner_id,
            device_id=device_id, acquisition_note=acquisition_note, acquired_by=user.username,
            received_at=acquired_at,
        )
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from exc
    if duplicate:
        db.rollback()
        return {"items": [_evidence_out(evidence, job, True)], "duplicate_count": 1}
    if job is None:  # Defensive: every newly sealed item receives a job.
        raise HTTPException(500, "Import job was not created")

    items: list[tuple[Evidence, Job | None, bool]] = [(evidence, job, False)]
    if sniff_type(Path(evidence.storage_path)) == "application/zip":
        try:
            members = _safe_members(Path(evidence.storage_path))
            job.status, job.stage, job.progress = "completed", "Done", 100
            job.logs = [*job.logs, f"Validated ZIP with {len(members)} file members"]
            for index, info in enumerate(members):
                with ZipFile(evidence.storage_path) as archive, archive.open(info) as member:
                    child, child_job, child_duplicate = service.seal(
                        case_id=case_id, fileobj=member, filename=PurePosixPath(info.filename).name,
                        content_type=mimetypes.guess_type(info.filename)[0] or "application/octet-stream",
                        actor=user.username, idempotency_key=f"{idempotency_key or evidence.sha256}:member:{index}",
                        source_type=None, owner_id=owner_id, device_id=device_id,
                        acquisition_note=acquisition_note, acquired_by=user.username, received_at=acquired_at,
                        parent_evidence_id=evidence.id, archive_path=info.filename,
                    )
                items.append((child, child_job, child_duplicate))
        except (BadZipFile, ValueError) as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
    db.commit()
    for _, queued_job, was_duplicate in items:
        if queued_job and queued_job.status == "queued" and not was_duplicate:
            background.add_task(run_intake_job, queued_job.id)
    return {"items": [_evidence_out(*item) for item in items], "duplicate_count": sum(1 for _, _, duplicate in items if duplicate)}


def _safe_members(path: Path):
    settings = get_settings()
    with ZipFile(path) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) > settings.max_zip_members:
            raise ValueError("ZIP contains too many members")
        total = 0
        for item in members:
            member_path = PurePosixPath(item.filename)
            if member_path.is_absolute() or ".." in member_path.parts or "\\" in item.filename:
                raise ValueError("ZIP contains an unsafe member path")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("ZIP symbolic links are not supported")
            if item.flag_bits & 0x1:
                raise ValueError("Encrypted ZIP members are not supported")
            total += item.file_size
            if total > settings.max_zip_uncompressed_bytes:
                raise ValueError("ZIP uncompressed size exceeds the safety limit")
            ratio = item.file_size / max(item.compress_size, 1)
            if ratio > settings.max_zip_ratio:
                raise ValueError("ZIP compression ratio exceeds the safety limit")
        return members


@router.get("/cases/{case_id}/intake/jobs")
def intake_jobs(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    jobs = db.scalars(select(Job).where(Job.case_id == case_id, Job.type == "ingest_extraction").order_by(Job.id))
    return [_job_out(job) for job in jobs]


@router.post("/cases/{case_id}/intake/jobs/{job_id}/cancel")
def cancel_job(case_id: int, job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _case_write(db, user, case_id)
    job = db.get(Job, job_id)
    if not job or job.case_id != case_id:
        raise HTTPException(404, "Import job not found")
    if job.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(409, "Import job is already finished")
    job.cancel_requested = True
    AuditService(db).log(action="evidence.import_cancel_requested", actor=user.username, case_id=case_id, target_type="job", target_id=str(job.id))
    db.commit()
    return _job_out(job)


@router.post("/cases/{case_id}/intake/jobs/{job_id}/retry", status_code=202)
def retry_job(case_id: int, job_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _case_write(db, user, case_id)
    prior = db.get(Job, job_id)
    if not prior or prior.case_id != case_id:
        raise HTTPException(404, "Import job not found")
    if prior.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled imports can be retried")
    job = Job(case_id=case_id, evidence_id=prior.evidence_id, type=prior.type, status="queued", stage="Stored", progress=35, attempt=prior.attempt + 1, logs=[f"Retry of job {prior.id}"])
    db.add(job)
    db.flush()
    AuditService(db).log(action="evidence.import_retried", actor=user.username, case_id=case_id, target_type="job", target_id=str(job.id), payload={"prior_job_id": prior.id, "attempt": job.attempt})
    db.commit()
    background.add_task(run_intake_job, job.id)
    return _job_out(job)
