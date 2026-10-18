import hashlib
import subprocess
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.services.audit_service import AuditService
from app.services.integrity_service import IntegrityService
from app.services.origin_service import OriginService, temporal_network
from app.services.report_service import ReportService


def _evidence(db, case_id: int, path: Path, name: str) -> Evidence:
    path.write_text(name)
    item = Evidence(
        case_id=case_id,
        filename=name,
        content_type="text/plain",
        mime="text/plain",
        source_type="whatsapp_chat",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        md5=hashlib.md5(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
        storage_path=str(path),
        storage_key=name,
    )
    db.add(item)
    db.flush()
    return item


def test_portable_integrity_verifier_and_exact_tamper_location(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    case = Case(title="Riya synthetic integrity case")
    db.add(case)
    db.flush()
    item = _evidence(db, case.id, tmp_path / "chat.txt", "chat.txt")
    entry = AuditService(db).log(
        action="evidence.sealed", case_id=case.id, target_type="evidence", target_id=str(item.id)
    )
    db.commit()

    clean = IntegrityService(db).status(case.id)
    assert clean["valid"] is True and clean["audit"]["signed_entries"] == 1
    assert (
        IntegrityService(db).tamper_demo(case.id, "file")["failed_at"]
        == f"evidence {item.id}: chat.txt"
    )
    assert (
        IntegrityService(db).tamper_demo(case.id, "audit")["failed_at"] == f"audit entry {entry.id}"
    )

    report = ReportService(db).export_case_bundle(case.id)
    db.commit()
    with zipfile.ZipFile(report.path) as bundle:
        verifier = tmp_path / "verify.py"
        verifier.write_bytes(bundle.read("verify.py"))
    checked = subprocess.run(
        [sys.executable, verifier, report.path], capture_output=True, text=True
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    Path(item.storage_path).write_bytes(b"Chat.txt")
    drift = IntegrityService(db).status(case.id)
    assert drift["valid"] is False and drift["files"][0]["status"] == "drift"


def test_clock_offset_alignment_provenance_and_impossible_sequence(db, tmp_path):
    case = Case(title="Riya synthetic clock case")
    db.add(case)
    db.flush()
    primary = _evidence(
        db, case.id, tmp_path / "whatsapp_riya_android.txt", "whatsapp_riya_android.txt"
    )
    secondary = _evidence(
        db,
        case.id,
        tmp_path / "whatsapp_second_device_tablet.txt",
        "whatsapp_second_device_tablet.txt",
    )
    base = datetime(2026, 9, 12, 4, tzinfo=UTC)
    for index, content in enumerate(["OTP bhejo", "double money", "refund sent"]):
        db.add(
            Event(
                case_id=case.id,
                evidence_id=primary.id,
                source_type="whatsapp_chat",
                event_type="message",
                timestamp_utc=base + timedelta(minutes=index),
                original_timestamp=f"09:3{index}",
                timezone_offset="+05:30",
                content=content,
                raw_ref=f"line:{index + 1}",
                parser_name="whatsapp",
                parser_version="2",
            )
        )
    for index, content in enumerate(["OTP bhejo", "refund sent"]):
        db.add(
            Event(
                case_id=case.id,
                evidence_id=secondary.id,
                source_type="whatsapp_chat",
                event_type="message",
                timestamp_utc=base + timedelta(minutes=index * 2) - timedelta(minutes=30),
                original_timestamp=f"09:0{index * 2}",
                timezone_offset="+05:30",
                content=content,
                raw_ref=f"line:{index + 1}",
                parser_name="whatsapp",
                parser_version="2",
            )
        )
    db.commit()

    result = OriginService(db).analyse(case.id)
    assert result["clock_reconciliation"]["correction_seconds"] == 1800
    assert result["second_device_comparison"]["missing"][0]["content"] == "double money"
    assert {item["file"] for item in result["provenance"]} == {
        "whatsapp_riya_android.txt",
        "whatsapp_second_device_tablet.txt",
    }
    assert temporal_network([("a", "b", -1), ("b", "a", -1)])["consistent"] is False
