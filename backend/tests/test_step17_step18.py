import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.models.ml import ModelRecord
from app.models.review import CaseReview
from app.services.event_search_service import EventSearchService, SearchError
from app.services.report_service import ReportService
from app.services.review_service import ReviewInput, select_exhibits, validate_review


def test_review_report_bundle_and_selection(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db.add(Case(id=1, title="Riya: investment scam complaint", case_number="SYN-001"))
    raw = b"Synthetic bank row: 25000 debit arjun@upi"
    source = tmp_path / "bank.csv"
    source.write_bytes(raw)
    evidence = Evidence(case_id=1, filename="bank.csv", sha256=hashlib.sha256(raw).hexdigest(),
                        md5=hashlib.md5(raw).hexdigest(), size_bytes=len(raw), storage_path=str(source), source_type="csv_records")
    db.add(evidence)
    db.flush()
    event = Event(case_id=1, evidence_id=evidence.id, source_type="csv_records", event_type="transaction",
                  content=raw.decode(), raw_ref="row:4")
    db.add(event)
    db.flush()
    payload = ReviewInput.model_validate({"revision": 0, "findings": [{"id": "F1", "statement": "The record shows a debit of INR 25000 involving arjun@upi.", "status": "established", "citations": [{"evidence_id": evidence.id, "event_id": event.id, "reference": "row:4"}]}], "exhibits": [{"id": "E1", "kind": "event", "evidence_id": evidence.id, "event_id": event.id, "reference": "row:4", "pages": 1}]})
    data = validate_review(db, 1, payload)
    db.add(CaseReview(case_id=1, revision=1, findings=data["findings"], exhibits=data["exhibits"]))
    db.add(ModelRecord(name="Synthetic baseline", version="1", licence="BSD-3-Clause", training_data="generated synthetic cases", known_limits=["Synthetic data only"], metrics={"precision": 0.8, "recall": 0.7}, artifact_path="local", artifact_sha256="a"*64, seed=17018))
    db.commit()
    plan = select_exhibits(data["findings"], data["exhibits"], 1)
    assert plan["complete"] and plan["selected_ids"] == ["E1"]
    assert select_exhibits(data["findings"], data["exhibits"], 1) == plan
    assert select_exhibits(data["findings"], [], 1)["status"] == "INFEASIBLE"
    report = ReportService(db).generate_case_report(1)
    text = "\n".join(page.extract_text() for page in PdfReader(report.path).pages)
    assert "arjun@upi" in text and "row:4" in text and "on synthetic data" in text
    assert "Synthetic baseline" in text and "verify with legal counsel" in text.lower()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "report.exported")).payload["sha256"] == report.sha256
    bundle = ReportService(db).export_case_bundle(1)
    with zipfile.ZipFile(bundle.path) as archive:
        assert {"README.md", "review.json", "verify.py", "events.csv"} <= set(archive.namelist())
        verifier = tmp_path / "verify.py"
        verifier.write_bytes(archive.read("verify.py"))
    result = subprocess.run([sys.executable, str(verifier), bundle.path], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    old = Path(report.path).read_bytes()
    another = ReportService(db).generate_case_report(1)
    assert another.path != report.path and Path(report.path).read_bytes() == old
    payload.findings[0].citations[0].evidence_id = 999
    with pytest.raises(ValueError, match="does not belong"):
        validate_review(db, 1, payload)


def test_regex_has_engine_timeout():
    with pytest.raises(SearchError, match="time limit"):
        EventSearchService._regex_matches(EventSearchService._safe_regex(r"(a|aa)+$"), "a" * 10000 + "!")


def test_security_headers_rate_and_body_limit():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.hardening import RequestHardening

    app = FastAPI()
    app.add_middleware(RequestHardening)

    @app.post("/api/auth/login")
    def login():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post("/api/auth/login")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        for _ in range(19):
            assert client.post("/api/auth/login").status_code == 200
        assert client.post("/api/auth/login").status_code == 429
        assert client.post("/api/auth/login", headers={"content-length": str(10**10)}).status_code == 413


def test_review_api_enforces_case_membership_and_read_only_role(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.api.v2.review import router
    from app.core.database import Base, get_db
    from app.core.deps import get_current_user
    from app.models.case import CaseMembership
    from app.models.user import User

    engine = create_engine(f"sqlite:///{tmp_path / 'access.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add_all([Case(id=1, title="Synthetic member case"), Case(id=2, title="Other synthetic case")])
    user = User(id=1, username="synthetic-prosecutor", hashed_password="unused", role="prosecutor")
    db.add(user)
    db.add(CaseMembership(case_id=1, user_id=1, role="prosecutor"))
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        assert client.get("/cases/1/review").status_code == 200
        assert client.get("/cases/2/review").status_code == 403
        assert client.put("/cases/1/review", json={"revision": 0, "findings": [], "exhibits": []}).status_code == 403
        user.role = "admin"
        saved = client.put("/cases/1/review", json={"revision": 0, "findings": [], "exhibits": []})
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        assert client.put("/cases/1/review", json={"revision": 0, "findings": [], "exhibits": []}).status_code == 409

    db.close()
    engine.dispose()
