from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime

import regex as timeout_regex
from sqlalchemy import Integer, func, insert, select, text
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

    def _ensure_index(self, case_id: int, budget: float = 15.0) -> None:
        from app.models.search import SearchKey, SearchRecord

        connection = self.db.connection()
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            connection.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(content, actors)"))
            for action in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS search_fts_{action.lower()} AFTER {action} ON events BEGIN DELETE FROM event_fts WHERE rowid=old.id; DELETE FROM search_records WHERE event_id=old.id; DELETE FROM search_keys WHERE event_id=old.id; END")
        started = time.monotonic()
        while True:
            missing = list(self.db.scalars(select(Event).outerjoin(SearchRecord, SearchRecord.event_id == Event.id).where(Event.case_id == case_id, SearchRecord.event_id.is_(None)).order_by(Event.id).limit(5000)))
            if not missing:
                break
            keys: list[dict] = []
            for event in missing:
                found = {item["canonical"] for item in extract_entities(event.content + " " + " ".join(event.actor_entities or []))}
                keys.extend({"case_id": case_id, "event_id": event.id, "kind": kind, "value": value} for kind, values in (("identifier", found), ("party", set(event.actor_entities or []))) for value in values if value)
            self.db.execute(insert(SearchRecord), [{"case_id": case_id, "event_id": event.id} for event in missing])
            if keys:
                self.db.execute(insert(SearchKey), keys)
            if sqlite:
                self.db.execute(text("INSERT OR REPLACE INTO event_fts(rowid,content,actors) VALUES (:id,:content,:actors)"), [{"id": event.id, "content": event.content, "actors": " ".join(event.actor_entities or [])} for event in missing])
            from app.services.embedding_service import CACHE
            for index in (CACHE / str(case_id)).glob("*/index.json"):
                index.unlink(missing_ok=True)
            self.db.flush()
            if time.monotonic() - started > budget:
                raise SearchError("Search index backfill reached its time limit; retry to continue the completed batches.")

    def search(self, case_id: int, spec: dict) -> dict:
        from sqlalchemy import exists, or_

        from app.models.search import SearchKey
        from app.services.embedding_service import rank_documents, rank_persisted_index

        self._ensure_index(case_id)
        filters = spec.get("facets") or {}
        q = str(spec.get("q") or "").strip()
        if len(q) > 200:
            raise SearchError("Text query is limited to 200 characters.")
        expanded = "refund" if q.casefold() in {"paise wapas", "पैसे वापस"} else q
        sqlite = self.db.connection().dialect.name == "sqlite"
        rows = select(Event.id).join(Evidence, Evidence.id == Event.evidence_id).outerjoin(Owner, Owner.id == Event.owner_id).outerjoin(Device, Device.id == Evidence.device_id).where(Event.case_id == case_id)
        total = self.db.scalar(select(func.count(Event.id)).where(Event.case_id == case_id)) or 0
        semantic = {"status": "not_requested", "reason": "Enter text to use offline hybrid retrieval"}
        fused: dict[int, float] = {}
        if q:
            if sqlite:
                terms = re.findall(r"[\w@.+-]+", expanded, re.UNICODE)
                match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
                lexical = [row[0] for row in self.db.execute(text("SELECT event_fts.rowid FROM event_fts JOIN events e ON e.id=event_fts.rowid WHERE event_fts MATCH :q AND e.case_id=:case ORDER BY bm25(event_fts), event_fts.rowid LIMIT 1000"), {"q": match or '""', "case": case_id})]
            else:
                lexical = list(self.db.scalars(select(Event.id).where(Event.case_id == case_id, func.to_tsvector("simple", Event.content).op("@@")(func.plainto_tsquery("simple", expanded))).order_by(Event.id)))
            if total <= 2000:
                documents = [(event.id, event.content + " " + " ".join(event.actor_entities or [])) for event in self.db.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.id))]
                vector, semantic = rank_documents(case_id, documents, q)
            else:
                vector, semantic = rank_persisted_index(case_id, q)
            cutoff = max(0.80, vector[0][1] - 0.025) if vector else 1.0
            vector_ids = [identifier for identifier, score in vector[:250] if score >= cutoff]
            for ordering in (lexical, vector_ids):
                for rank, identifier in enumerate(ordering, start=1):
                    fused[identifier] = fused.get(identifier, 0.0) + 1 / (60 + rank)
            if sqlite:
                lexical_table = text("SELECT event_fts.rowid AS id FROM event_fts JOIN events e ON e.id=event_fts.rowid WHERE event_fts MATCH :match_query AND e.case_id=:match_case").bindparams(match_query=match or '""', match_case=case_id).columns(id=Integer).subquery()
                lexical_ids = select(lexical_table.c.id)
            else:
                lexical_ids = select(Event.id).where(Event.case_id == case_id, func.to_tsvector("simple", Event.content).op("@@")(func.plainto_tsquery("simple", expanded)))
            rows = rows.where(or_(Event.id.in_(lexical_ids), Event.id.in_(vector_ids or [-1])))
        requested_type = str(filters.get("type") or "")
        if requested_type:
            requested_type = "transaction" if requested_type == "payment" else requested_type
            rows = rows.where(Event.event_type == requested_type)
        for key, column in (("app", Event.source_app), ("owner", Owner.display_name), ("device", Device.label)):
            if filters.get(key):
                value = filters[key]
                rows = rows.where(or_(column == value, column.is_(None)) if value == "Unknown" else column == value)
        for kind in ("identifier", "party"):
            if filters.get(kind):
                rows = rows.where(exists(select(SearchKey.event_id).where(SearchKey.event_id == Event.id, SearchKey.kind == kind, SearchKey.value == filters[kind])))
        if filters.get("source"):
            value = str(filters["source"])
            rows = rows.where(or_(Evidence.filename == value, Evidence.id == int(value)) if value.isdigit() else Evidence.filename == value)
        if filters.get("tag"):
            rows = rows.where(exists(select(EventTag.event_id).join(Tag, Tag.id == EventTag.tag_id).where(EventTag.event_id == Event.id, Tag.case_id == case_id, Tag.name == filters["tag"])))
        if filters.get("deleted") not in {None, "", "all"}:
            rows = rows.where(Event.is_deleted_recovered == bool(filters["deleted"]))
        start = _parse_iso((spec.get("time") or {}).get("start"))
        end = _parse_iso((spec.get("time") or {}).get("end"))
        if start:
            rows = rows.where(Event.timestamp_utc >= start)
        if end:
            rows = rows.where(Event.timestamp_utc <= end)
        phrases = [str(value).casefold() for value in spec.get("phrases", []) if str(value).strip()]
        regex = self._safe_regex(str(spec.get("regex") or ""))
        if phrases or regex:
            # Aho-Corasick checks all phrases in one pass; regex has an engine-level timeout.
            from app.services.pattern_service import AhoCorasick
            matcher = AhoCorasick(phrases) if phrases else None
            matched = []
            deadline = time.monotonic() + 2
            for event in self.db.scalars(select(Event).where(Event.id.in_(rows)).execution_options(yield_per=5000)):
                if time.monotonic() > deadline:
                    raise SearchError("Search scan reached its two-second time limit; narrow the filters")
                haystack = event.content + " " + " ".join(event.actor_entities or [])
                phrase_ok = not matcher or set(matcher.find(haystack.casefold())) >= set(phrases)
                if phrase_ok and self._regex_matches(regex, haystack):
                    matched.append(event.id)
            rows = rows.where(Event.id.in_(matched or [-1]))
        selected = rows.subquery()
        ids = select(selected.c.id)
        count = self.db.scalar(select(func.count()).select_from(selected)) or 0
        def facet(column, extra_join=None):
            statement = select(func.coalesce(column, "Unknown"), func.count()).select_from(Event).join(Evidence, Evidence.id == Event.evidence_id).outerjoin(Owner, Owner.id == Event.owner_id).outerjoin(Device, Device.id == Evidence.device_id).where(Event.id.in_(ids))
            if extra_join:
                statement = extra_join(statement)
            return [{"value": value, "count": amount} for value, amount in self.db.execute(statement.group_by(column).order_by(func.count().desc(), column))]
        facets = {"types": facet(Event.event_type), "apps": facet(Event.source_app), "owners": facet(Owner.display_name), "devices": facet(Device.label), "sources": facet(Evidence.filename)}
        for kind, key in (("identifier", "identifiers"), ("party", "parties")):
            facets[key] = [{"value": value, "count": amount} for value, amount in self.db.execute(select(SearchKey.value, func.count()).where(SearchKey.event_id.in_(ids), SearchKey.kind == kind).group_by(SearchKey.value).order_by(func.count().desc(), SearchKey.value))]
        facets["tags"] = [{"value": value, "count": amount} for value, amount in self.db.execute(select(Tag.name, func.count()).join(EventTag, EventTag.tag_id == Tag.id).where(EventTag.event_id.in_(ids), Tag.case_id == case_id).group_by(Tag.name).order_by(Tag.name))]
        bucket = func.date(Event.timestamp_utc)
        histogram = [{"bucket": str(value), "count": amount} for value, amount in self.db.execute(select(bucket, func.count()).where(Event.id.in_(ids), Event.timestamp_utc.is_not(None)).group_by(bucket).order_by(bucket))]
        ist_bucket = func.date(Event.timestamp_utc, "+330 minutes") if sqlite else func.date(Event.timestamp_utc.op("AT TIME ZONE")("Asia/Kolkata"))
        histogram_ist = [{"bucket": str(value), "count": amount} for value, amount in self.db.execute(select(ist_bucket, func.count()).where(Event.id.in_(ids), Event.timestamp_utc.is_not(None)).group_by(ist_bucket).order_by(ist_bucket))]
        page = spec.get("page") or {}
        cursor = max(0, int(page.get("cursor") or 0))
        limit = min(100000, max(1, int(page.get("limit") or 100)))
        # Preserve the existing event-ID cursor contract, including ranked pages.
        from sqlalchemy import case
        score = case(fused, value=Event.id, else_=0) if fused else None
        page_query = select(Event).where(Event.id.in_(ids))
        if cursor:
            if score is not None:
                cursor_score = fused.get(cursor, 0.0)
                page_query = page_query.where(or_(score < cursor_score, (score == cursor_score) & (Event.id > cursor)))
            else:
                page_query = page_query.where(Event.id > cursor)
        page_query = page_query.order_by(score.desc(), Event.id) if score is not None else page_query.order_by(Event.id)
        events = list(self.db.scalars(page_query.limit(limit + 1)))
        has_more = len(events) > limit
        events = events[:limit]
        evidence = {item.id: item for item in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
        owners = {item.id: item.display_name for item in self.db.scalars(select(Owner).where(Owner.case_id == case_id))}
        devices = {item.id: item.label for item in self.db.scalars(select(Device).where(Device.case_id == case_id))}
        page_ids = [item.id for item in events]
        tags: dict = {}
        for event_id, name in self.db.execute(select(EventTag.event_id, Tag.name).join(Tag, Tag.id == EventTag.tag_id).where(EventTag.event_id.in_(page_ids))):
            tags.setdefault(event_id, []).append(name)
        return {"items": [self._event_out(event, evidence[event.evidence_id], owners, devices, tags) for event in events],
                "total_matching": count, "total_in_case": total, "next_cursor": events[-1].id if events and has_more else None,
                "search_engine": "sqlite_fts5" if sqlite else "postgres_full_text", "facets": facets, "histogram": histogram, "histogram_ist": histogram_ist,
                "filters": spec, "query_expansion": {"original": q, "expanded": expanded, "method": "declared_hinglish_rule" if expanded != q else "none"},
                "semantic_search": semantic, "ranking": {"method": "reciprocal rank fusion", "k": 60, "cursor_kind": "event_id"}}

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
                text("INSERT OR REPLACE INTO event_fts(rowid, content, actors) VALUES (:id, :content, :actors)"),
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
            return timeout_regex.compile(pattern, timeout_regex.IGNORECASE)
        except timeout_regex.error as exc:
            raise SearchError(f"Invalid regex: {exc}") from exc

    @staticmethod
    def _regex_matches(pattern, value: str) -> bool:
        if pattern is None:
            return True
        try:
            return bool(pattern.search(value, timeout=0.025))
        except TimeoutError as exc:
            raise SearchError("Regex time limit reached. Narrow the pattern.") from exc

    @staticmethod
    def _event_out(
        event: Event,
        evidence: Evidence,
        owners: dict[int, str],
        devices: dict[int, str],
        tags: dict[int, list[str]],
    ) -> dict:
        return {
            "event_id": event.id,
            "evidence_id": event.evidence_id,
            "type": event.event_type,
            "action": event.action,
            "app": event.source_app,
            "owner": owners.get(event.owner_id, "Unknown") if event.owner_id is not None else "Unknown",
            "device": devices.get(evidence.device_id, "Unknown") if evidence.device_id is not None else "Unknown",
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
            "location": event.location,
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
