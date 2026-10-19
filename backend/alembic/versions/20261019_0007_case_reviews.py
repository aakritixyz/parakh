"""Persist reviewed findings and exhibit trays."""
import sqlalchemy as sa
from alembic import op

revision = "20261019_0007"
down_revision = "20261018_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "case_reviews",
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("exhibits", sa.JSON(), nullable=False),
    )
    op.create_index("ix_events_case_type_time", "events", ["case_id", "event_type", "timestamp_utc"])


def downgrade():
    op.drop_index("ix_events_case_type_time", table_name="events")
    op.drop_table("case_reviews")
