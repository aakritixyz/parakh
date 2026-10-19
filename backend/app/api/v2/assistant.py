import hashlib

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_case_access
from app.models.user import User
from app.services.assistant_service import AssistantService
from app.services.audit_service import AuditService

router = APIRouter(tags=["v2 cited assistant"])


class AssistantInput(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.post("/cases/{case_id}/assistant")
def cited_assistant(
    case_id: int,
    payload: AssistantInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_case_access(db, user, case_id)
    result = AssistantService(db).answer(case_id, payload.question)
    AuditService(db).log(
        action="assistant.answered",
        actor=user.username,
        case_id=case_id,
        target_type="case",
        target_id=str(case_id),
        payload={
            "question_sha256": hashlib.sha256(payload.question.encode()).hexdigest(),
            "refused": result["refused"],
            "citation_count": len(result["citations"]),
            "model": result["model_card"]["name"],
        },
    )
    db.commit()
    return result
