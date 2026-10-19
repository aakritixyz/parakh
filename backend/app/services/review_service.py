from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import DocumentExtraction, Event, Evidence
from app.models.review import CaseReview


class ReceiptInput(BaseModel):
    evidence_id: int
    reference: str = Field(default="", max_length=255)
    event_id: int | None = None


class FindingInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=4000)
    status: Literal["established", "possible", "not established", "contradicted"] = "not established"
    citations: list[ReceiptInput] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    comments: list[str] = Field(default_factory=list, max_length=100)
    review_state: Literal["draft", "reviewing", "reviewed"] = "draft"


class ExhibitInput(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    kind: Literal["event", "document", "finding"]
    evidence_id: int | None = None
    event_id: int | None = None
    finding_id: str | None = None
    reference: str = Field(default="", max_length=255)
    pages: int = Field(default=1, ge=1, le=100)


class ReviewInput(BaseModel):
    revision: int = Field(ge=0)
    findings: list[FindingInput] = Field(default_factory=list, max_length=200)
    exhibits: list[ExhibitInput] = Field(default_factory=list, max_length=500)


def review_out(db: Session, case_id: int) -> dict:
    item = db.get(CaseReview, case_id)
    return {
        "revision": item.revision if item else 0,
        "findings": item.findings if item else [],
        "exhibits": item.exhibits if item else [],
    }


def validate_review(db: Session, case_id: int, payload: ReviewInput) -> dict:
    evidence = {item.id: item for item in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    event_map = {item.id: item for item in db.scalars(select(Event).where(Event.case_id == case_id))}
    finding_ids = {item.id for item in payload.findings}
    if len(finding_ids) != len(payload.findings) or len({e.id for e in payload.exhibits}) != len(payload.exhibits):
        raise ValueError("Finding and exhibit IDs must be unique")

    def receipt(evidence_id, event_id, reference):
        if evidence_id not in evidence:
            raise ValueError("Source does not belong to this case")
        if event_id is not None:
            event = event_map.get(event_id)
            if event is None or event.evidence_id != evidence_id or reference != event.raw_ref:
                raise ValueError("Event citation does not resolve to its original source reference")
        elif reference and not any(e.evidence_id == evidence_id and e.raw_ref == reference for e in event_map.values()):
            if reference != "ocr:document" or db.scalar(select(DocumentExtraction.id).where(DocumentExtraction.case_id == case_id, DocumentExtraction.evidence_id == evidence_id)) is None:
                raise ValueError("Source reference does not resolve to a parsed record")

    for finding in payload.findings:
        if finding.status != "not established" and not finding.citations:
            raise ValueError("A supported finding must include a source receipt")
        for citation in finding.citations:
            receipt(citation.evidence_id, citation.event_id, citation.reference)
    for exhibit in payload.exhibits:
        if exhibit.kind == "finding":
            if exhibit.finding_id not in finding_ids:
                raise ValueError("Exhibit finding not found")
        else:
            if exhibit.kind == "event" and exhibit.event_id is None:
                raise ValueError("Event exhibit needs an event ID")
            receipt(exhibit.evidence_id, exhibit.event_id, exhibit.reference)
    result = payload.model_dump()
    for finding in result["findings"]:
        for citation in finding["citations"]:
            source = evidence[citation["evidence_id"]]
            event = event_map.get(citation["event_id"])
            citation.update(file=source.filename, sha256=source.sha256,
                            timestamp=event.timestamp_utc.isoformat() if event and event.timestamp_utc else None)
    return result


def select_exhibits(findings: list[dict], exhibits: list[dict], page_limit: int) -> dict:
    """Bounded deterministic branch-and-bound for the binary set-cover program."""
    import time

    started = time.monotonic()
    required = {f["id"] for f in findings if f.get("status") != "not established"}
    covers = []
    for exhibit in exhibits:
        covers.append({f["id"] for f in findings if f["id"] in required and (
            exhibit.get("finding_id") == f["id"] or any(
                link["evidence_id"] == exhibit.get("evidence_id")
                and (not exhibit.get("event_id") or link.get("event_id") == exhibit["event_id"])
                for link in f.get("citations", [])
            )
        )})
    best = None
    complete = True
    # Minimise sum(x_i); sum(pages_i*x_i)<=page_limit; each finding covered >=1.
    # Branch on an uncovered finding, trying only exhibits that actually cover it.
    stack: list[tuple[frozenset[int], frozenset[str], int]] = [(frozenset(), frozenset(), 0)]
    visited: set[frozenset[int]] = set()
    while stack:
        if time.monotonic() - started >= 2 or len(visited) >= 100000:
            complete = False
            break
        chosen, covered, pages = stack.pop()
        if chosen in visited:
            continue
        visited.add(chosen)
        if required <= covered:
            candidate = sorted(chosen)
            if best is None or len(candidate) < len(best):
                best = candidate
            continue
        if best is not None and len(chosen) >= len(best):
            continue
        missing = min(required - covered, key=lambda key: (sum(key in c for c in covers), key))
        for index in reversed(range(len(exhibits))):
            cost = exhibits[index].get("pages", 1)
            if missing in covers[index] and index not in chosen and pages + cost <= page_limit:
                stack.append((chosen | {index}, covered | covers[index], pages + cost))
    status = "OPTIMAL" if complete and best is not None else "INFEASIBLE" if complete else "INCOMPLETE"
    return {
        "selected_ids": [exhibits[i]["id"] for i in (best or [])],
        "status": status, "complete": complete and best is not None,
        "method": "binary integer set cover; deterministic branch-and-bound", "seed": 17018,
        "time_limit_seconds": 2, "state_limit": 100000, "version": "1.0", "page_limit": page_limit,
        "assumptions": "Only explicit finding links or shared source receipts establish coverage; declared pages are estimates. Fixed traversal, no random draws.",
        "fallback": "Keep the manual tray and increase the budget; no unsupported finding is omitted.",
        "required_finding_ids": sorted(required),
    }
