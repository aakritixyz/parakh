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
from app.parsers.base import ParsedEvent, Parser, parse_datetime, streaming_parser, timezone_offset
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

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        settings = get_settings()
        selected_order = self.options.get("date_order")
        dayfirst = (
            settings.whatsapp_day_first
            if selected_order is None
            else selected_order != "month_first"
        )
        current: ParsedEvent | None = None
        with path.open(encoding="utf-8-sig", errors="replace") as source:
            for line_number, raw_line in enumerate(source, start=1):
                line = raw_line.rstrip("\r\n")
                header = self._header(line)
                if header is None:
                    if current is not None:
                        current.content += "\n" + line
                    elif line.strip():
                        self.warnings.append(
                            {
                                "type": "unparsed_line",
                                "line": line_number,
                                "message": "Text before the first WhatsApp header was not parsed.",
                            }
                        )
                    continue
                if current is not None:
                    yield current
                timestamp, body = header
                self._flag_ambiguous_date(timestamp, line_number)
                actor, separator, content = body.partition(":")
                is_message = bool(separator and actor.strip())
                content = content.strip() if is_message else body.strip()
                current = ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    event_type="message" if is_message else "other",
                    timestamp_utc=parse_datetime(
                        timestamp,
                        default_timezone=settings.whatsapp_timezone,
                        dayfirst=dayfirst,
                        fuzzy=False,
                    ),
                    original_timestamp=timestamp,
                    timezone_offset=timezone_offset(
                        timestamp,
                        default_timezone=settings.whatsapp_timezone,
                        dayfirst=dayfirst,
                    ),
                    direction="unknown",
                    from_party_text=actor.strip() if is_message else None,
                    actor_entities=[actor.strip()] if is_message else [],
                    action=("media_omitted" if _is_whatsapp_media_omitted(content) else "message")
                    if is_message
                    else "system_message",
                    content=content,
                    raw_ref=f"line:{line_number}",
                    confidence=0.95 if is_message else 0.85,
                )
        if current is not None:
            yield current

    def _flag_ambiguous_date(self, timestamp: str, line_number: int) -> None:
        match = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-]", timestamp)
        if not match:
            return
        first, second = (int(value) for value in match.groups())
        if (
            first <= 12
            and second <= 12
            and first != second
            and not any(
                isinstance(item, dict) and item.get("type") == "ambiguous_date"
                for item in self.warnings
            )
        ):
            self.warnings.append(
                {
                    "type": "ambiguous_date",
                    "line": line_number,
                    "value": timestamp,
                    "selected": self.options.get("date_order", "day_first"),
                    "message": "Numeric date can mean DD/MM or MM/DD. Investigator decision required.",
                }
            )


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

    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            fieldnames = {_csv_header(name) for name in (reader.fieldnames or [])}
            if len(fieldnames) != len(reader.fieldnames or []):
                raise ValueError("CSV has duplicate column names after normalization.")
            first_row = next(reader, None)
            if first_row is not None and None in first_row:
                raise ValueError("CSV row 2 has more fields than its header.")
        return self._parse_rows(path, case_id=case_id, evidence_id=evidence_id)

    @streaming_parser
    def _parse_rows(self, path: Path, *, case_id: int, evidence_id: int):
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
                recipient = lower.get("to") or lower.get("recipient") or lower.get("called")
                direction = lower.get("direction") or "unknown"
                yield ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=source_type,
                    event_type=_event_type_for_csv(source_type, action),
                    timestamp_utc=parse_datetime(ts),
                    original_timestamp=ts,
                    timezone_offset=timezone_offset(ts),
                    direction=direction.casefold() if direction else "unknown",
                    from_party_text=actor,
                    to_party_text=[recipient] if recipient else [],
                    actor_entities=[actor] if actor else [],
                    action=action,
                    content=json.dumps(row, ensure_ascii=False),
                    raw_ref=f"row:{i}",
                )


def _event_type_for_csv(source_type: str, action: str) -> str:
    if source_type == "bank_upi_statement":
        return "transaction"
    if source_type == "cdr_ipdr":
        return (
            "call"
            if "call" in action.casefold() or action.casefold() in {"in", "out"}
            else "telecom"
        )
    return "other"


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

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        with sqlite3.connect(path) as conn:
            tables = {
                row[0] for row in conn.execute("select name from sqlite_master where type='table'")
            }
            if "urls" in tables:
                columns = {row[1] for row in conn.execute("pragma table_info(urls)")}
                timestamp_column = "visit_time_utc" if "visit_time_utc" in columns else None
                query = (
                    "select url, title, visit_time_utc from urls limit 500"
                    if timestamp_column
                    else "select url, title, null from urls limit 500"
                )
                for i, (url, title, ts) in enumerate(conn.execute(query), start=1):
                    yield ParsedEvent(
                        case_id=case_id,
                        evidence_id=evidence_id,
                        source_type=self.source_type,
                        event_type="web_visit",
                        timestamp_utc=parse_datetime(str(ts)) if ts else None,
                        original_timestamp=str(ts) if ts else None,
                        timezone_offset=timezone_offset(str(ts)) if ts else None,
                        action="visited_url",
                        content=f"{title or ''} {url}",
                        raw_ref=f"urls:{i}",
                    )


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

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        messages: list[Message] | mailbox.mbox
        if path.name.lower().endswith(".mbox"):
            messages = list(mailbox.mbox(path))
        else:
            messages = [email.message_from_bytes(path.read_bytes())]
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
            sender = msg.get("From", "")
            recipients = [value.strip() for value in msg.get("To", "").split(",") if value.strip()]
            yield ParsedEvent(
                case_id=case_id,
                evidence_id=evidence_id,
                source_type=self.source_type,
                event_type="email",
                timestamp_utc=parse_datetime(msg.get("Date")),
                original_timestamp=msg.get("Date"),
                timezone_offset=timezone_offset(msg.get("Date")),
                direction="unknown",
                from_party_text=sender or None,
                to_party_text=recipients,
                actor_entities=[sender, *recipients],
                action="email",
                content=f"Subject: {msg.get('Subject', '')}\n{body[:2000]}",
                raw_ref=f"message:{i}",
            )


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

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        yield ParsedEvent(
            case_id=case_id,
            evidence_id=evidence_id,
            source_type=self.source_type,
            event_type="media",
            action="image_added",
            content=path.name,
        )


@ParserRegistry.register
class PdfParser(Parser):
    name = "pdf_document"
    version = "2"
    source_type = "pdf"
    supported_types = ("pdf",)
    status = "stable"

    def __init__(self, *, options: dict | None = None) -> None:
        super().__init__(options=options)

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

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        if PdfReader is None:
            self.warnings = ["pypdf_not_installed"]
            return
        try:
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
        except PDF_READ_ERRORS:
            self.warnings = ["pdf_unreadable"]
            return
        yield ParsedEvent(
            case_id=case_id,
            evidence_id=evidence_id,
            source_type=self.source_type,
            event_type="document",
            action="pdf_text",
            content=text[:5000],
            raw_ref="page:1",
        )


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

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        text = path.read_text(errors="ignore")
        if text.lstrip().startswith(("{", "[")):
            data = json.loads(text)
            rows = data.get("locations", data if isinstance(data, list) else [])
            for i, row in enumerate(rows[:500], start=1):
                lat = row.get("latitudeE7", 0) / 1e7 if "latitudeE7" in row else row.get("lat")
                lon = row.get("longitudeE7", 0) / 1e7 if "longitudeE7" in row else row.get("lon")
                ts = row.get("timestamp") or row.get("timestampMs")
                yield ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    event_type="location",
                    timestamp_utc=parse_datetime(str(ts)),
                    original_timestamp=str(ts),
                    timezone_offset=timezone_offset(str(ts)),
                    action="location",
                    location={"lat": lat, "lon": lon},
                    raw_ref=f"location:{i}",
                )
