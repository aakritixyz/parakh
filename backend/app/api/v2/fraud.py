from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.fraud_service import FraudService
from app.services.run_receipt import record_run

router = APIRouter(tags=["v2 fraud and authenticity"])


class LeadUpdate(BaseModel):
    status: str
    assignee: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=2000)


@router.get("/cases/{case_id}/fraud-review")
def fraud_review(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    result = FraudService(db).board(case_id)
    return record_run(db, case_id, user.username, "fraud", {}, result)


@router.patch("/cases/{case_id}/leads/{lead_id}")
def update_lead(
    case_id: int,
    lead_id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id, write=True)
    try:
        result = FraudService(db).update_lead(
            case_id, lead_id, user.username, payload.status, payload.assignee, payload.comment
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return result
