from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.review import CaseReview
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.report_service import ReportService
from app.services.review_service import ReviewInput, review_out, select_exhibits, validate_review

router = APIRouter(tags=["v2 findings, exhibits and reports"])


@router.get("/cases/{case_id}/review")
def get_review(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    return review_out(db, case_id)


@router.put("/cases/{case_id}/review")
def save_review(case_id: int, payload: ReviewInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id, write=True)
    try:
        data = validate_review(db, case_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    current = db.get(CaseReview, case_id)
    if current is None:
        if payload.revision != 0:
            raise HTTPException(409, "Review changed; reload before saving")
        current = CaseReview(case_id=case_id, revision=0, findings=[], exhibits=[])
        db.add(current)
        db.flush()
    result = db.execute(update(CaseReview).where(CaseReview.case_id == case_id, CaseReview.revision == payload.revision).values(
        findings=data["findings"], exhibits=data["exhibits"], revision=payload.revision + 1).returning(CaseReview.revision))
    if result.scalar_one_or_none() is None:
        raise HTTPException(409, "Review changed; reload before saving")
    AuditService(db).log(action="case.review_saved", actor=user.username, case_id=case_id,
                         payload={"revision": payload.revision + 1, "findings": data["findings"], "exhibits": data["exhibits"]})
    db.commit()
    db.expire_all()
    return review_out(db, case_id)


@router.post("/cases/{case_id}/review/select-exhibits")
def optimise_exhibits(case_id: int, page_limit: int = Query(10, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    data = review_out(db, case_id)
    result = select_exhibits(data["findings"], data["exhibits"], page_limit)
    AuditService(db).log(action="report.exhibits_selected", actor=user.username, case_id=case_id, payload=result)
    db.commit()
    return result


@router.post("/cases/{case_id}/report.pdf")
def download_report(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    report = ReportService(db).generate_case_report(case_id)
    db.commit()
    return FileResponse(report.path, filename=f"parakh-case-{case_id}-review.pdf", media_type="application/pdf")


@router.post("/cases/{case_id}/report-data")
def report_data(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import base64
    from pathlib import Path
    require_case_access(db, user, case_id)
    report = ReportService(db).generate_case_report(case_id)
    db.commit()
    return {"pdf_base64": base64.b64encode(Path(report.path).read_bytes()).decode(), "sha256": report.sha256}
