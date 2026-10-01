from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseMembership
from app.models.user import User
from app.services.audit_service import AuditService


class CaseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_case(self, title: str, description: str, actor: str) -> Case:
        case = Case(title=title, description=description)
        self.db.add(case)
        self.db.flush()
        user = self.db.scalar(select(User).where(User.username == actor))
        if user:
            self.db.add(
                CaseMembership(
                    case_id=case.id,
                    user_id=user.id,
                    role="investigator" if user.role != "admin" else "admin",
                    granted_by=user.id,
                )
            )
        AuditService(self.db).log(
            action="case.created",
            actor=actor,
            case_id=case.id,
            target_type="case",
            target_id=str(case.id),
            payload={"title": title},
        )
        return case
