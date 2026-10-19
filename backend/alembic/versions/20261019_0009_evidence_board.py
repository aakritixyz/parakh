"""Versioned evidence board state and immutable named snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0009"
down_revision = "20261019_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evidence_boards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_boards_case_id", "evidence_boards", ["case_id"], unique=True)
    op.create_table(
        "board_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("evidence_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("board_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("board_id", "name", name="uq_board_snapshot_name"),
    )
    op.create_index("ix_board_snapshots_board_id", "board_snapshots", ["board_id"])


def downgrade():
    op.drop_index("ix_board_snapshots_board_id", table_name="board_snapshots")
    op.drop_table("board_snapshots")
    op.drop_index("ix_evidence_boards_case_id", table_name="evidence_boards")
    op.drop_table("evidence_boards")
