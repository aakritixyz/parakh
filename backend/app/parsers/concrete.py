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

PDF_READ_ERRORS: tuple[type[Exception], ...] = (ValueError,)
try:
    from pypdf import PdfReader as _PdfReader
    from pypdf.errors import PdfReadError as _PdfReadError
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight environments
    PdfReader: Any | None = None
else:
    PdfReader = _PdfReader
    PDF_READ_ERRORS = (ValueError, _PdfReadError)

from app.core.config import get_settings
from app.parsers.base import ParsedEvent, Parser, parse_datetime
from app.parsers.registry import ParserRegistry


@ParserRegistry.register
class WhatsAppParser(Parser):
    name = "whatsapp_text_export"
    version = "2"
    source_type = "whatsapp_chat"
    supported_types = ("txt",)
    status = "beta"
    # Android and iOS exports vary in delimiters, seconds, and 12/24-hour clocks.
    _date = r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    _clock = r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp]\.?[Mm]\.?)?"
    _timestamp = rf"{_date},?\s+{_clock}"
    header_patterns = (
        re.compile(rf"^\[({_timestamp})\]\s*(?:[-–—]\s+)?(.*)$"),
        re.compile(rf"^({_timestamp})\s+[-–—]\s+(.*)$"),
    )

    @classmethod
    def _header(cls, line: str) -> tuple[str, str] | None:
        # Export-added direction marks occur before the header, not in the
        # sender or message body. Never modify the underlying evidence file.
        line = line.lstrip("\ufeff\u200e\u200f ")
        for pattern in cls.header_patterns:
            match = pattern.match(line)
            if match:
                return match.group(1), match.group(2)
        return None

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        if not filename.lower().endswith(".txt"):
            return False
        if "whatsapp" in filename.lower():
            return True
        with path.open(encoding="utf-8-sig", errors="replace") as source:
            sample = source.read(65536)
        return any(cls._header(line) for line in sample.splitlines()[:20])

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        events: list[ParsedEvent] = []
        settings = get_settings()
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1
        ):
            header = self._header(line)
            if header is None:
                if events:
                    events[-1].content += "\n" + line
                continue
            timestamp, body = header
            actor, separator, content = body.partition(":")
            is_message = bool(separator and actor.strip())
            content = content.strip() if is_message else body.strip()
            events.append(
                ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    timestamp_utc=parse_datetime(
                        timestamp,
                        default_timezone=settings.whatsapp_timezone,
                        dayfirst=settings.whatsapp_day_first,
                        fuzzy=False,
                    ),
                    original_timestamp=timestamp,
                    actor_entities=[actor.strip()] if is_message else [],
                    action=("media_omitted" if _is_whatsapp_media_omitted(content) else "message")
                    if is_message
                    else "system_message",
                    content=content,
                    raw_ref=f"line:{line_number}",
                    confidence=0.95 if is_message else 0.85,
                )
            )
        return events


def _is_whatsapp_media_omitted(value: str) -> bool:
    lowered = value.lower()
    return "<media omitted>" in lowered or "media omitted" in lowered or "image omitted" in lowered


@ParserRegistry.register
class CsvParser(Parser):
    name = "csv_records"
    version = "2"
    source_type = "csv_records"
    supported_types = ("csv",)
    status = "beta"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith(".csv")

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        events = []
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            fieldnames = {_csv_header(name) for name in (reader.fieldnames or [])}
            if len(fieldnames) != len(reader.fieldnames or []):
                raise ValueError("CSV has duplicate column names after normalization.")
            source_type = _csv_source_type(fieldnames)
            for i, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(f"CSV row {i} has more fields than its header.")
                lower = {_csv_header(k): v for k, v in row.items()}
                ts = (
                    lower.get("timestamp")
                    or lower.get("date")
                    or lower.get("time")
                    or lower.get("transaction date")
                )
                actor = (
                    lower.get("from")
                    or lower.get("sender")
                    or lower.get("account")
                    or lower.get("phone")
                )
                action = (
                    lower.get("type") or lower.get("action") or lower.get("direction") or "record"
                )
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


def _csv_header(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", " ").split())


def _csv_source_type(fieldnames: set[str]) -> str:
    # Classify the schema, never cell values. A lone account, UPI, or amount
    # column is not sufficient evidence that a generic CSV is a bank export.
    amounts = {"amount", "debit", "credit", "withdrawal", "deposit", "transaction amount"}
    references = {"utr", "transaction id", "txn id", "reference", "reference number", "upi ref no"}
    accounts = {
        "account",
        "account number",
        "vpa",
        "upi",
        "upi id",
        "ifsc",
        "counterparty",
        "balance",
    }
    times = {"date", "time", "timestamp", "datetime", "transaction date"}
    network = {"imei", "imsi", "cell id", "lac", "tower", "source ip", "destination ip"}
    numbers = {
        "phone",
        "caller",
        "called",
        "calling number",
        "called number",
        "msisdn",
        "a party",
        "b party",
    }
    durations = {"duration", "duration sec", "duration seconds"}
    if (fieldnames & network and fieldnames & (numbers | times)) or (
        fieldnames & durations and fieldnames & numbers
    ):
        return "cdr_ipdr"
    if fieldnames & amounts and fieldnames & (references | accounts):
        return "bank_upi_statement"
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
            tables = {
                row[0] for row in conn.execute("select name from sqlite_master where type='table'")
            }
            if "urls" in tables:
                for i, (url, title) in enumerate(
                    conn.execute("select url, title from urls limit 500"), start=1
                ):
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
        return content_type.startswith("image/") or filename.lower().endswith(
            (".jpg", ".jpeg", ".png")
        )

    def metadata(self, path: Path) -> dict:
        with Image.open(path) as img:
            return {
                "parser": self.source_type,
                "format": img.format,
                "size": img.size,
                "exif_keys": list((img.getexif() or {}).keys()),
            }

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        return [
            ParsedEvent(
                case_id=case_id,
                evidence_id=evidence_id,
                source_type=self.source_type,
                action="image_added",
                content=path.name,
            )
        ]


@ParserRegistry.register
class PdfParser(Parser):
    name = "pdf_document"
    version = "2"
    source_type = "pdf"
    supported_types = ("pdf",)
    status = "stable"

    def __init__(self) -> None:
        self.warnings: list[str] = []

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith(".pdf") or content_type == "application/pdf"

    def metadata(self, path: Path) -> dict:
        if PdfReader is None:
            self.warnings = ["pypdf_not_installed"]
        else:
            try:
                reader = PdfReader(str(path))
                return {
                    "parser": self.source_type,
                    "pages": len(reader.pages),
                    "metadata": {k: str(v) for k, v in (reader.metadata or {}).items()},
                }
            except PDF_READ_ERRORS:
                self.warnings = ["pdf_unreadable"]
        return {
            "parser": self.source_type,
            "pages": None,
            "metadata": {},
            "warnings": self.warnings,
        }

    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> list[ParsedEvent]:
        if PdfReader is None:
            self.warnings = ["pypdf_not_installed"]
            return []
        try:
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
        except PDF_READ_ERRORS:
            self.warnings = ["pdf_unreadable"]
            return []
        return [
            ParsedEvent(
                case_id=case_id,
                evidence_id=evidence_id,
                source_type=self.source_type,
                action="pdf_text",
                content=text[:5000],
            )
        ]


@ParserRegistry.register
class GpsParser(Parser):
    name = "gps_location"
    version = "1"
    source_type = "gps"
    supported_types = ("json", "gpx")
    status = "beta"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return filename.lower().endswith((".gpx", ".json")) and any(
            x in filename.lower() for x in ["gps", "location", "takeout"]
        )

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
