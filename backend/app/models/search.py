from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SearchRecord(Base):
    __tablename__ = "search_records"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)


class SearchKey(Base):
    __tablename__ = "search_keys"
    __table_args__ = (Index("ix_search_keys_lookup", "case_id", "kind", "value", "event_id"),)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), primary_key=True)
    case_id: Mapped[int] = mapped_column(Integer)
