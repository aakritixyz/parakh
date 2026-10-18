from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.integrity_service import IntegrityService
from app.services.report_service import ReportService

router = APIRouter(tags=["v2 integrity"])


@router.get("/cases/{case_id}/integrity")
def integrity(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    return IntegrityService(db).status(case_id)


@router.post("/cases/{case_id}/integrity/rehash")
def rehash(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    result = IntegrityService(db).status(case_id)
    AuditService(db).log(
        action="integrity.rehashed",
        actor=user.username,
        case_id=case_id,
        payload={"valid": result["valid"]},
    )
    db.commit()
    return result


@router.post("/cases/{case_id}/integrity/tamper-demo")
def tamper_demo(
    case_id: int,
    target: str = Query("file"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    if target not in {"file", "audit"}:
        raise HTTPException(422, "target must be file or audit")
    result = IntegrityService(db).tamper_demo(case_id, target)
    AuditService(db).log(
        action="integrity.tamper_demo",
        actor=user.username,
        case_id=case_id,
        payload={"target": target, "detected": result["detected"]},
    )
    db.commit()
    return result


@router.post("/cases/{case_id}/integrity/export")
def export_bundle(
    case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    require_case_access(db, user, case_id)
    report = ReportService(db).export_case_bundle(case_id)
    db.commit()
    return FileResponse(
        report.path, filename=f"parakh-case-{case_id}-verified.zip", media_type="application/zip"
    )
