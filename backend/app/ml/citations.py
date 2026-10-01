import re

CITATION_RE = re.compile(r"\[evidence_id=(\d+)(?:,\s*event_id=(\d+))?\]")


def verify_citations(text: str) -> dict:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    unsupported = [s for s in sentences if not CITATION_RE.search(s)]
    return {"valid": not unsupported, "unsupported_claims": unsupported, "citations": CITATION_RE.findall(text)}
