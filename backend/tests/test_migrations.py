import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, Table, create_engine, inspect, text

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.core.database import Base
from app.core.migrations import migrate_database, migration_config, require_current_schema


@pytest.fixture()
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.sqlite'}")
    yield engine
    engine.dispose()


def test_migration_creates_complete_schema_and_is_repeatable(database):
    migrate_database(database)
    require_current_schema(database)
    inspector = inspect(database)
    assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    with database.begin() as conn:
        assert (
            compare_metadata(
                MigrationContext.configure(conn, opts={"compare_server_default": True}),
                Base.metadata,
            )
            == []
        )
        conn.execute(
            text(
                "INSERT INTO users (username,hashed_password,role) VALUES ('keeper','hash','admin')"
            )
        )
    migrate_database(database)
    with database.connect() as conn:
        assert conn.execute(text("SELECT username FROM users")).scalar_one() == "keeper"
    assert {
        tuple(item["constrained_columns"]) for item in inspector.get_foreign_keys("events")
    } >= {("extraction_id",), ("owner_id",), ("evidence_id",)}
    assert "ix_events_timestamp_utc" in {item["name"] for item in inspector.get_indexes("events")}


def test_baseline_is_frozen_against_future_application_models(database):
    future = Table("future_phase_only", Base.metadata, Column("id", Integer, primary_key=True))
    try:
        migrate_database(database)
        assert "future_phase_only" not in inspect(database).get_table_names()
    finally:
        Base.metadata.remove(future)


def test_existing_schema_requires_explicit_adoption_and_preserves_rows(database):
    Base.metadata.create_all(database)  # Fixture representing the old prototype.
    with database.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (username,hashed_password,role) VALUES ('keeper','hash','admin')"
            )
        )
    with pytest.raises(RuntimeError, match="Unversioned database"):
        migrate_database(database)
    assert "alembic_version" not in inspect(database).get_table_names()
    migrate_database(database, adopt_existing=True)
    require_current_schema(database)
    with database.connect() as conn:
        assert conn.execute(text("SELECT username,hashed_password FROM users")).one() == (
            "keeper",
            "hash",
        )


def test_incompatible_legacy_schema_is_not_stamped_or_rewritten(database):
    with database.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)"))
        conn.execute(text("INSERT INTO users (username) VALUES ('legacy')"))
    with pytest.raises(RuntimeError, match="schema differs"):
        migrate_database(database, adopt_existing=True)
    assert inspect(database).get_table_names() == ["users"]
    with database.connect() as conn:
        assert conn.execute(text("SELECT username FROM users")).scalar_one() == "legacy"


def test_unmigrated_schema_is_rejected_without_creating_tables(database):
    with pytest.raises(RuntimeError, match="app.cli migrate"):
        require_current_schema(database)
    assert inspect(database).get_table_names() == []


def test_offline_migration_sql_can_build_the_schema(database):
    config = migration_config()
    config.output_buffer = io.StringIO()
    config.attributes["skip_logging"] = True
    command.upgrade(config, "head", sql=True)
    script = config.output_buffer.getvalue()
    assert "CREATE TABLE events" in script
    assert "CURRENT_TIMESTAMP" in script
    with database.connect() as conn:
        conn.connection.driver_connection.executescript(script)
    require_current_schema(database)


def test_importing_api_does_not_create_schema(tmp_path):
    database = tmp_path / "import-only.sqlite"
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import create_app; create_app()"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not database.exists()


def test_migrate_operator_command_bootstraps_an_empty_database(tmp_path):
    database = tmp_path / "cli.sqlite"
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "migrate"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(f"sqlite:///{database}")
    try:
        require_current_schema(engine)
        assert "evidence" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
