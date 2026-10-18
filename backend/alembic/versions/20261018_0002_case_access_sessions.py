"""Case administration and revocable refresh sessions."""
import sqlalchemy as sa
from alembic import op

revision = "20261018_0002"
down_revision = "20261001_0001"
branch_labels = None
depends_on = None


def frozen_cases(include_new=False):
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    table = sa.Table("cases", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("case_number", sa.String(120)),
        sa.Column("jurisdiction", sa.String(200)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("classification", sa.String(80), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if include_new:
        table.append_column(sa.Column("offence_type", sa.String(120)))
        table.append_column(sa.Column("lead_investigator_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_case_lead")))
    return table


def upgrade():
    with op.batch_alter_table("cases", copy_from=frozen_cases()) as batch:
        batch.add_column(sa.Column("offence_type", sa.String(120), nullable=True))
        batch.add_column(sa.Column("lead_investigator_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_case_lead", "users", ["lead_investigator_id"], ["id"])
    if op.get_context().dialect.name == "sqlite":
        op.create_index("ix_cases_case_number", "cases", ["case_number"])
        op.create_index("ix_cases_title", "cases", ["title"])
    op.create_table("auth_sessions", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("refresh_hash", sa.String(64), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("audit_heads", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("sequence", sa.Integer(), nullable=False))
    op.execute(sa.text("INSERT INTO audit_heads (id, sequence) VALUES (1, 0)"))


def downgrade():
    op.drop_table("audit_heads")
    op.drop_index("ix_auth_sessions_user_id", "auth_sessions")
    op.drop_table("auth_sessions")
    with op.batch_alter_table("cases", copy_from=frozen_cases(True)) as batch:
        batch.drop_constraint("fk_case_lead", type_="foreignkey")
        batch.drop_column("lead_investigator_id")
        batch.drop_column("offence_type")

    if op.get_context().dialect.name == "sqlite":
        op.create_index("ix_cases_case_number", "cases", ["case_number"])
        op.create_index("ix_cases_title", "cases", ["title"])
