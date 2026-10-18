import re
from pathlib import Path

from app.parsers.base import Parser, streaming_parser


class ParserRegistry:
    _parsers: list[type[Parser]] = []

    @classmethod
    def register(cls, parser: type[Parser]) -> type[Parser]:
        cls._parsers.append(parser)
        return parser

    @classmethod
    def detect(cls, filename: str, content_type: str, path: Path) -> Parser:
        parser, _, _ = cls.detect_with_confidence(filename, content_type, path)
        return parser

    @classmethod
    def detect_with_confidence(
        cls, filename: str, content_type: str, path: Path, *, options: dict | None = None
    ) -> tuple[Parser, float, list[str]]:
        for parser_cls in cls._parsers:
            if parser_cls.matches(filename, content_type, path):
                confidence = parser_cls.detection_confidence(filename, content_type, path)
                return parser_cls(options=options), confidence, [f"Matched {parser_cls.name}"]
        return GenericLogParser(options=options), 0.35, ["No specialised format matched"]

    @classmethod
    def capabilities(cls) -> list[dict]:
        return [
            {
                "name": parser_cls.name,
                "class_name": parser_cls.__name__,
                "source_type": parser_cls.source_type,
                "version": parser_cls.version,
                "formats": list(parser_cls.supported_types),
                "status": parser_cls.status,
            }
            for parser_cls in cls._parsers
        ]


class GenericLogParser(Parser):
    name = "generic_log"
    version = "1"
    source_type = "generic_log"
    supported_types = ("txt", "log", "unknown")
    status = "stable"

    @classmethod
    def matches(cls, filename: str, content_type: str, path: Path) -> bool:
        return True

    @streaming_parser
    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        from app.parsers.base import ParsedEvent

        with path.open(encoding="utf-8-sig", errors="replace") as source:
            for i, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                if i > 500:
                    self.warnings.append(
                        {"type": "record_limit", "message": "Only the first 500 lines were parsed."}
                    )
                    break
                offset = re.search(
                    r"(?i)(?:offset|slow|fast)[^\n-]*?(-?\d+)\s*(seconds?|minutes?)", line
                )
                if offset and not any(
                    isinstance(item, dict) and item.get("type") == "clock_offset_hint"
                    for item in self.warnings
                ):
                    self.warnings.append(
                        {
                            "type": "clock_offset_hint",
                            "line": i,
                            "value": offset.group(0).strip(),
                            "message": "A clock offset is stated in the source and needs investigator review.",
                        }
                    )
                yield ParsedEvent(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    source_type=self.source_type,
                    event_type="other",
                    action="log_line",
                    content=line.rstrip("\r\n")[:2000],
                    raw_ref=f"line:{i}",
                )


from app.parsers import concrete as _concrete  # noqa: E402,F401
