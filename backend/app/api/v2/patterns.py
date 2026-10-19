from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.pattern_service import PatternService
from app.services.run_receipt import record_run

router = APIRouter(tags=["v2 patterns and anomalies"])


@router.get("/cases/{case_id}/patterns")
def patterns(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    return record_run(db, case_id, user.username, "pattern", {}, PatternService(db).analyse(case_id))
