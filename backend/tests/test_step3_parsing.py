import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.models.case import Case
from app.models.evidence import DocumentExtraction, Event, Evidence
from app.models.user import User
from app.parsers.concrete import WhatsAppParser
from app.parsers.registry import ParserRegistry
from app.services.document_extraction_service import DocumentExtractionService
from app.services.evidence_service import EvidenceService

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"


def test_all_riya_parser_counts_match_the_answer_key():
    expected = json.loads((ROOT / "docs/demo/riya/validation.json").read_text())[
        "parser_smoke_check"
    ]
    total = 0
    for filename, answer in expected.items():
        path = EVIDENCE / filename
        parser, confidence, reasons = ParserRegistry.detect_with_confidence(
            filename, "application/octet-stream", path
        )
        events = list(parser.parse(path, case_id=1, evidence_id=1))
        assert parser.name == answer["parser"]
        assert len(events) == answer["records"]
        assert 0 < confidence <= 1 and reasons
        total += len(events)
    assert total == 108


def test_whatsapp_supports_multiline_hinglish_devanagari_and_date_decision(tmp_path):
    path = tmp_path / "whatsapp.txt"
    path.write_text(
        "09/12/2026, 09:10 - Riya: paise wapas bhejo\n"
        "यह दूसरी पंक्ति है\n"
        "09/12/2026, 09:11 - Messages are encrypted"
    )
    day_parser = WhatsAppParser(options={"date_order": "day_first"})
    month_parser = WhatsAppParser(options={"date_order": "month_first"})
    day_events = list(day_parser.parse(path, case_id=1, evidence_id=1))
    month_events = list(month_parser.parse(path, case_id=1, evidence_id=1))
    assert "paise wapas" in day_events[0].content
    assert "यह दूसरी पंक्ति है" in day_events[0].content
    assert day_events[1].action == "system_message"
    assert day_events[0].timestamp_utc != month_events[0].timestamp_utc
    assert any(item["type"] == "ambiguous_date" for item in day_parser.warnings)
    assert day_events[0].timezone_offset == "+05:30"


def test_reparse_replaces_events_without_duplicates_and_changes_timestamp(db, tmp_path):
    user = User(username="step3", role="investigator", hashed_password="test")
    db.add(user)
    db.flush()
    case = Case(title="Synthetic date decision", created_by=user.id)
    db.add(case)
    db.flush()
    source = tmp_path / "whatsapp.txt"
    source.write_text("09/12/2026, 09:10 - Riya: paise wapas")
    evidence = Evidence(
        case_id=case.id,
        filename=source.name,
        content_type="text/plain",
        mime="text/plain",
        source_type="whatsapp",
        sha256="a" * 64,
        md5="b" * 32,
        size_bytes=source.stat().st_size,
        storage_path=str(source),
        storage_key="a" * 64,
        metadata_json={"parser_options": {"date_order": "day_first"}},
    )
    db.add(evidence)
    db.flush()
    service = EvidenceService(db)
    first = service.reparse(evidence.id, "step3")
    first_time = db.scalar(select(Event.timestamp_utc).where(Event.evidence_id == evidence.id))
    evidence.metadata_json = {"parser_options": {"date_order": "month_first"}}
    second = service.reparse(evidence.id, "step3")
    second_time = db.scalar(select(Event.timestamp_utc).where(Event.evidence_id == evidence.id))
    assert first["inserted"] == second["inserted"] == 1
    assert second["deleted"] == 1
    assert db.scalar(select(func.count(Event.id)).where(Event.evidence_id == evidence.id)) == 1
    assert first_time != second_time


def test_false_refund_receipt_fields_have_confidence_and_source_regions(db):
    user = User(username="receipt", role="investigator", hashed_password="test")
    db.add(user)
    db.flush()
    case = Case(title="Synthetic receipt", created_by=user.id)
    db.add(case)
    db.flush()
    path = EVIDENCE / "06_refund_receipt_claim.pdf"
    evidence = Evidence(
        case_id=case.id,
        filename=path.name,
        content_type="application/pdf",
        mime="application/pdf",
        source_type="receipt",
        sha256="c" * 64,
        md5="d" * 32,
        size_bytes=path.stat().st_size,
        storage_path=str(path),
        storage_key="c" * 64,
    )
    db.add(evidence)
    db.flush()
    extraction, warnings = DocumentExtractionService(db).extract(evidence)
    assert extraction is not None and warnings == []
    assert extraction.engine == "embedded_pdf_text"
    assert extraction.fields["amount"]["value"] == "50,000.00"
    assert extraction.fields["time"]["value"].startswith("09:42")
    assert extraction.fields["payee"]["value"].startswith("Riya")
    assert extraction.fields["utr"]["value"] == "DEMO-UPI-001"
    assert all(field["confidence"] > 0 for field in extraction.fields.values())
    assert all("page" in field["receipt"] for field in extraction.fields.values())
    assert db.scalar(
        select(DocumentExtraction).where(DocumentExtraction.evidence_id == evidence.id)
    )


def test_normalized_event_masks_aadhaar_like_text_but_original_is_unchanged(db, tmp_path):
    user = User(username="mask", role="investigator", hashed_password="test")
    db.add(user)
    db.flush()
    case = Case(title="Synthetic masking", created_by=user.id)
    db.add(case)
    db.flush()
    path = tmp_path / "note.txt"
    original = "Reference 1234 5678 9012"
    path.write_text(original)
    evidence = Evidence(
        case_id=case.id,
        filename=path.name,
        content_type="text/plain",
        mime="text/plain",
        source_type="document",
        sha256="e" * 64,
        md5="f" * 32,
        size_bytes=path.stat().st_size,
        storage_path=str(path),
        storage_key="e" * 64,
        received_at=datetime.now(UTC),
    )
    db.add(evidence)
    db.flush()
    EvidenceService(db).reparse(evidence.id, "mask")
    event = db.scalar(select(Event).where(Event.evidence_id == evidence.id))
    assert event.content == "Reference XXXX XXXX 9012"
    assert path.read_text() == original
