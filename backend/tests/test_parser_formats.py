from datetime import UTC, datetime
from hashlib import sha256

import pytest

from app.core.config import Settings
from app.parsers.base import parse_datetime
from app.parsers.concrete import CsvParser, WhatsAppParser
from app.parsers.registry import ParserRegistry


@pytest.mark.parametrize(
    "header,hour",
    [
        ("12/09/2026, 09:10 - Riya: नमस्ते", 3),
        ("12/09/26, 9:10 AM - Riya: नमस्ते", 3),
        ("[12/09/26, 9:10:00 AM] Riya: नमस्ते", 3),
        ("[12/09/2026, 21:10:00] Riya: नमस्ते", 15),
        ("12-09-2026, 9:10 pm - Riya: नमस्ते", 15),
        ("12.09.2026, 09:10 – Riya: नमस्ते", 3),
        ("\ufeff\u200e[12/09/26, 9:10\u202fAM] Riya: नमस्ते", 3),
        ("12/09/2026, 12:10 AM - Riya: नमस्ते", 18),
    ],
)
def test_whatsapp_formats_have_explicit_indian_timezone(tmp_path, monkeypatch, header, hour):
    monkeypatch.setattr("app.parsers.concrete.get_settings", lambda: Settings(_env_file=None))
    path = tmp_path / "_chat.txt"
    path.write_text(header, encoding="utf-8")
    before = sha256(path.read_bytes()).digest()
    parser = ParserRegistry.detect(path.name, "text/plain", path)
    assert isinstance(parser, WhatsAppParser)
    (event,) = parser.parse(path, case_id=1, evidence_id=2)
    expected = datetime(2026, 9, 11 if "12:10 AM" in header else 12, hour, 40, tzinfo=UTC)
    assert event.timestamp_utc == expected
    assert event.actor_entities == ["Riya"]
    assert event.content == "नमस्ते"
    assert event.raw_ref == "line:1"
    assert sha256(path.read_bytes()).digest() == before


def test_whatsapp_date_order_and_timezone_are_configurable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.parsers.concrete.get_settings",
        lambda: Settings(_env_file=None, whatsapp_day_first=False, whatsapp_timezone="UTC"),
    )
    path = tmp_path / "whatsapp.txt"
    path.write_text("9/12/26, 9:10 AM - Riya: hello")
    (event,) = WhatsAppParser().parse(path, case_id=1, evidence_id=2)
    assert event.timestamp_utc == datetime(2026, 9, 12, 9, 10, tzinfo=UTC)
    assert event.original_timestamp == "9/12/26, 9:10 AM"


def test_multiline_and_system_messages_preserve_content_and_raw_lines(tmp_path):
    path = tmp_path / "whatsapp.txt"
    path.write_text(
        "[12/09/26, 9:10 AM] Riya: first\n\nsecond: with colon\n[12/09/26, 9:11 AM] Messages are encrypted\n[12/09/26, 9:12 AM] Arjun: <Media omitted>"
    )
    events = WhatsAppParser().parse(path, case_id=1, evidence_id=2)
    assert [event.raw_ref for event in events] == ["line:1", "line:4", "line:5"]
    assert events[0].content == "first\n\nsecond: with colon"
    assert events[1].action == "system_message"
    assert events[1].actor_entities == []
    assert events[2].action == "media_omitted"


def test_generic_text_is_not_mistaken_for_whatsapp(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Discuss WhatsApp UPI transfers tomorrow")
    assert not WhatsAppParser.matches(path.name, "text/plain", path)


@pytest.mark.parametrize("value", ["2026-09-12T09:10:00+05:30", "2026-09-12 09:10 IST"])
def test_iso_dates_and_explicit_ist_are_not_silently_reinterpreted(value):
    assert parse_datetime(value) == datetime(2026, 9, 12, 3, 40, tzinfo=UTC)


@pytest.mark.parametrize(
    "header,row,source",
    [
        ("date,amount,utr,vpa", "2026-09-12,25000,UTR1,arjun@upi", "bank_upi_statement"),
        (" Date , AMOUNT , ACCOUNT ", "2026-09-12,25000,victim", "bank_upi_statement"),
        (
            "timestamp,phone,direction,duration_sec",
            "2026-09-12,+919876543210,incoming,182",
            "cdr_ipdr",
        ),
        ("timestamp,caller,called,cell_id,amount", "2026-09-12,111,222,42,0.50", "cdr_ipdr"),
        ("date,account,name", "2026-09-12,support,Riya", "csv_records"),
        ("description,note", "UPI account,arjun@upi", "csv_records"),
        ("date,amount,description", "2026-09-12,2,apples", "csv_records"),
        ("date,upi,note", "2026-09-12,arjun@upi,contact", "csv_records"),
    ],
)
def test_csv_classification_uses_multiple_schema_markers(tmp_path, header, row, source):
    path = tmp_path / "records.csv"
    path.write_text("\ufeff" + header + "\n" + row + "\n", encoding="utf-8")
    (event,) = CsvParser().parse(path, case_id=1, evidence_id=2)
    assert event.source_type == source
    assert event.raw_ref == "row:2"
    if source == "bank_upi_statement":
        assert event.timestamp_utc == datetime(2026, 9, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "content,message", [("Date,date\na,b\n", "duplicate"), ("date,name\na,b,c\n", "more fields")]
)
def test_ambiguous_csv_columns_fail_explicitly(tmp_path, content, message):
    path = tmp_path / "records.csv"
    path.write_text(content)
    with pytest.raises(ValueError, match=message):
        CsvParser().parse(path, case_id=1, evidence_id=2)


def test_invalid_timezone_setting_fails_before_ingestion():
    with pytest.raises(ValueError, match="IANA time zone"):
        Settings(_env_file=None, whatsapp_timezone="not/a-timezone")
