"""Model registry and auditable model cards."""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0006"
down_revision = "20261018_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("licence", sa.String(120), nullable=False),
        sa.Column("training_data", sa.Text(), nullable=False),
        sa.Column("known_limits", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("explanations", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("evaluation_label", sa.String(80), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_model_name_version"),
    )
    op.create_index("ix_model_records_name", "model_records", ["name"])


def downgrade():
    op.drop_index("ix_model_records_name", table_name="model_records")
    op.drop_table("model_records")
