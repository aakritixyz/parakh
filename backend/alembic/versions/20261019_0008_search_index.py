"""Materialized, incrementally invalidated search facets."""
import sqlalchemy as sa
from alembic import op

revision = "20261019_0008"
down_revision = "20261019_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("search_records", sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True), sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False))
    op.create_index("ix_search_records_case_id", "search_records", ["case_id"])
    op.create_table("search_keys", sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True), sa.Column("kind", sa.String(16), primary_key=True), sa.Column("value", sa.String(500), primary_key=True), sa.Column("case_id", sa.Integer(), nullable=False))
    op.create_index("ix_search_keys_lookup", "search_keys", ["case_id", "kind", "value", "event_id"])
    if op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER search_events_{action.lower()} AFTER {action} ON events BEGIN DELETE FROM search_records WHERE event_id=old.id; DELETE FROM search_keys WHERE event_id=old.id; END")


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS search_events_{action}")
    op.drop_index("ix_search_keys_lookup", table_name="search_keys")
    op.drop_table("search_keys")
    op.drop_index("ix_search_records_case_id", table_name="search_records")
    op.drop_table("search_records")
