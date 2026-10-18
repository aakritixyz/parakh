import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.database import get_db
from app.core.migrations import migrate_database
from app.core.security import verify_password
from app.models.evidence import Event
from app.models.user import User
from app.services.audit_service import AuditService
from scripts import seed_demo


@pytest.fixture()
def bootstrap(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.sqlite'}")
    migrate_database(engine)
    sessions = sessionmaker(bind=engine)
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "whatsapp.txt").write_text("12/09/2026, 09:10 - Riya: hello")
    settings = Settings(
        _env_file=None,
        storage_root=tmp_path / "vault",
        demo_admin_username="custom-officer",
        demo_admin_password="configured-local-password",
    )
    monkeypatch.setattr(seed_demo, "engine", engine)
    monkeypatch.setattr(seed_demo, "SessionLocal", sessions)
    monkeypatch.setattr(seed_demo, "DATA", raw)
    monkeypatch.setattr(seed_demo, "get_settings", lambda: settings)
    monkeypatch.setattr("app.parsers.concrete.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.content_addressed.get_settings", lambda: settings)
    yield engine, sessions, settings
    engine.dispose()


def test_fresh_migration_seed_login_and_api_lifespan(bootstrap, monkeypatch):
    engine, sessions, settings = bootstrap
    case_id = asyncio.run(seed_demo.seed())
    with sessions() as db:
        user = db.scalar(select(User))
        assert user.username == "custom-officer"
        assert user.hashed_password != settings.demo_admin_password
        assert verify_password(settings.demo_admin_password, user.hashed_password)
        assert db.scalar(select(Event)).timestamp_utc.isoformat() == "2026-09-12T03:40:00+00:00"
        assert AuditService(db).verify_chain()["valid"]

    import app.main as main

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    app = main.create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        assert client.get("/readyz").status_code == 200
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": settings.demo_admin_username,
                "password": settings.demo_admin_password,
            },
        )
        assert response.status_code == 200
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        response = client.get(f"/api/v1/cases/{case_id}/dashboard", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["summary"]["event_count"] == 1
        from datetime import UTC, datetime

        timestamp = response.json()["timeline"][0]["timestamp_utc"]
        assert datetime.fromisoformat(timestamp.replace("Z", "+00:00")) == datetime(
            2026, 9, 12, 3, 40, tzinfo=UTC
        )
        assert (
            client.post(
                "/api/v1/auth/token",
                data={"username": settings.demo_admin_username, "password": "incorrect"},
            ).status_code
            == 401
        )


@pytest.mark.parametrize(
    "env,password",
    [("dev", None), ("production", None), ("production", "admin123"), ("production", "changeme")],
)
def test_demo_seed_rejects_missing_or_production_default_password(bootstrap, env, password):
    _, sessions, settings = bootstrap
    settings.env = env
    settings.demo_admin_password = password
    with pytest.raises(RuntimeError):
        asyncio.run(seed_demo.seed())
    with sessions() as db:
        assert db.scalar(select(User)) is None


def test_seeding_does_not_reset_an_existing_accounts_password(bootstrap):
    _, sessions, settings = bootstrap
    asyncio.run(seed_demo.seed())
    with sessions() as db:
        before = db.scalar(select(User)).hashed_password
    settings.demo_admin_password = "a-different-configured-password"
    with pytest.raises(RuntimeError, match="never resets"):
        asyncio.run(seed_demo.seed())
    with sessions() as db:
        assert db.scalar(select(User)).hashed_password == before


def test_api_startup_rejects_unmigrated_database(tmp_path, monkeypatch):
    import app.main as main

    engine = create_engine(f"sqlite:///{tmp_path / 'unmigrated.sqlite'}")
    monkeypatch.setattr(main, "engine", engine)
    try:
        with pytest.raises(RuntimeError, match="app.cli migrate"), TestClient(main.create_app()):
            pass
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_unreadable_demo_pdf_is_preserved_and_flagged_without_fabricated_events(
    bootstrap, tmp_path
):
    from hashlib import sha256

    from app.models.evidence import Evidence
    from app.models.investigation import Extraction
    from app.services.authenticity_service import AuthenticityService
    from app.services.evidence_service import EvidenceService

    _, sessions, _ = bootstrap
    sample = seed_demo.DATA / "damaged.pdf"
    sample.write_bytes(b"%PDF-1.4\n%%EOF\n% suspicious incremental marker\n%%EOF")
    original = sample.read_bytes()
    case_id = asyncio.run(seed_demo.seed())
    with sessions() as db:
        evidence = db.scalar(select(Evidence).where(Evidence.filename == "damaged.pdf"))
        extraction = db.scalar(select(Extraction).where(Extraction.evidence_id == evidence.id))
        assert evidence.case_id == case_id
        assert evidence.sha256 == sha256(original).hexdigest()
        assert "pdf_unreadable" in evidence.metadata_json["warnings"]
        assert extraction.parse_status == "needs_review"
        assert not evidence.events
        assert "pdf_unreadable" in {
            finding.signal for finding in AuthenticityService(db).report(evidence).findings
        }
        result = EvidenceService(db).reparse(evidence.id)
        assert result["inserted"] == 0
        assert extraction.parse_status == "needs_review"
        assert sample.read_bytes() == original


def test_password_hashes_preserve_bcrypt_compatibility_and_reject_byte_truncation():
    import bcrypt

    from app.core.security import hash_password
    from app.schemas.core import UserCreate

    old_hash = bcrypt.hashpw(b"legacy-test-password", bcrypt.gensalt(prefix=b"2a")).decode()
    assert verify_password("legacy-test-password", old_hash)
    assert not verify_password("incorrect", old_hash)
    password = "é" * 36
    current = hash_password(password)
    assert verify_password(password, current)
    assert not verify_password(password + "x", current)
    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password(password + "x")
    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        UserCreate(username="tester", password=password + "x")


def test_operator_creates_investigator_with_hashed_password(bootstrap, monkeypatch):
    from argparse import Namespace

    from app import cli

    engine, sessions, settings = bootstrap
    monkeypatch.setattr(cli, "engine", engine)
    monkeypatch.setattr(cli, "SessionLocal", sessions)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    args = Namespace(username="demo-investigator", password="synthetic-test-password")
    cli.create_investigator(args)
    with sessions() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        assert user.role == "investigator"
        assert user.hashed_password != args.password
        assert verify_password(args.password, user.hashed_password)
    with pytest.raises(SystemExit, match="User already exists"):
        cli.create_investigator(args)
