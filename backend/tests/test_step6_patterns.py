from datetime import UTC, datetime, timedelta

from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.services.pattern_service import PatternService
from app.services.step6_model_service import train_hinglish_classifier


def _evidence(db, case_id: int) -> Evidence:
    item = Evidence(
        case_id=case_id,
        filename="communications.txt",
        content_type="text/plain",
        mime="text/plain",
        source_type="whatsapp",
        sha256="a" * 64,
        md5="b" * 32,
        size_bytes=100,
        storage_path="/vault/a",
        storage_key="a" * 64,
    )
    db.add(item)
    db.flush()
    return item


def _message(case_id: int, evidence_id: int, timestamp: datetime, content: str, index: int) -> Event:
    return Event(
        case_id=case_id,
        evidence_id=evidence_id,
        source_app="whatsapp",
        source_type="chat",
        event_type="message",
        action="message",
        timestamp_utc=timestamp,
        actor_entities=["Agent Arjun"],
        content=content,
        raw_ref=f"line:{index}",
        parser_name="test",
        parser_version="1",
    )


def test_planted_scam_phrase_and_late_night_burst_are_source_linked(db):
    case = Case(title="Synthetic Step 6")
    db.add(case)
    db.flush()
    evidence = _evidence(db, case.id)
    start = datetime(2026, 9, 8, 6, tzinfo=UTC)
    normal = [
        _message(case.id, evidence.id, start + timedelta(hours=index * 4), f"normal note {index}", index)
        for index in range(16)
    ]
    late_start = datetime(2026, 9, 12, 20, 30, tzinfo=UTC)  # 02:00 IST
    burst = [
        _message(
            case.id,
            evidence.id,
            late_start + timedelta(seconds=index * 45),
            "KYC update only, OTP bhejoo jaldi" if index == 0 else f"urgent template {index}",
            100 + index,
        )
        for index in range(8)
    ]
    db.add_all(normal + burst)
    db.flush()
    result = PatternService(db).analyse(case.id)
    assert any(flag["type"] == "scam_phrase" and flag["support"] for flag in result["flags"])
    late = next(flag for flag in result["flags"] if flag["type"] == "late_night_burst")
    assert late["test"]["p_value"] <= late["test"]["fdr_alpha"]
    assert all(item["file"] == "communications.txt" for item in late["support"])


def test_uniform_control_has_no_fdr_significant_burst_and_classifier_reports_metrics(db, tmp_path):
    case = Case(title="Synthetic shuffled control")
    db.add(case)
    db.flush()
    evidence = _evidence(db, case.id)
    start = datetime(2026, 9, 1, 5, tzinfo=UTC)
    db.add_all(
        [
            _message(case.id, evidence.id, start + timedelta(hours=index * 3), f"routine {index}", index)
            for index in range(24)
        ]
    )
    db.flush()
    result = PatternService(db).analyse(case.id)
    assert not any(flag["status"] == "significant anomaly" for flag in result["flags"])
    card = train_hinglish_classifier(tmp_path, seed=61026)
    assert card["metrics"]["label"] == "on synthetic data"
    assert card["metrics"]["precision"] > 0
    assert card["metrics"]["recall"] > 0
