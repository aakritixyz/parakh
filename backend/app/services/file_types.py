from pathlib import Path


def sniff_type(path: Path) -> str:
    with path.open("rb") as source:
        head = source.read(8192)
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "application/zip"
    if head.startswith(b"SQLite format 3\x00"):
        return "application/vnd.sqlite3"
    if head.startswith((b"\xff\xd8\xff",)):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    stripped = head.lstrip()
    if stripped.startswith((b"{", b"[")):
        return "application/json"
    if b"\x00" not in head:
        return "text/plain"
    return "application/octet-stream"


def extension_mismatch(filename: str, detected: str) -> str | None:
    expected = {
        ".pdf": "application/pdf",
        ".zip": "application/zip",
        ".sqlite": "application/vnd.sqlite3",
        ".db": "application/vnd.sqlite3",
        ".json": "application/json",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(Path(filename).suffix.lower())
    if expected and expected != detected:
        return f"Extension suggests {expected}, but magic bytes indicate {detected}."
    return None
