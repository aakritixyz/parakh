from pathlib import Path

from app.parsers.base import Parser


class ParserRegistry:
    _parsers: list[type[Parser]] = []

    @classmethod
    def register(cls, parser: type[Parser]) -> type[Parser]:
        cls._parsers.append(parser)
        return parser

    @classmethod
    def detect(cls, filename: str, content_type: str, path: Path) -> Parser:
        for parser_cls in cls._parsers:
            if parser_cls.matches(filename, content_type, path):
                return parser_cls()
        return GenericLogParser()

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

    def parse(self, path: Path, *, case_id: int, evidence_id: int):
        from app.parsers.base import ParsedEvent

        text = path.read_text(errors="ignore")
        return [
            ParsedEvent(
                case_id=case_id,
                evidence_id=evidence_id,
                source_type=self.source_type,
                action="log_line",
                content=line[:2000],
                raw_ref=f"line:{i}",
            )
            for i, line in enumerate(text.splitlines()[:500], start=1)
            if line.strip()
        ]


from app.parsers import concrete as _concrete  # noqa: E402,F401
