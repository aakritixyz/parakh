"""Explicit schema lifecycle; serving requests must never create or stamp tables."""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from alembic import command
from app.core.database import Base

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BASELINE_REVISION = "20261001_0001"


def migration_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def require_current_schema(engine: Engine) -> None:
    expected = set(ScriptDirectory.from_config(migration_config()).get_heads())
    with engine.connect() as connection:
        actual = set(MigrationContext.configure(connection).get_current_heads())
    if actual != expected:
        raise RuntimeError(
            "Database schema is not at the current migration. Run "
            "`python -m app.cli migrate` from backend/ before starting or seeding Parakh. "
            "For an existing unversioned prototype, back it up and see --adopt-existing."
        )


def migrate_database(engine: Engine, *, adopt_existing: bool = False) -> None:
    # Importing models registers metadata for the adoption comparison only. The
    # historical migration itself contains frozen DDL and never imports models.
    import app.models  # noqa: F401

    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        current = MigrationContext.configure(connection)
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if not current.get_current_heads() and tables:
            if not adopt_existing:
                raise RuntimeError(
                    "Unversioned database found. Back it up, then run "
                    "`python -m app.cli migrate --adopt-existing` to validate it before stamping."
                )
            differences = compare_metadata(
                MigrationContext.configure(connection, opts={"compare_server_default": True}),
                Base.metadata,
            )
            if differences:
                raise RuntimeError(
                    "Existing schema differs from this release; no adoption was performed. "
                    "Keep the backup and use a new database or a reviewed legacy migration."
                )
            command.stamp(config, "head")
        command.upgrade(config, "head")
