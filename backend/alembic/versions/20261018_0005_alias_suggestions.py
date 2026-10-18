"""Auditable alias suggestions and reversible investigator decisions."""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0005"
down_revision = "20261018_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alias_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("identifier_id", sa.Integer(), sa.ForeignKey("identifiers.id"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("feedback_count", sa.Integer(), nullable=False),
        sa.Column("prior_party_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("case_id", "party_id", "identifier_id", name="uq_alias_suggestion_pair"),
    )
    op.create_index("ix_alias_suggestions_case_id", "alias_suggestions", ["case_id"])
    op.create_index("ix_alias_suggestions_party_id", "alias_suggestions", ["party_id"])
    op.create_index("ix_alias_suggestions_identifier_id", "alias_suggestions", ["identifier_id"])
    op.create_index("ix_alias_suggestions_status", "alias_suggestions", ["status"])


def downgrade():
    op.drop_index("ix_alias_suggestions_status", table_name="alias_suggestions")
    op.drop_index("ix_alias_suggestions_identifier_id", table_name="alias_suggestions")
    op.drop_index("ix_alias_suggestions_party_id", table_name="alias_suggestions")
    op.drop_index("ix_alias_suggestions_case_id", table_name="alias_suggestions")
    op.drop_table("alias_suggestions")
