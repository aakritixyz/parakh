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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DbRole(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    make: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    os: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imei: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    serial: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(160), default="Unlabelled device")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True, index=True)
    extraction_type: Mapped[str] = mapped_column(String(60), default="logical_export", index=True)
    source_name: Mapped[str] = mapped_column(String(200), default="")
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    parser_name: Mapped[str] = mapped_column(String(120), default="")
    parser_version: Mapped[str] = mapped_column(String(40), default="")
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Identifier(Base):
    __tablename__ = "identifiers"
    __table_args__ = (UniqueConstraint("type", "normalized_value", name="uq_identifier_type_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    normalized_value: Mapped[str] = mapped_column(String(255), index=True)
    raw_value: Mapped[str] = mapped_column(String(255))
    masked_for_display: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdentifierAlias(Base):
    __tablename__ = "identifier_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier_id: Mapped[int] = mapped_column(ForeignKey("identifiers.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    reason: Mapped[str] = mapped_column(String(120), default="observed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PartyIdentifier(Base):
    __tablename__ = "party_identifiers"
    __table_args__ = (UniqueConstraint("party_id", "identifier_id", name="uq_party_identifier"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    identifier_id: Mapped[int] = mapped_column(ForeignKey("identifiers.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(120), default="parser")


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    app: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    participants: Mapped[list] = mapped_column(JSON, default=list)
    first_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)


class EventRecipient(Base):
    __tablename__ = "event_recipients"
    __table_args__ = (UniqueConstraint("event_id", "party_id", name="uq_event_recipient"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="document", index=True)
    mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    exif: Mapped[dict] = mapped_column(JSON, default=dict)
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("case_id", "name", name="uq_case_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    color: Mapped[str] = mapped_column(String(32), default="#2f80ed")


class EventTag(Base):
    __tablename__ = "event_tags"
    __table_args__ = (UniqueConstraint("event_id", "tag_id", name="uq_event_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), index=True)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(60), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatchList(Base):
    __tablename__ = "watch_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatchListEntry(Base):
    __tablename__ = "watch_list_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_list_id: Mapped[int] = mapped_column(ForeignKey("watch_lists.id"), index=True)
    identifier_type: Mapped[str] = mapped_column(String(40), default="other")
    pattern: Mapped[str] = mapped_column(String(255), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    filter_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(32), default="Hashing", server_default="Hashing")
    cancel_requested: Mapped[bool] = mapped_column(default=False, server_default="0")
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    logs: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditCheckpoint(Base):
    __tablename__ = "audit_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_log_id: Mapped[int] = mapped_column(ForeignKey("audit_logs.id"), index=True)
    tip_hash: Mapped[str] = mapped_column(String(64), index=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
