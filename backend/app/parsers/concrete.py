import csv
import email
import json
import mailbox
import re
import sqlite3
from email.message import Message
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from pypdf import PdfReader as _PdfReader
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight environments
    PdfReader: Any | None = None
else:
    PdfReader = _PdfReader

from app.parsers.base import ParsedEvent, Parser, parse_datetime
from app.parsers.registry import ParserRegistry


@ParserRegistry.register
class WhatsAppParser(Parser):
    name = "whatsapp_text_export"
    version = "1"
    source_type = "whatsapp_chat"
    supported_types = ("txt",)
    status = "beta"
    message_patterns = (
        re.compile(
            r"^\[?(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]?\s+(?:-\s+)?([^:]+):\s?(.*)$"
        ),
        re.compile(
            r"^(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\s+-\s+([^:]+):\s?(.*)$"
        ),
    )
    system_patterns = (
        re.compile(
            r"^\[?(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]?\s+(?:-\s+)?(.*)$"
        ),
    )

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith(".txt") and "whatsapp" in filename.lower()

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        events: list[ParsedEvent] = []
        for i, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
            parsed = self._parse_line(line, case_id=case_id, evidence_id=evidence_id, line_number=i)
            if parsed:
                events.append(parsed)
            elif events and line.strip():
                events[-1].content = f"{events[-1].content}\n{line.rstrip()}".strip()
        return events

    def _parse_line(
        self, line: str, *, case_id: int, evidence_id: int, line_number: int
    ) -> ParsedEvent | None:
        for pattern in self.message_patterns:
            match = pattern.match(line)
            if match:
                ts, actor, body = match.groups()
                body = body.strip()
                return ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    timestamp_utc=parse_datetime(ts),
                    original_timestamp=ts,
                    actor_entities=[actor.strip()],
                    action="media_omitted" if _is_whatsapp_media_omitted(body) else "message",
                    content=body,
                    raw_ref=f"line:{line_number}",
                    confidence=0.95,
                )
        for pattern in self.system_patterns:
            match = pattern.match(line)
            if match:
                ts, body = match.groups()
                body = body.strip()
                return ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    timestamp_utc=parse_datetime(ts),
                    original_timestamp=ts,
                    actor_entities=[],
                    action="system_message",
                    content=body,
                    raw_ref=f"line:{line_number}",
                    confidence=0.85,
                )
        return None


def _is_whatsapp_media_omitted(value: str) -> bool:
    lowered = value.lower()
    return "<media omitted>" in lowered or "media omitted" in lowered or "image omitted" in lowered


@ParserRegistry.register
class CsvParser(Parser):
    name = "csv_records"
    version = "1"
    source_type = "csv_records"
    supported_types = ("csv",)
    status = "beta"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith(".csv")

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        events = []
        with path.open(newline="", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            fieldnames = {name.strip().lower() for name in (reader.fieldnames or [])}
            source_type = _csv_source_type(fieldnames)
            for i, row in enumerate(reader, start=2):
                lower = {k.lower(): v for k, v in row.items()}
                ts = lower.get("timestamp") or lower.get("date") or lower.get("time")
                actor = lower.get("from") or lower.get("sender") or lower.get("account") or lower.get("phone")
                action = lower.get("type") or lower.get("action") or lower.get("direction") or "record"
                events.append(
                    ParsedEvent(
                        case_id=case_id,
                        evidence_id=evidence_id,
                        source_type=source_type,
                        timestamp_utc=parse_datetime(ts),
                        original_timestamp=ts,
                        actor_entities=[actor] if actor else [],
                        action=action,
                        content=json.dumps(row, ensure_ascii=False),
                        raw_ref=f"row:{i}",
                    )
                )
        return events


def _csv_source_type(fieldnames: set[str]) -> str:
    financial_markers = {
        "amount",
        "balance",
        "debit",
        "credit",
        "utr",
        "reference",
        "upi",
        "vpa",
        "ifsc",
        "account",
        "transaction id",
        "txn id",
    }
    telecom_markers = {"imei", "imsi", "cell_id", "lac", "tower", "duration", "called", "caller"}
    if fieldnames & financial_markers:
        return "bank_upi_statement"
    if fieldnames & telecom_markers:
        return "cdr_ipdr"
    return "csv_records"


@ParserRegistry.register
class BrowserSQLiteParser(Parser):
    name = "browser_sqlite"
    version = "1"
    source_type = "browser_history"
    supported_types = ("sqlite", "db")
    status = "beta"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith((".sqlite", ".db"))

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        events = []
        with sqlite3.connect(path) as conn:
            tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
            if "urls" in tables:
                for i, (url, title) in enumerate(conn.execute("select url, title from urls limit 500"), start=1):
                    events.append(
                        ParsedEvent(
                            case_id=case_id,
                            evidence_id=evidence_id,
                            source_type=self.source_type,
                            action="visited_url",
                            content=f"{title or ''} {url}",
                            raw_ref=f"urls:{i}",
                        )
                    )
        return events


@ParserRegistry.register
class EmailParser(Parser):
    name = "email_archive"
    version = "1"
    source_type = "email"
    supported_types = ("eml", "mbox")
    status = "beta"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith((".eml", ".mbox"))

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        messages: list[Message] = []
        if path.name.lower().endswith(".mbox"):
            messages = list(mailbox.mbox(path))
        else:
            messages = [email.message_from_bytes(path.read_bytes())]
        events = []
        for i, msg in enumerate(messages, start=1):
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        part_payload = part.get_payload(decode=True)
                        body += (
                            part_payload.decode(errors="ignore")
                            if isinstance(part_payload, bytes)
                            else str(part.get_payload())
                        )
            else:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    body = payload.decode(errors="ignore")
                else:
                    body = str(msg.get_payload())
            events.append(
                ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    timestamp_utc=parse_datetime(msg.get("Date")),
                    original_timestamp=msg.get("Date"),
                    actor_entities=[msg.get("From", ""), msg.get("To", "")],
                    action="email",
                    content=f"Subject: {msg.get('Subject', '')}\n{body[:2000]}",
                    raw_ref=f"message:{i}",
                )
            )
        return events


@ParserRegistry.register
class ImageParser(Parser):
    name = "image_metadata"
    version = "1"
    source_type = "image"
    supported_types = ("jpg", "jpeg", "png")
    status = "stable"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return content_type.startswith("image/") or filename.lower().endswith((".jpg", ".jpeg", ".png"))

    def metadata(self, path: Path) -> dict:
        with Image.open(path) as img:
            return {"parser": self.source_type, "format": img.format, "size": img.size, "exif_keys": list((img.getexif() or {}).keys())}

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        return [ParsedEvent(case_id=case_id, evidence_id=evidence_id, source_type=self.source_type, action="image_added", content=path.name)]


@ParserRegistry.register
class PdfParser(Parser):
    name = "pdf_document"
    version = "1"
    source_type = "pdf"
    supported_types = ("pdf",)
    status = "stable"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith(".pdf") or content_type == "application/pdf"

    def metadata(self, path: Path) -> dict:
        if PdfReader is None:
            return {"parser": self.source_type, "pages": None, "metadata": {}, "warning": "pypdf_not_installed"}
        reader = PdfReader(str(path))
        return {"parser": self.source_type, "pages": len(reader.pages), "metadata": {k: str(v) for k, v in (reader.metadata or {}).items()}}

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        if PdfReader is None:
            return [ParsedEvent(case_id=case_id, evidence_id=evidence_id, source_type=self.source_type, action="pdf_added", content="PDF parser fallback: install pypdf for text extraction.")]
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
        return [ParsedEvent(case_id=case_id, evidence_id=evidence_id, source_type=self.source_type, action="pdf_text", content=text[:5000])]


@ParserRegistry.register
class GpsParser(Parser):
    name = "gps_location"
    version = "1"
    source_type = "gps"
    supported_types = ("json", "gpx")
    status = "beta"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith((".gpx", ".json")) and any(x in filename.lower() for x in ["gps", "location", "takeout"])

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        text = path.read_text(errors="ignore")
        events = []
        if path.suffix.lower() == ".json":
            data = json.loads(text)
            rows = data.get("locations", data if isinstance(data, list) else [])
            for i, row in enumerate(rows[:500], start=1):
                lat = row.get("latitudeE7", 0) / 1e7 if "latitudeE7" in row else row.get("lat")
                lon = row.get("longitudeE7", 0) / 1e7 if "longitudeE7" in row else row.get("lon")
                ts = row.get("timestamp") or row.get("timestampMs")
                events.append(
                    ParsedEvent(
                        case_id=case_id,
                        evidence_id=evidence_id,
                        source_type=self.source_type,
                        timestamp_utc=parse_datetime(str(ts)),
                        original_timestamp=str(ts),
                        action="location",
                        location={"lat": lat, "lon": lon},
                        raw_ref=f"location:{i}",
                    )
                )
        return events
