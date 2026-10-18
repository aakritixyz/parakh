from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseMembership
from app.models.evidence import Evidence
from app.models.investigation import Job
from app.models.user import User

WRITE_ROLES = {"admin", "investigator", "analyst"}


def can_access_case(db: Session, user: User, case_id: int, *, write: bool = False) -> bool:
    if user.role == "admin":
        return True
    membership = db.scalar(
        select(CaseMembership).where(CaseMembership.case_id == case_id, CaseMembership.user_id == user.id)
    )
    if not membership:
        return False
    if write and (user.role not in WRITE_ROLES or membership.role not in WRITE_ROLES):
        return False
    return True


def require_case_access(db: Session, user: User, case_id: int, *, write: bool = False) -> None:
    if not db.get(Case, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    if not can_access_case(db, user, case_id, write=write):
        raise HTTPException(status_code=403, detail="Case access denied")


def require_evidence_access(db: Session, user: User, evidence_id: int, *, write: bool = False) -> Evidence:
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    require_case_access(db, user, evidence.case_id, write=write)
    return evidence


def require_job_access(db: Session, user: User, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.case_id is not None:
        require_case_access(db, user, job.case_id)
    elif user.role != "admin":
        raise HTTPException(status_code=403, detail="Job access denied")
    return job
