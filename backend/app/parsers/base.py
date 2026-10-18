import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil import parser as dt_parser  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class ParsedEvent(BaseModel):
    case_id: int
    evidence_id: int
    source_type: str
    timestamp_utc: datetime | None = None
    original_timestamp: str | None = None
    actor_entities: list[str] = Field(default_factory=list)
    action: str = "observed"
    content: str = ""
    location: dict | None = None
    raw_ref: str = ""
    confidence: float = 1.0


class Parser(ABC):
    source_type = "unknown"
    name = "parser"
    version = "1"
    supported_types: tuple[str, ...] = ()
    status = "stable"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return False

    def metadata(self, path: Path) -> dict:
        return {"parser": self.source_type, "size": path.stat().st_size}

    @abstractmethod
    def parse(
        self, path: Path, *, case_id: int, evidence_id: int
    ) -> list[ParsedEvent] | Iterator[ParsedEvent]:
        raise NotImplementedError


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
