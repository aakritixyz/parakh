from sqlalchemy import JSON, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaseReview(Base):
    __tablename__ = "case_reviews"

    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    exhibits: Mapped[list] = mapped_column(JSON, default=list)
