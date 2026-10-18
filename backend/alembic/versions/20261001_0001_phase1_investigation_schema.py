"""Frozen investigation schema baseline.

Revision ID: 20261001_0001
Revises:

Keep this historical schema independent of application models. Databases already
at this revision retain their version; later schema changes need new revisions.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identifiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("raw_value", sa.String(length=255), nullable=False),
        sa.Column("masked_for_display", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "normalized_value", name="uq_identifier_type_value"),
    )
    op.create_index(
        op.f("ix_identifiers_normalized_value"), "identifiers", ["normalized_value"], unique=False
    )
    op.create_index(op.f("ix_identifiers_type"), "identifiers", ["type"], unique=False)
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("case_number", sa.String(length=120), nullable=True),
        sa.Column("jurisdiction", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cases_case_number"), "cases", ["case_number"], unique=False)
    op.create_index(op.f("ix_cases_title"), "cases", ["title"], unique=False)
    op.create_table(
        "identifier_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identifier_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["identifier_id"],
            ["identifiers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_identifier_aliases_alias"), "identifier_aliases", ["alias"], unique=False
    )
    op.create_index(
        op.f("ix_identifier_aliases_identifier_id"),
        "identifier_aliases",
        ["identifier_id"],
        unique=False,
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_case_id"), "audit_logs", ["case_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entry_hash"), "audit_logs", ["entry_hash"], unique=False)
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=60), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookmarks_case_id"), "bookmarks", ["case_id"], unique=False)
    op.create_index(op.f("ix_bookmarks_target_id"), "bookmarks", ["target_id"], unique=False)
    op.create_index(op.f("ix_bookmarks_target_type"), "bookmarks", ["target_type"], unique=False)
    op.create_table(
        "case_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_membership_user"),
    )
    op.create_index(
        op.f("ix_case_memberships_case_id"), "case_memberships", ["case_id"], unique=False
    )
    op.create_index(
        op.f("ix_case_memberships_user_id"), "case_memberships", ["user_id"], unique=False
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=60), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_case_id"), "comments", ["case_id"], unique=False)
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("os", sa.String(length=120), nullable=True),
        sa.Column("imei", sa.String(length=64), nullable=True),
        sa.Column("serial", sa.String(length=120), nullable=True),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_case_id"), "devices", ["case_id"], unique=False)
    op.create_index(op.f("ix_devices_imei"), "devices", ["imei"], unique=False)
    op.create_index(op.f("ix_devices_serial"), "devices", ["serial"], unique=False)
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("canonical", sa.String(length=255), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("masked", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "kind", "canonical", name="uq_case_entity"),
    )
    op.create_index(op.f("ix_entities_canonical"), "entities", ["canonical"], unique=False)
    op.create_index(op.f("ix_entities_case_id"), "entities", ["case_id"], unique=False)
    op.create_index(op.f("ix_entities_kind"), "entities", ["kind"], unique=False)
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("md5", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("acquired_by", sa.String(length=120), nullable=True),
        sa.Column("acquisition_note", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_upload_idempotency"),
    )
    op.create_index(op.f("ix_evidence_case_id"), "evidence", ["case_id"], unique=False)
    op.create_index(op.f("ix_evidence_sha256"), "evidence", ["sha256"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_case_id"), "jobs", ["case_id"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_type"), "jobs", ["type"], unique=False)
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee", sa.String(length=120), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_case_id"), "leads", ["case_id"], unique=False)
    op.create_table(
        "owners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_owners_case_id"), "owners", ["case_id"], unique=False)
    op.create_index(op.f("ix_owners_display_name"), "owners", ["display_name"], unique=False)
    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parties_case_id"), "parties", ["case_id"], unique=False)
    op.create_index(op.f("ix_parties_display_name"), "parties", ["display_name"], unique=False)
    op.create_index(op.f("ix_parties_kind"), "parties", ["kind"], unique=False)
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_case_id"), "reports", ["case_id"], unique=False)
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("filter_spec", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_searches_case_id"), "saved_searches", ["case_id"], unique=False)
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "name", name="uq_case_tag"),
    )
    op.create_index(op.f("ix_tags_case_id"), "tags", ["case_id"], unique=False)
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=False)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_case_id"), "tasks", ["case_id"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_table(
        "threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("app", sa.String(length=80), nullable=False),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("first_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_threads_app"), "threads", ["app"], unique=False)
    op.create_index(op.f("ix_threads_case_id"), "threads", ["case_id"], unique=False)
    op.create_table(
        "watch_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watch_lists_case_id"), "watch_lists", ["case_id"], unique=False)
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("thumbnail_key", sa.String(length=500), nullable=True),
        sa.Column("phash", sa.String(length=64), nullable=True),
        sa.Column("exif", sa.JSON(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifacts_case_id"), "artifacts", ["case_id"], unique=False)
    op.create_index(op.f("ix_artifacts_evidence_id"), "artifacts", ["evidence_id"], unique=False)
    op.create_index(op.f("ix_artifacts_kind"), "artifacts", ["kind"], unique=False)
    op.create_index(op.f("ix_artifacts_phash"), "artifacts", ["phash"], unique=False)
    op.create_index(op.f("ix_artifacts_sha256"), "artifacts", ["sha256"], unique=False)
    op.create_table(
        "audit_checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_log_id", sa.Integer(), nullable=False),
        sa.Column("tip_hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["audit_log_id"],
            ["audit_logs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_checkpoints_audit_log_id"),
        "audit_checkpoints",
        ["audit_log_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_checkpoints_tip_hash"), "audit_checkpoints", ["tip_hash"], unique=False
    )
    op.create_table(
        "authenticity_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("detector_version", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authenticity_reports_case_id"), "authenticity_reports", ["case_id"], unique=False
    )
    op.create_index(
        op.f("ix_authenticity_reports_evidence_id"),
        "authenticity_reports",
        ["evidence_id"],
        unique=False,
    )
    op.create_table(
        "extractions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("extraction_type", sa.String(length=60), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extractions_case_id"), "extractions", ["case_id"], unique=False)
    op.create_index(op.f("ix_extractions_device_id"), "extractions", ["device_id"], unique=False)
    op.create_index(
        op.f("ix_extractions_evidence_id"), "extractions", ["evidence_id"], unique=False
    )
    op.create_index(
        op.f("ix_extractions_extraction_type"), "extractions", ["extraction_type"], unique=False
    )
    op.create_index(op.f("ix_extractions_owner_id"), "extractions", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_extractions_parse_status"), "extractions", ["parse_status"], unique=False
    )
    op.create_table(
        "party_identifiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("identifier_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["identifier_id"],
            ["identifiers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["parties.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("party_id", "identifier_id", name="uq_party_identifier"),
    )
    op.create_index(
        op.f("ix_party_identifiers_identifier_id"),
        "party_identifiers",
        ["identifier_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_party_identifiers_party_id"), "party_identifiers", ["party_id"], unique=False
    )
    op.create_table(
        "watch_list_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watch_list_id", sa.Integer(), nullable=False),
        sa.Column("identifier_type", sa.String(length=40), nullable=False),
        sa.Column("pattern", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["watch_list_id"],
            ["watch_lists.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_watch_list_entries_pattern"), "watch_list_entries", ["pattern"], unique=False
    )
    op.create_index(
        op.f("ix_watch_list_entries_watch_list_id"),
        "watch_list_entries",
        ["watch_list_id"],
        unique=False,
    )
    op.create_table(
        "authenticity_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("signal", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["authenticity_reports.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authenticity_findings_evidence_id"),
        "authenticity_findings",
        ["evidence_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_authenticity_findings_report_id"),
        "authenticity_findings",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_authenticity_findings_signal"), "authenticity_findings", ["signal"], unique=False
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("extraction_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("source_app", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_timestamp", sa.String(length=120), nullable=True),
        sa.Column("timezone_offset", sa.String(length=16), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("from_party_id", sa.Integer(), nullable=True),
        sa.Column("actor_entities", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_lang", sa.String(length=16), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("location", sa.JSON(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("raw_ref", sa.String(length=255), nullable=False),
        sa.Column("is_deleted_recovered", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Double(), nullable=False),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
        ),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["extractions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["from_party_id"],
            ["parties.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["threads.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_case_id"), "events", ["case_id"], unique=False)
    op.create_index(op.f("ix_events_dedupe_hash"), "events", ["dedupe_hash"], unique=False)
    op.create_index(op.f("ix_events_event_type"), "events", ["event_type"], unique=False)
    op.create_index(op.f("ix_events_evidence_id"), "events", ["evidence_id"], unique=False)
    op.create_index(op.f("ix_events_extraction_id"), "events", ["extraction_id"], unique=False)
    op.create_index(op.f("ix_events_from_party_id"), "events", ["from_party_id"], unique=False)
    op.create_index(op.f("ix_events_owner_id"), "events", ["owner_id"], unique=False)
    op.create_index(op.f("ix_events_source_app"), "events", ["source_app"], unique=False)
    op.create_index(op.f("ix_events_source_type"), "events", ["source_type"], unique=False)
    op.create_index(op.f("ix_events_thread_id"), "events", ["thread_id"], unique=False)
    op.create_index(op.f("ix_events_timestamp_utc"), "events", ["timestamp_utc"], unique=False)
    op.create_table(
        "event_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["parties.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "party_id", name="uq_event_recipient"),
    )
    op.create_index(
        op.f("ix_event_recipients_event_id"), "event_recipients", ["event_id"], unique=False
    )
    op.create_index(
        op.f("ix_event_recipients_party_id"), "event_recipients", ["party_id"], unique=False
    )
    op.create_table(
        "event_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "tag_id", name="uq_event_tag"),
    )
    op.create_index(op.f("ix_event_tags_event_id"), "event_tags", ["event_id"], unique=False)
    op.create_index(op.f("ix_event_tags_tag_id"), "event_tags", ["tag_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is disabled to preserve forensic evidence and audit history."
    )
