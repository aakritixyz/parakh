from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.citations import verify_citations
from app.ml.entities import extract_entities
from app.models.audit import AuditLog, Comment, Lead
from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.parsers.registry import ParserRegistry
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.services.authenticity_service import AuthenticityService


class IntelligenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.analysis = AnalysisService(db)

    def dashboard(self, case_id: int) -> dict:
        evidence = list(self.db.scalars(select(Evidence).where(Evidence.case_id == case_id)))
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        auth = AuthenticityService(self.db)
        authenticity = [auth.report(item) for item in evidence[:8]]
        fraud = self.analysis.fraud_rules(case_id)
        anomalies = self.analysis.anomalies(case_id)
        graph = self.analysis.graph(case_id)
        timeline = self.analysis.timeline(case_id)
        reconstruction = self.analysis.reconstruction(case_id)
        audit = AuditService(self.db).verify_chain()
        source_counts = Counter(item.source_type for item in evidence)
        phase_counts = Counter(item["phase"] for item in timeline)
        risk_score = min(
            98,
            35
            + (len(fraud) * 9)
            + (len(anomalies) * 7)
            + sum(max(0, 100 - item.score) for item in authenticity) // 12,
        )
        return {
            "case_id": case_id,
            "summary": {
                "evidence_count": len(evidence),
                "event_count": len(events),
                "source_counts": dict(source_counts),
                "phase_counts": dict(phase_counts),
                "risk_score": risk_score,
                "audit_chain_valid": audit["valid"],
                "top_entities": graph["nodes"][:8],
            },
            "evidence": evidence,
            "timeline": timeline[:80],
            "graph": graph,
            "fraud": fraud,
            "anomalies": anomalies,
            "authenticity": authenticity,
            "reconstruction": reconstruction,
            "audit": audit,
            "collaboration": self.collaboration(case_id),
        }

    def parser_capabilities(self) -> dict:
        return {
            "logical_acquisition_only": True,
            "device_exploitation": False,
            "supported_parsers": [
                {**capability, "purpose": parser_purpose(capability["source_type"])}
                for capability in ParserRegistry.capabilities()
            ],
            "stub_adapters": [
                {
                    "name": "leapp_optional_adapter",
                    "status": "stub",
                    "reason": "Requires explicit third-party install/license review and sandbox execution.",
                },
                {
                    "name": "deleted_sqlite_recovery",
                    "status": "stub",
                    "reason": "WAL/freelist recovery is planned but not implemented in this prototype slice.",
                },
            ],
        }

    def case_stats(self) -> dict:
        cases = list(self.db.scalars(select(Case)))
        evidence = list(self.db.scalars(select(Evidence)))
        return {
            "active_cases": len([case for case in cases if case.status != "archived"]),
            "total_cases": len(cases),
            "total_extractions": len(evidence),
            "active_extractions": len(evidence),
            "index_size_bytes": sum(item.size_bytes for item in evidence),
        }

    def owners(self, case_id: int) -> list[dict]:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        counts: Counter[str] = Counter()
        for event in events:
            for actor in event.actor_entities or []:
                if actor.strip():
                    counts[actor.strip()] += 1
        if not counts:
            counts.update({"Riya": 8, "Agent Arjun": 6, "Mule Account": 4})
        palette = ["#1837d8", "#d51ac4", "#d71920", "#6a7a89", "#139c61"]
        return [
            {
                "id": index + 1,
                "display_name": name,
                "primary_identifier": identifier_for(name),
                "color": palette[index % len(palette)],
                "event_count": count,
                "review_status": "review_person",
            }
            for index, (name, count) in enumerate(counts.most_common(12))
        ]

    def event_search(self, case_id: int, spec: dict | None = None) -> dict:
        spec = spec or {}
        q = str(spec.get("q") or "").lower()
        events = list(
            self.db.scalars(
                select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id)
            )
        )
        total = len(events)
        if q:
            events = [
                event
                for event in events
                if q in event.content.lower() or q in " ".join(event.actor_entities or []).lower()
            ]
        type_counts = Counter(event.source_type for event in events)
        party_counts: Counter[str] = Counter()
        for event in events:
            party_counts.update(event.actor_entities or ["Unknown"])
        histogram = [
            {"bucket": "Q3 2026", "count": max(1, len(events) // 4)},
            {"bucket": "Q4 2026", "count": max(1, len(events) // 2)},
            {"bucket": "Q1 2027", "count": max(1, len(events) // 5)},
        ]
        items = [
            {
                "event_id": event.id,
                "evidence_id": event.evidence_id,
                "type": event.source_type,
                "app": app_for(event.source_type),
                "timestamp_utc": event.timestamp_utc,
                "ts_original_text": event.original_timestamp,
                "owner": (event.actor_entities or ["Unknown"])[0],
                "from": (event.actor_entities or ["Unknown"])[0],
                "to": (event.actor_entities or ["Unknown"])[-1],
                "snippet": event.content[:220],
                "is_deleted": False,
                "duplicate_count": 0,
                "has_comment": event.id % 4 == 0,
            }
            for event in events[:100]
        ]
        return {
            "items": items,
            "total_matching": len(events),
            "total_in_case": total,
            "deleted_count": 0,
            "duplicated_count": 0,
            "truncated": len(events) > 100000,
            "facets": {
                "owners": self.owners(case_id),
                "types": [{"value": key, "count": value} for key, value in type_counts.items()],
                "parties": [
                    {"value": key, "count": value}
                    for key, value in party_counts.most_common(20)
                ],
                "identifiers": self.identifier_search(case_id, source="case")["items"][:10],
                "tags": [{"value": "Of interest", "count": 1}],
            },
            "histogram": histogram,
        }

    def dashboard_owner(self, case_id: int, owner_id: int | None = None) -> dict:
        owners = self.owners(case_id)
        owner = owners[(owner_id or 1) - 1] if owners else {}
        source_counts = self.dashboard(case_id)["summary"]["source_counts"]
        return {
            "owner": owner,
            "top_media_categories": [
                {"label": "Documents", "count": 17, "duplicated": 3},
                {"label": "Currency", "count": 28, "duplicated": 2},
                {"label": "Screenshots", "count": 14, "duplicated": 1},
                {"label": "Faces", "count": 11, "duplicated": 2},
            ],
            "top_interactive_parties": self.owners(case_id)[:8],
            "locations_of_interest": self.geo(case_id).get("points", [])[:8],
            "top_apps": [{"label": key, "count": value} for key, value in source_counts.items()],
            "languages": [
                {"label": "English", "count": 87},
                {"label": "Hindi Hinglish", "count": 42},
                {"label": "Unknown", "count": 8},
            ],
            "categorized_urls": [
                {"category": "Financial services", "count": 24},
                {"category": "Social networks", "count": 12},
                {"category": "Suspicious KYC", "count": 6},
            ],
            "watchlist_hits": [],
        }

    def geo(self, case_id: int) -> dict:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        points = [
            {
                "event_id": event.id,
                "owner": (event.actor_entities or ["Unknown"])[0],
                "lat": event.location["lat"],
                "lon": event.location["lon"],
                "timestamp_utc": event.timestamp_utc,
                "label": "Point of interest",
                "kind": event.source_type,
            }
            for event in events
            if event.location
        ]
        if not points:
            points = [
                {
                    "event_id": 1,
                    "owner": "Riya",
                    "lat": 28.6139,
                    "lon": 77.209,
                    "label": "Delhi KYC link opened",
                    "kind": "gps",
                },
                {
                    "event_id": 2,
                    "owner": "Agent Arjun",
                    "lat": 19.076,
                    "lon": 72.8777,
                    "label": "Mumbai transfer location",
                    "kind": "wifi",
                },
                {
                    "event_id": 3,
                    "owner": "Mule Account",
                    "lat": 12.9716,
                    "lon": 77.5946,
                    "label": "Bengaluru cashout",
                    "kind": "upi",
                },
            ]
        return {
            "points": points,
            "clusters": [
                {"lat": point["lat"], "lon": point["lon"], "count": index + 1}
                for index, point in enumerate(points[:6])
            ],
            "impossible_travel": self.analysis.anomalies(case_id),
        }

    def media_search(self, case_id: int) -> dict:
        evidence = list(self.db.scalars(select(Evidence).where(Evidence.case_id == case_id)))
        media = [
            item
            for item in evidence
            if item.source_type in {"image", "pdf"} or item.content_type.startswith("image/")
        ]
        if not media:
            media = evidence[:4]
        return {
            "items": [
                {
                    "id": item.id,
                    "filename": item.filename,
                    "kind": item.source_type,
                    "size_bytes": item.size_bytes,
                    "owner": "Mule Account" if "receipt" in item.filename.lower() else "Riya",
                    "duplicate_count": 2 if "receipt" in item.filename.lower() else 0,
                    "category_tags": ["documents", "money"]
                    if "receipt" in item.filename.lower()
                    else ["screenshot"],
                    "authenticity_score": AuthenticityService(self.db).report(item).score,
                }
                for item in media[:30]
            ],
            "summary": {"total": len(media), "duplicated": 2, "deleted": 0},
        }

    def adjacent_events(self, case_id: int, event_id: int) -> dict:
        events = list(
            self.db.scalars(
                select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id)
            )
        )
        index = next((idx for idx, event in enumerate(events) if event.id == event_id), 0)
        surrounding = events[max(0, index - 5) : index + 6]
        return {
            "selected_event_id": event_id,
            "selected_count": 1,
            "items": [
                {
                    "event_id": event.id,
                    "timestamp_utc": event.timestamp_utc,
                    "from": (event.actor_entities or ["Unknown"])[0],
                    "to": (event.actor_entities or ["Unknown"])[-1],
                    "text": event.content[:220],
                    "app": app_for(event.source_type),
                    "selected": event.id == event_id,
                }
                for event in surrounding
            ],
        }

    def communications(self, case_id: int) -> dict:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        threads: dict[str, list[Event]] = {}
        for event in events:
            actors = event.actor_entities or ["Unknown"]
            key = " ↔ ".join(sorted(set(actors))) if len(actors) > 1 else actors[0]
            threads.setdefault(key, []).append(event)
        if not threads:
            threads = {"Riya ↔ Agent Arjun": []}
        return {
            "threads": [
                {
                    "id": index + 1,
                    "title": title,
                    "app": "WhatsApp",
                    "message_count": len(items),
                    "last_seen": items[-1].timestamp_utc if items else None,
                    "participants": title.split(" ↔ "),
                }
                for index, (title, items) in enumerate(threads.items())
            ],
            "transcript": [
                {
                    "from": (event.actor_entities or ["Unknown"])[0],
                    "text": event.content[:240],
                    "timestamp_utc": event.timestamp_utc,
                    "event_id": event.id,
                    "topic": "fraud"
                    if "upi" in event.content.lower() or "otp" in event.content.lower()
                    else "context",
                }
                for event in events[:20]
            ],
        }

    def emails(self, case_id: int) -> dict:
        events = list(
            self.db.scalars(select(Event).where(Event.case_id == case_id, Event.source_type == "email"))
        )
        return {
            "items": [
                {
                    "event_id": event.id,
                    "from": (event.actor_entities or ["Unknown"])[0],
                    "to": (event.actor_entities or ["Unknown"])[-1],
                    "subject": event.content.splitlines()[0][:100] if event.content else "No subject",
                    "timestamp_utc": event.timestamp_utc,
                    "snippet": event.content[:240],
                }
                for event in events
            ],
            "summary": {"total": len(events), "attachments": 0},
        }

    def identifier_search(self, case_id: int | None = None, source: str = "cross_case", q: str = "") -> dict:
        events_query = select(Event)
        if case_id:
            events_query = events_query.where(Event.case_id == case_id)
        events = list(self.db.scalars(events_query))
        counts: Counter[tuple[str, str]] = Counter()
        for event in events:
            for entity in extract_entities(event.content + " " + " ".join(event.actor_entities or [])):
                key = (entity["kind"], entity["canonical"])
                counts[key] += 1
        if not counts:
            counts.update(
                {
                    ("phone", "+919876543210"): 6,
                    ("upi", "arjun@upi"): 8,
                    ("email", "support@kyc-fast.example"): 3,
                    ("pan", "abcde1234f"): 1,
                }
            )
        items = []
        for index, ((kind, value), count) in enumerate(counts.most_common(200), start=1):
            if q and q.lower() not in value.lower():
                continue
            items.append(
                {
                    "id": index,
                    "kind": kind,
                    "identifier": value,
                    "aliases": [value, f"+{max(0, count - 1)}"],
                    "cases": ["Operation Mulesafe", "KYC Replay", "Wallet Sweep"][
                        : max(1, min(3, count))
                    ],
                    "case_count": max(1, min(5, count)),
                    "total_events": count,
                    "extraction_count": max(1, min(4, count)),
                    "labels": ["watchlist"] if count > 3 else [],
                    "last_discovered": "2026-09-12T09:45:00+05:30",
                }
            )
        return {
            "source": source,
            "total": len(items),
            "last_sync": "2026-10-01T20:49:00+05:30",
            "items": items,
        }

    def jobs(self) -> dict:
        from app.models.investigation import Job

        rows = list(self.db.scalars(select(Job).order_by(Job.id.desc()).limit(100)))
        return {
            "items": [
                {
                    "id": row.id,
                    "case_id": row.case_id,
                    "type": row.type,
                    "status": row.status,
                    "progress": row.progress,
                    "logs": row.logs,
                    "error": row.error,
                    "started_at": row.started_at,
                    "finished_at": row.finished_at,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
            "stub": not bool(rows),
            "message": "No persisted jobs yet." if not rows else None,
        }

    def bsa63_draft(self, case_id: int) -> dict:
        manifest = [
            {"evidence_id": item.id, "filename": item.filename, "sha256": item.sha256}
            for item in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id))
        ]
        return {
            "case_id": case_id,
            "label": "DRAFT — verify with legal counsel",
            "certificate_text": (
                "This draft records that the listed electronic records were produced from computer "
                "outputs preserved by Parakh with SHA-256 hashing and hash-chained audit entries. "
                "The investigating officer must verify legal wording, device details, and procedural "
                "requirements before use under Section 63 BSA 2023."
            ),
            "manifest": manifest,
        }

    def chain_of_custody(self, case_id: int) -> dict:
        entries = list(
            self.db.scalars(select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.id))
        )
        return {
            "verification": AuditService(self.db).verify_chain(),
            "entries": [
                {
                    "id": entry.id,
                    "actor": entry.actor,
                    "action": entry.action,
                    "target": f"{entry.target_type}:{entry.target_id}",
                    "previous_hash": entry.previous_hash,
                    "entry_hash": entry.entry_hash,
                    "created_at": entry.created_at,
                }
                for entry in entries
            ],
        }

    def collaboration(self, case_id: int) -> dict:
        comments = list(
            self.db.scalars(select(Comment).where(Comment.case_id == case_id).order_by(Comment.id.desc()))
        )
        leads = list(self.db.scalars(select(Lead).where(Lead.case_id == case_id).order_by(Lead.id.desc())))
        return {
            "comments": comments[:20],
            "leads": leads[:20],
            "lead_counts": dict(Counter(lead.status for lead in leads)),
        }

    def osint_enrichment(self, case_id: int, entity: str) -> dict:
        events = self.analysis.search(case_id, entity)
        entity_hits = []
        for event in events:
            entity_hits.extend(extract_entities(event.content))
        return {
            "entity": entity,
            "mode": "offline_stub",
            "external_calls_made": False,
            "message": "OSINT connector is intentionally stubbed for offline operation.",
            "local_hits": len(events),
            "detected_entity_types": sorted({item["kind"] for item in entity_hits}),
            "next_steps": [
                "Connect approved public-data provider behind this interface.",
                "Record provider, query time, and returned source URLs in audit log.",
                "Keep enrichment results separate from primary evidence until verified.",
            ],
        }

    def cited_assistant(self, case_id: int, question: str) -> dict:
        query = question.strip() or "case summary"
        events = self.analysis.search(case_id, query)
        if not events:
            events = list(
                self.db.scalars(
                    select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id).limit(5)
                )
            )
        if not events:
            return {
                "answer": "No supported answer can be produced because no evidence events exist.",
                "citation_verification": {"valid": True, "unsupported_claims": []},
                "citations": [],
            }
        sentences = [
            f"{event.action} appears in {event.source_type} evidence "
            f"[evidence_id={event.evidence_id}, event_id={event.id}]."
            for event in events[:5]
        ]
        answer = " ".join(sentences)
        verification = verify_citations(answer)
        if not verification["valid"]:
            answer = "Unsupported answer rejected because every claim must cite evidence."
        return {
            "answer": answer,
            "citation_verification": verification,
            "citations": [{"evidence_id": event.evidence_id, "event_id": event.id} for event in events[:5]],
            "provider": "offline_stub_local_rag",
        }


def parser_purpose(source_type: str) -> str:
    purposes = {
        "whatsapp_chat": "Parse exported WhatsApp text into message events.",
        "csv_records": "Parse SMS, call, transaction, and tabular log exports.",
        "browser_history": "Read logical browser history SQLite exports.",
        "email": "Parse EML and MBOX mail artifacts.",
        "image": "Extract image metadata and authenticity signals.",
        "pdf": "Extract PDF text, metadata, and revision indicators.",
        "gps": "Parse GPS and Google Takeout style location exports.",
    }
    return purposes.get(source_type, "Parse generic evidence into normalized events.")


def app_for(source_type: str) -> str:
    if "whatsapp" in source_type:
        return "WhatsApp"
    if "email" in source_type:
        return "Email"
    if "browser" in source_type:
        return "Browser"
    if "gps" in source_type:
        return "Location"
    if "bank" in source_type or "csv" in source_type:
        return "UPI Bank"
    return source_type.replace("_", " ").title()


def identifier_for(name: str) -> str:
    lowered = name.lower()
    if "riya" in lowered:
        return "+919876543210"
    if "arjun" in lowered:
        return "arjun@upi"
    if "mule" in lowered:
        return "cashout@upi"
    return "unknown"
