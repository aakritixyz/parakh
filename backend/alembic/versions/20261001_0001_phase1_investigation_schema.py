"""Phase 1 investigation schema.

Revision ID: 20261001_0001
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op
from app.core.database import Base
from app.models import *  # noqa: F403

revision = "20261001_0001"
down_revision = None
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _add_missing(table: str, columns: Iterable[sa.Column]) -> None:
    existing = _columns(table)
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    _add_missing(
        "cases",
        [
            sa.Column("case_number", sa.String(length=120), nullable=True),
            sa.Column("jurisdiction", sa.String(length=200), nullable=True),
            sa.Column("classification", sa.String(length=80), server_default="standard", nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
    )
    _add_missing(
        "case_memberships",
        [
            sa.Column("granted_by", sa.Integer(), nullable=True),
            sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
    )
    _add_missing(
        "evidence",
        [
            sa.Column("mime", sa.String(length=120), server_default="application/octet-stream", nullable=False),
            sa.Column("storage_key", sa.String(length=500), server_default="", nullable=False),
            sa.Column("acquired_by", sa.String(length=120), nullable=True),
            sa.Column("acquisition_note", sa.Text(), server_default="", nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        ],
    )
    _add_missing(
        "events",
        [
            sa.Column("extraction_id", sa.Integer(), nullable=True),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("source_app", sa.String(length=80), server_default="unknown", nullable=False),
            sa.Column("event_type", sa.String(length=40), server_default="other", nullable=False),
            sa.Column("timezone_offset", sa.String(length=16), nullable=True),
            sa.Column("direction", sa.String(length=16), server_default="unknown", nullable=False),
            sa.Column("from_party_id", sa.Integer(), nullable=True),
            sa.Column("content_lang", sa.String(length=16), nullable=True),
            sa.Column("thread_id", sa.Integer(), nullable=True),
            sa.Column("attachments", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("is_deleted_recovered", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("parser_name", sa.String(length=120), server_default="", nullable=False),
            sa.Column("parser_version", sa.String(length=40), server_default="", nullable=False),
            sa.Column("dedupe_hash", sa.String(length=64), nullable=True),
        ],
    )
    _add_missing(
        "leads",
        [
            sa.Column("assignee", sa.String(length=120), nullable=True),
        ],
    )
    _add_missing(
        "reports",
        [
            sa.Column("manifest_hash", sa.String(length=64), server_default="", nullable=False),
            sa.Column("status", sa.String(length=32), server_default="generated", nullable=False),
            sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        ],
    )


def downgrade() -> None:
    # Phase 1 is a forward-only prototype migration. Dropping forensic schema
    # tables/columns could destroy audit and evidence linkage history.
    raise NotImplementedError("Downgrade is intentionally disabled for forensic audit safety.")
