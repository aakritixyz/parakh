from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.identity_service import IdentityService

router = APIRouter(tags=["v2 people and aliases"])


@router.get("/cases/{case_id}/identities")
def identities(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    result = IdentityService(db).overview(case_id)
    db.commit()
    return result


@router.post("/cases/{case_id}/alias-suggestions/{suggestion_id}/confirm")
def confirm_alias(
    case_id: int,
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id, write=True)
    try:
        result = IdentityService(db).confirm(case_id, suggestion_id, user.username)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    return result


@router.post("/cases/{case_id}/alias-suggestions/{suggestion_id}/unmerge")
def unmerge_alias(
    case_id: int,
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id, write=True)
    try:
        result = IdentityService(db).unmerge(case_id, suggestion_id, user.username)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    return result
