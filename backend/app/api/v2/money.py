from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.money_service import MoneyService
from app.services.run_receipt import record_run

router = APIRouter(tags=["v2 money analysis"])


@router.get("/cases/{case_id}/money")
def money_analysis(
    case_id: int,
    rule: str = Query(default="fifo"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    try:
        return record_run(db, case_id, user.username, "money", {"rule": rule}, MoneyService(db).analyse(case_id, rule))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
