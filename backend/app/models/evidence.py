from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import UTCDateTime


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_case_upload_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    source_type: Mapped[str] = mapped_column(String(80), default="unknown")
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    md5: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(500), default="")
    acquired_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acquisition_note: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="evidence_items")
    events = relationship("Event", back_populates="evidence", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    extraction_id: Mapped[int | None] = mapped_column(ForeignKey("extractions.id"), nullable=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True, index=True)
    source_app: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    source_type: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(40), default="other", index=True)
    timestamp_utc: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    original_timestamp: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone_offset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    direction: Mapped[str] = mapped_column(String(16), default="unknown")
    from_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True, index=True)
    actor_entities: Mapped[list] = mapped_column(JSON, default=list)
    action: Mapped[str] = mapped_column(String(120), default="observed")
    content: Mapped[str] = mapped_column(Text, default="")
    content_lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id"), nullable=True, index=True)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_ref: Mapped[str] = mapped_column(String(255), default="")
    is_deleted_recovered: Mapped[bool] = mapped_column(default=False)
    confidence: Mapped[float] = mapped_column(default=1.0)
    parser_name: Mapped[str] = mapped_column(String(120), default="")
    parser_version: Mapped[str] = mapped_column(String(40), default="")
    dedupe_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evidence = relationship("Evidence", back_populates="events")
