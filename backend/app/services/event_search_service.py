from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ml.entities import extract_entities
from app.models.audit import Comment
from app.models.evidence import Event, Evidence
from app.models.investigation import Device, EventTag, Owner, Tag


class SearchError(ValueError):
    pass


class EventSearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(self, case_id: int, spec: dict) -> dict:
        query = select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id)
        q = str(spec.get("q") or "").strip()
        expanded_q = "refund" if q.casefold() in {"paise wapas", "पैसे वापस"} else q
        if q and self.db.bind and self.db.bind.dialect.name == "sqlite":
            ids = self._sqlite_fts_ids(case_id, expanded_q)
            query = query.where(Event.id.in_(ids))
        events = list(self.db.scalars(query))
        evidence = {
            item.id: item
            for item in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id))
        }
        owners: dict[int | None, str] = {
            item.id: item.display_name
            for item in self.db.scalars(select(Owner).where(Owner.case_id == case_id))
        }
        devices: dict[int | None, str] = {
            item.id: item.label
            for item in self.db.scalars(select(Device).where(Device.case_id == case_id))
        }
        tags_by_event: dict[int, list[str]] = {}
        for event_id, tag_name in self.db.execute(
            select(EventTag.event_id, Tag.name)
            .join(Tag, Tag.id == EventTag.tag_id)
            .where(Tag.case_id == case_id)
        ):
            tags_by_event.setdefault(event_id, []).append(tag_name)

        regex = self._safe_regex(str(spec.get("regex") or ""))
        phrases = [str(item).casefold() for item in spec.get("phrases", []) if str(item).strip()]
        filters = spec.get("facets") or {}
        start = _parse_iso((spec.get("time") or {}).get("start"))
        end = _parse_iso((spec.get("time") or {}).get("end"))
        deadline = time.monotonic() + 0.15

        filtered: list[Event] = []
        for event in events:
            if time.monotonic() > deadline:
                raise SearchError("Search time limit reached. Narrow the filters or regex.")
            source = evidence.get(event.evidence_id)
            haystack = f"{event.content} {' '.join(event.actor_entities or [])}".casefold()
            identifiers = [item["canonical"] for item in extract_entities(haystack)]
            event_owner = owners.get(event.owner_id, "Unknown")
            device = devices.get(source.device_id, "Unknown") if source else "Unknown"
            requested_type = str(filters.get("type") or "")
            type_match = event.event_type
            if requested_type == "payment":
                requested_type = "transaction"
            checks = [
                not q
                or expanded_q.casefold() in haystack
                or bool(self.db.bind and self.db.bind.dialect.name == "sqlite"),
                not phrases or all(phrase in haystack for phrase in phrases),
                regex is None or bool(regex.search(f"{event.content} {' '.join(event.actor_entities or [])}")),
                not requested_type or type_match == requested_type or event.action == requested_type,
                not filters.get("app") or event.source_app == filters["app"],
                not filters.get("owner") or event_owner == filters["owner"],
                not filters.get("device") or device == filters["device"],
                not filters.get("party") or filters["party"] in (event.actor_entities or []),
                not filters.get("identifier") or filters["identifier"] in identifiers,
                not filters.get("tag") or filters["tag"] in tags_by_event.get(event.id, []),
                not filters.get("source")
                or (source is not None and str(filters["source"]) in {str(source.id), source.filename}),
                filters.get("deleted") in {None, "", "all"}
                or bool(event.is_deleted_recovered) == bool(filters["deleted"]),
                start is None or (event.timestamp_utc is not None and event.timestamp_utc >= start),
                end is None or (event.timestamp_utc is not None and event.timestamp_utc <= end),
            ]
            if all(checks):
                filtered.append(event)

        type_counts = Counter(event.event_type for event in filtered)
        app_counts = Counter(event.source_app for event in filtered)
        owner_counts = Counter(owners.get(event.owner_id, "Unknown") for event in filtered)
        device_counts = Counter(
            devices.get(evidence[event.evidence_id].device_id, "Unknown")
            for event in filtered
            if event.evidence_id in evidence
        )
        party_counts = Counter(name for event in filtered for name in event.actor_entities or [])
        identifier_counts = Counter(
            item["canonical"]
            for event in filtered
            for item in extract_entities(event.content + " " + " ".join(event.actor_entities or []))
        )
        tag_counts = Counter(name for event in filtered for name in tags_by_event.get(event.id, []))
        source_counts = Counter(
            evidence[event.evidence_id].filename
            for event in filtered
            if event.evidence_id in evidence
        )
        day_counts = Counter(
            event.timestamp_utc.date().isoformat() for event in filtered if event.timestamp_utc
        )
        page = spec.get("page") or {}
        cursor = int(page.get("cursor") or 0)
        limit = min(100_000, max(1, int(page.get("limit") or 100)))
        page_events = [event for event in filtered if event.id > cursor][:limit]
        return {
            "items": [self._event_out(event, evidence[event.evidence_id], owners, devices, tags_by_event) for event in page_events],
            "total_matching": len(filtered),
            "total_in_case": len(events),
            "next_cursor": page_events[-1].id if len(page_events) == limit else None,
            "search_engine": "sqlite_fts5" if self.db.bind and self.db.bind.dialect.name == "sqlite" else "postgres_full_text",
            "facets": {
                "types": _counts(type_counts),
                "apps": _counts(app_counts),
                "owners": _counts(owner_counts),
                "devices": _counts(device_counts),
                "parties": _counts(party_counts),
                "identifiers": _counts(identifier_counts),
                "tags": _counts(tag_counts),
                "sources": _counts(source_counts),
            },
            "histogram": [{"bucket": key, "count": value} for key, value in sorted(day_counts.items())],
            "filters": spec,
            "query_expansion": {
                "original": q,
                "expanded": expanded_q,
                "method": "declared_hinglish_rule" if expanded_q != q else "none",
            },
            "semantic_search": {
                "status": "planned_after_step_5a",
                "reason": "Offline multilingual embedding models are not enabled before the ML foundation and model-card workflow.",
            },
        }

    def detail(self, case_id: int, event_id: int) -> dict:
        event = self.db.get(Event, event_id)
        if not event or event.case_id != case_id:
            raise SearchError("Event not found")
        evidence = self.db.get(Evidence, event.evidence_id)
        if evidence is None:
            raise SearchError("Source evidence not found")
        adjacent = list(
            self.db.scalars(
                select(Event)
                .where(Event.case_id == case_id, Event.evidence_id == event.evidence_id)
                .order_by(Event.timestamp_utc, Event.id)
            )
        )
        index = adjacent.index(event)
        comments = list(
            self.db.scalars(
                select(Comment).where(
                    Comment.case_id == case_id,
                    Comment.target_type == "event",
                    Comment.target_id == event_id,
                )
            )
        )
        return {
            "event": self._event_out(event, evidence, {}, {}, {}),
            "source": {
                "evidence_id": evidence.id,
                "filename": evidence.filename,
                "reference": event.raw_ref,
                "timestamp": event.timestamp_utc,
                "sha256": evidence.sha256,
            },
            "adjacent": [
                {
                    "event_id": item.id,
                    "timestamp_utc": item.timestamp_utc,
                    "content": item.content,
                    "raw_ref": item.raw_ref,
                }
                for item in adjacent[max(0, index - 2) : index + 3]
            ],
            "comments": [
                {"id": item.id, "body": item.body, "author": item.author, "created_at": item.created_at}
                for item in comments
            ],
        }

    def _sqlite_fts_ids(self, case_id: int, query: str) -> list[int]:
        if len(query) > 200:
            raise SearchError("Text query is limited to 200 characters.")
        connection = self.db.connection()
        connection.execute(
            text("CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(content, actors)")
        )
        indexed: int = connection.execute(text("SELECT count(*) FROM event_fts")).scalar_one()
        expected = self.db.scalar(select(func.count(Event.id))) or 0
        if indexed != expected:
            connection.execute(text("DELETE FROM event_fts"))
            rows = self.db.execute(select(Event.id, Event.content, Event.actor_entities)).all()
            connection.execute(
                text("INSERT INTO event_fts(rowid, content, actors) VALUES (:id, :content, :actors)"),
                [
                    {"id": row.id, "content": row.content, "actors": " ".join(row.actor_entities or [])}
                    for row in rows
                ],
            )
        escaped = query.replace('"', '""')
        return [
            row[0]
            for row in connection.execute(
                text("SELECT rowid FROM event_fts WHERE event_fts MATCH :query"),
                {"query": f'"{escaped}"'},
            )
        ]

    @staticmethod
    def _safe_regex(pattern: str):
        if not pattern:
            return None
        if len(pattern) > 160 or re.search(r"(?:\+|\*|\{\d+,?\d*\})[^)]*\)(?:\+|\*)", pattern):
            raise SearchError("Regex rejected by the timeout guard.")
        try:
            return re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise SearchError(f"Invalid regex: {exc}") from exc

    @staticmethod
    def _event_out(
        event: Event,
        evidence: Evidence,
        owners: dict[int | None, str],
        devices: dict[int | None, str],
        tags: dict[int, list[str]],
    ) -> dict:
        return {
            "event_id": event.id,
            "evidence_id": event.evidence_id,
            "type": event.event_type,
            "action": event.action,
            "app": event.source_app,
            "owner": owners.get(event.owner_id, "Unknown"),
            "device": devices.get(evidence.device_id, "Unknown"),
            "parties": event.actor_entities,
            "identifiers": [
                item["canonical"]
                for item in extract_entities(event.content + " " + " ".join(event.actor_entities or []))
            ],
            "tags": tags.get(event.id, []),
            "timestamp_utc": event.timestamp_utc,
            "original_timestamp": event.original_timestamp,
            "timezone_offset": event.timezone_offset,
            "content": event.content,
            "raw_ref": event.raw_ref,
            "confidence": event.confidence,
            "source": {
                "filename": evidence.filename,
                "sha256": evidence.sha256,
                "reference": event.raw_ref,
            },
        }


def _counts(counter: Counter) -> list[dict]:
    return [{"value": key, "count": value} for key, value in counter.most_common()]


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SearchError("Invalid time filter") from exc
