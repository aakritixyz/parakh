from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.correlation_service import CorrelationService

router = APIRouter(tags=["v2 correlation and reconstruction"])


@router.get("/cases/{case_id}/correlation")
def correlation(
    case_id: int,
    source: str | None = Query(default=None),
    target: str | None = Query(default=None),
    focus: str | None = Query(default=None),
    depth: int = Query(default=1, ge=0, le=4),
    clock_confidence: float = Query(default=1.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    return CorrelationService(db).analyse(
        case_id,
        source=source,
        target=target,
        focus=focus,
        depth=depth,
        clock_confidence=clock_confidence,
    )
