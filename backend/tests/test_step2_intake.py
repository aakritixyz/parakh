import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.database import get_db
from app.core.migrations import migrate_database
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.case import Case, CaseMembership
from app.models.evidence import Evidence
from app.models.investigation import Job, Owner
from app.models.user import User

PASSWORD = "synthetic-step2-password"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'step2.sqlite'}", connect_args={"check_same_thread": False}
    )
    migrate_database(engine)
    sessions = sessionmaker(bind=engine)
    settings = Settings(
        _env_file=None,
        secret_key="synthetic-step2-secret",
        storage_root=tmp_path / "vault",
        max_zip_uncompressed_bytes=10_000_000,
        max_zip_ratio=20,
    )
    import app.api.v2.auth as auth
    import app.api.v2.intake as intake
    import app.core.security as security
    import app.main as main
    import app.services.evidence_service as evidence_service
    import app.services.intake_worker as worker
    import app.storage.content_addressed as storage

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(intake, "get_settings", lambda: settings)
    monkeypatch.setattr(evidence_service, "get_settings", lambda: settings)
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    with sessions() as db:
        user = User(
            username="demo-investigator",
            role="investigator",
            hashed_password=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        case = Case(
            title="Riya: investment scam complaint",
            description="Synthetic only",
            created_by=user.id,
            lead_investigator_id=user.id,
        )
        db.add(case)
        db.flush()
        db.add(
            CaseMembership(
                case_id=case.id, user_id=user.id, role="investigator", granted_by=user.id
            )
        )
        db.commit()
        case_id = case.id
    app = main.create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        login = client.post(
            "/api/v2/auth/login",
            data={"username": "demo-investigator", "password": PASSWORD},
        )
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        yield client, sessions, headers, case_id, settings
    engine.dispose()


def owner(client, headers, case_id):
    result = client.post(
        f"/api/v2/cases/{case_id}/owners",
        headers=headers,
        json={"display_name": "Riya", "notes": "Synthetic owner"},
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


def upload(client, headers, case_id, owner_id, name, data, key):
    return client.post(
        f"/api/v2/cases/{case_id}/intake",
        headers={**headers, "Idempotency-Key": key},
        files={"file": (name, data, "application/octet-stream")},
        data={
            "source_type": "document",
            "owner_id": str(owner_id),
            "handed_over_by": "Riya",
            "acquired_at": datetime(2026, 10, 18, 10, 0, tzinfo=UTC).isoformat(),
            "acquisition_method": "Logical export supplied by owner",
            "note": "Synthetic evidence pack",
        },
    )


def test_done_when_all_15_files_seal_dedupe_and_one_file_tamper_isolated(api):
    client, sessions, headers, case_id, _ = api
    owner_id = owner(client, headers, case_id)
    evidence_dir = Path(__file__).resolve().parents[2] / "evidence"
    files = sorted(evidence_dir.iterdir())
    assert len(files) == 15
    for index, path in enumerate(files):
        response = upload(
            client, headers, case_id, owner_id, path.name, path.read_bytes(), f"riya-{index}"
        )
        assert response.status_code == 202, response.text
        item = response.json()["items"][0]
        assert item["sha256"] and item["md5"] and item["job"]["stage"] == "Stored"
    with sessions() as db:
        assert db.scalar(select(func.count(Evidence.id)).where(Evidence.case_id == case_id)) == 15
        assert db.scalar(select(func.count(Job.id)).where(Job.case_id == case_id)) == 15
        assert set(db.scalars(select(Job.status).where(Job.case_id == case_id))) == {"completed"}
        assert db.scalar(select(Owner).where(Owner.display_name == "Riya"))
        sealed = list(db.scalars(select(Evidence).where(Evidence.case_id == case_id)))
        assert all(Path(item.storage_path).stat().st_mode & 0o222 == 0 for item in sealed)
        assert all(item.owner_id == owner_id and item.acquisition_note for item in sealed)
        assert len({item.sha256 for item in sealed}) == 15
        assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "evidence.sealed")) == 15
        target, untouched = sealed[0], sealed[1]
        target_path = Path(target.storage_path)
        original = target_path.read_bytes()
        target_path.chmod(0o644)
        target_path.write_bytes(b"X" + original[1:])
        target_id, untouched_id = target.id, untouched.id
    duplicate = upload(
        client, headers, case_id, owner_id, files[1].name, files[1].read_bytes(), "new-key"
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["items"][0]["duplicate"] is True
    with sessions() as db:
        assert db.scalar(select(func.count(Evidence.id)).where(Evidence.case_id == case_id)) == 15
    assert client.get(f"/api/v1/evidence/{target_id}/integrity", headers=headers).json()["valid"] is False
    assert client.get(f"/api/v1/evidence/{untouched_id}/integrity", headers=headers).json()["valid"] is True


def test_safe_zip_registers_hashed_children_and_blocks_traversal_and_bomb(api):
    client, sessions, headers, case_id, _ = api
    owner_id = owner(client, headers, case_id)
    safe = io.BytesIO()
    with zipfile.ZipFile(safe, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("folder/chat.txt", "synthetic chat")
        archive.writestr("bank.csv", "date,amount\n2026-01-01,25000")
    response = upload(client, headers, case_id, owner_id, "pack.zip", safe.getvalue(), "safe-zip")
    assert response.status_code == 202, response.text
    assert len(response.json()["items"]) == 3
    with sessions() as db:
        parent = db.scalar(select(Evidence).where(Evidence.filename == "pack.zip"))
        children = list(db.scalars(select(Evidence).where(Evidence.parent_evidence_id == parent.id)))
        assert {child.archive_path for child in children} == {"folder/chat.txt", "bank.csv"}
        assert all(child.sha256 and child.md5 for child in children)

    unsafe = io.BytesIO()
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape.txt", "blocked")
    rejected = upload(client, headers, case_id, owner_id, "unsafe.zip", unsafe.getvalue(), "bad-zip")
    assert rejected.status_code == 422
    assert "unsafe member path" in rejected.text

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("huge.txt", "A" * 100_000)
    rejected = upload(client, headers, case_id, owner_id, "bomb.zip", bomb.getvalue(), "bomb-zip")
    assert rejected.status_code == 422
    assert "compression ratio" in rejected.text


def test_magic_bytes_warning_and_cancel_retry_controls(api):
    client, sessions, headers, case_id, _ = api
    owner_id = owner(client, headers, case_id)
    response = upload(client, headers, case_id, owner_id, "fake.pdf", b"plain text", "magic")
    assert response.status_code == 202
    assert "magic bytes" in response.json()["items"][0]["magic_byte_warning"]
    with sessions() as db:
        evidence = db.scalar(select(Evidence).where(Evidence.filename == "fake.pdf"))
        pending = Job(
            case_id=case_id,
            evidence_id=evidence.id,
            type="ingest_extraction",
            status="queued",
            stage="Stored",
            progress=35,
        )
        db.add(pending)
        db.commit()
        job_id = pending.id
    cancelled = client.post(
        f"/api/v2/cases/{case_id}/intake/jobs/{job_id}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    with sessions() as db:
        job = db.get(Job, job_id)
        job.status = "cancelled"
        job.stage = "Cancelled"
        db.commit()
    retried = client.post(
        f"/api/v2/cases/{case_id}/intake/jobs/{job_id}/retry", headers=headers
    )
    assert retried.status_code == 202
    with sessions() as db:
        latest = db.scalar(select(Job).where(Job.id != job_id).order_by(Job.id.desc()))
        assert latest.attempt == 2 and latest.status == "completed"
