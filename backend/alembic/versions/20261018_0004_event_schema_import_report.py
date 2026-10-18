"""Unified event parties and document extraction receipts."""
import sqlalchemy as sa

from alembic import op

revision = "20261018_0004"
down_revision = "20261018_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("from_party_text", sa.String(255), nullable=True))
    op.add_column("events", sa.Column("to_party_text", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id"), nullable=False),
        sa.Column("engine", sa.String(120), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("boxes", sa.JSON(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_extractions_case_id", "document_extractions", ["case_id"])
    op.create_index(
        "ix_document_extractions_evidence_id", "document_extractions", ["evidence_id"], unique=True
    )


def downgrade():
    op.drop_index("ix_document_extractions_evidence_id", table_name="document_extractions")
    op.drop_index("ix_document_extractions_case_id", table_name="document_extractions")
    op.drop_table("document_extractions")
    op.drop_column("events", "to_party_text")
    op.drop_column("events", "from_party_text")
