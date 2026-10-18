from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.origin_service import OriginService

router = APIRouter(tags=["v2 origin and clocks"])


@router.get("/cases/{case_id}/origin")
def origin(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_case_access(db, user, case_id)
    return OriginService(db).analyse(case_id)
