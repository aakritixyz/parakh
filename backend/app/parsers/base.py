import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil import parser as dt_parser  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class ParsedEvent(BaseModel):
    case_id: int
    evidence_id: int
    source_type: str
    event_type: str = "other"
    timestamp_utc: datetime | None = None
    original_timestamp: str | None = None
    timezone_offset: str | None = None
    direction: str = "unknown"
    from_party_text: str | None = None
    to_party_text: list[str] = Field(default_factory=list)
    actor_entities: list[str] = Field(default_factory=list)
    action: str = "observed"
    content: str = ""
    location: dict | None = None
    raw_ref: str = ""
    confidence: float = 1.0


class EventStream(Iterator[ParsedEvent]):
    """A lazy iterator with list-like compatibility for older parser callers."""

    def __init__(self, source: Iterator[ParsedEvent]) -> None:
        self._source = source
        self._cache: list[ParsedEvent] = []
        self._position = 0
        self._complete = False

    def __iter__(self):
        return self

    def __next__(self) -> ParsedEvent:
        if self._position < len(self._cache):
            item = self._cache[self._position]
            self._position += 1
            return item
        if self._complete:
            raise StopIteration
        try:
            item = next(self._source)
        except StopIteration:
            self._complete = True
            raise
        self._cache.append(item)
        self._position += 1
        return item

    def _materialize(self) -> None:
        while not self._complete:
            try:
                item = next(self._source)
            except StopIteration:
                self._complete = True
            else:
                self._cache.append(item)

    def __len__(self) -> int:
        self._materialize()
        return len(self._cache)

    def __getitem__(self, index):
        self._materialize()
        return self._cache[index]


def streaming_parser(function: Callable) -> Callable:
    def wrapper(*args, **kwargs) -> EventStream:
        return EventStream(function(*args, **kwargs))

    return wrapper


class Parser(ABC):
    source_type = "unknown"
    name = "parser"
    version = "1"
    supported_types: tuple[str, ...] = ()
    status = "stable"

    def __init__(self, *, options: dict | None = None) -> None:
        self.options = options or {}
        self.warnings: list[dict | str] = []

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return False

    def metadata(self, path: Path) -> dict:
        return {"parser": self.source_type, "size": path.stat().st_size}

    @abstractmethod
    def parse(self, path: Path, *, case_id: int, evidence_id: int) -> Iterator[ParsedEvent]:
        raise NotImplementedError

    @classmethod
    def detection_confidence(cls, filename: str, content_type: str, path: Path) -> float:
        return 0.8


def parse_datetime(
    value: str | None, *, default_timezone: str = "UTC", dayfirst: bool = True, fuzzy: bool = True
) -> datetime | None:
    if not value:
        return None
    try:
        parsed = dt_parser.parse(
            value,
            dayfirst=dayfirst and not bool(re.match(r"^\d{4}[-/.]", value)),
            fuzzy=fuzzy,
            tzinfos={"IST": ZoneInfo("Asia/Kolkata")},
        )
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    return parsed.astimezone(UTC)


def timezone_offset(
    value: str | None, *, default_timezone: str = "UTC", dayfirst: bool = True
) -> str | None:
    if not value:
        return None
    try:
        parsed = dt_parser.parse(
            value,
            dayfirst=dayfirst and not bool(re.match(r"^\d{4}[-/.]", value)),
            fuzzy=True,
            tzinfos={"IST": ZoneInfo("Asia/Kolkata")},
        )
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    offset = parsed.utcoffset()
    if offset is None:
        return None
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, remainder = divmod(abs(minutes), 60)
    return f"{sign}{hours:02d}:{remainder:02d}"
