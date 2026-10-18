"""Evidence intake metadata, exact dedupe and background job state."""
import sqlalchemy as sa
from alembic import op

revision = "20261018_0003"
down_revision = "20261018_0002"
branch_labels = None
depends_on = None


def frozen_evidence(include_new=False):
    metadata = sa.MetaData()
    for name in ("cases", "owners", "devices"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("mime", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("md5", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("acquired_by", sa.String(120)),
        sa.Column("acquisition_note", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(120)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]
    if include_new:
        columns += [
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", name="fk_evidence_owner")),
            sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", name="fk_evidence_device")),
            sa.Column("parent_evidence_id", sa.Integer()),
            sa.Column("archive_path", sa.String(500)),
        ]
    table = sa.Table(
        "evidence", metadata, *columns,
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_upload_idempotency"),
        *( [sa.UniqueConstraint("case_id", "sha256", name="uq_case_evidence_sha256")] if include_new else [] ),
    )
    if include_new:
        sa.ForeignKeyConstraint([table.c.parent_evidence_id], [table.c.id], name="fk_evidence_parent")
    return table


def frozen_jobs(include_new=False):
    metadata = sa.MetaData()
    sa.Table("cases", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("evidence", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id")),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]
    if include_new:
        columns += [
            sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id", name="fk_job_evidence")),
            sa.Column("stage", sa.String(32), nullable=False, server_default="Hashing"),
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        ]
    return sa.Table("jobs", metadata, *columns)


def upgrade():
    with op.batch_alter_table("evidence", copy_from=frozen_evidence()) as batch:
        batch.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("device_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("parent_evidence_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("archive_path", sa.String(500), nullable=True))
        batch.create_foreign_key("fk_evidence_owner", "owners", ["owner_id"], ["id"])
        batch.create_foreign_key("fk_evidence_device", "devices", ["device_id"], ["id"])
        batch.create_foreign_key("fk_evidence_parent", "evidence", ["parent_evidence_id"], ["id"])
        batch.create_unique_constraint("uq_case_evidence_sha256", ["case_id", "sha256"])
        batch.create_index("ix_evidence_owner_id", ["owner_id"])
        batch.create_index("ix_evidence_device_id", ["device_id"])
        batch.create_index("ix_evidence_parent_evidence_id", ["parent_evidence_id"])
    with op.batch_alter_table("jobs", copy_from=frozen_jobs()) as batch:
        batch.add_column(sa.Column("evidence_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("stage", sa.String(32), nullable=False, server_default="Hashing"))
        batch.add_column(sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key("fk_job_evidence", "evidence", ["evidence_id"], ["id"])
        batch.create_index("ix_jobs_evidence_id", ["evidence_id"])
    if op.get_context().dialect.name == "sqlite":
        op.create_index("ix_evidence_case_id", "evidence", ["case_id"])
        op.create_index("ix_evidence_sha256", "evidence", ["sha256"])
        op.create_index("ix_jobs_case_id", "jobs", ["case_id"])
        op.create_index("ix_jobs_status", "jobs", ["status"])
        op.create_index("ix_jobs_type", "jobs", ["type"])


def downgrade():
    with op.batch_alter_table("jobs", copy_from=frozen_jobs(True)) as batch:
        batch.drop_index("ix_jobs_evidence_id")
        batch.drop_constraint("fk_job_evidence", type_="foreignkey")
        batch.drop_column("attempt")
        batch.drop_column("cancel_requested")
        batch.drop_column("stage")
        batch.drop_column("evidence_id")
    with op.batch_alter_table("evidence", copy_from=frozen_evidence(True)) as batch:
        batch.drop_index("ix_evidence_parent_evidence_id")
        batch.drop_index("ix_evidence_device_id")
        batch.drop_index("ix_evidence_owner_id")
        batch.drop_constraint("uq_case_evidence_sha256", type_="unique")
        batch.drop_constraint("fk_evidence_parent", type_="foreignkey")
        batch.drop_constraint("fk_evidence_device", type_="foreignkey")
        batch.drop_constraint("fk_evidence_owner", type_="foreignkey")
        batch.drop_column("archive_path")
        batch.drop_column("parent_evidence_id")
        batch.drop_column("device_id")
        batch.drop_column("owner_id")
    if op.get_context().dialect.name == "sqlite":
        op.create_index("ix_evidence_case_id", "evidence", ["case_id"])
        op.create_index("ix_evidence_sha256", "evidence", ["sha256"])
        op.create_index("ix_jobs_case_id", "jobs", ["case_id"])
        op.create_index("ix_jobs_status", "jobs", ["status"])
        op.create_index("ix_jobs_type", "jobs", ["type"])
