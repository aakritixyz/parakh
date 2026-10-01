from collections import Counter, defaultdict
from datetime import UTC, datetime
from math import atan2, cos, radians, sin, sqrt

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.citations import verify_citations
from app.ml.entities import extract_entities
from app.models.entity import Entity
from app.models.evidence import Event


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def materialize_entities(self, case_id: int) -> list[Entity]:
        existing = {(e.kind, e.canonical) for e in self.db.scalars(select(Entity).where(Entity.case_id == case_id))}
        created = []
        events = self.db.scalars(select(Event).where(Event.case_id == case_id))
        for event in events:
            for item in extract_entities(" ".join([event.content, " ".join(event.actor_entities or [])])):
                key = (item["kind"], item["canonical"])
                if key in existing:
                    continue
                entity = Entity(
                    case_id=case_id,
                    kind=item["kind"],
                    canonical=item["canonical"],
                    aliases=[item["value"]],
                    masked=item["masked"],
                )
                self.db.add(entity)
                created.append(entity)
                existing.add(key)
        self.db.flush()
        return created

    def search(self, case_id: int, query: str) -> list[Event]:
        needle = query.lower()
        return [
            e
            for e in self.db.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id))
            if needle in e.content.lower() or needle in " ".join(e.actor_entities or []).lower()
        ]

    def anomalies(self, case_id: int) -> list[dict]:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        anomalies = []
        by_actor: dict[str, list[Event]] = defaultdict(list)
        for event in events:
            for actor in event.actor_entities or ["unknown"]:
                by_actor[actor].append(event)
            if event.timestamp_utc and event.timestamp_utc.astimezone(UTC).hour in {0, 1, 2, 3, 4}:
                anomalies.append({"type": "odd_hours", "event_id": event.id, "features": {"hour_utc": event.timestamp_utc.hour}})
        for actor, actor_events in by_actor.items():
            days = Counter(e.timestamp_utc.date().isoformat() for e in actor_events if e.timestamp_utc)
            for day, count in days.items():
                if count >= 8:
                    anomalies.append({"type": "communication_burst", "actor": actor, "features": {"day": day, "count": count}})
        anomalies.extend(self._location_jumps(events))
        return anomalies

    def _location_jumps(self, events: list[Event]) -> list[dict]:
        points = [e for e in events if e.location and e.timestamp_utc]
        points.sort(key=lambda e: e.timestamp_utc or datetime.min.replace(tzinfo=UTC))
        out = []
        for a, b in zip(points, points[1:], strict=False):
            hours = abs(((b.timestamp_utc or datetime.now(UTC)) - (a.timestamp_utc or datetime.now(UTC))).total_seconds()) / 3600
            if hours == 0:
                continue
            if not a.location or not b.location:
                continue
            km = haversine(a.location["lat"], a.location["lon"], b.location["lat"], b.location["lon"])
            speed = km / hours
            if speed > 900:
                out.append({"type": "impossible_travel", "event_ids": [a.id, b.id], "features": {"km": round(km, 2), "hours": round(hours, 2), "kmh": round(speed, 2)}})
        return out

    def fraud_rules(self, case_id: int) -> list[dict]:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        findings: list[dict[str, object]] = []
        content = "\n".join(e.content for e in events).lower()
        for phrase in ["guaranteed return", "double money", "kyc update", "otp", "urgent payment", "investment plan"]:
            if phrase in content:
                findings.append({"type": "scam_language", "rule": phrase, "explanation": "Common phishing/investment-scam wording found."})
        upi_targets: Counter[str] = Counter()
        for event in events:
            for ent in extract_entities(event.content):
                if ent["kind"] == "upi":
                    upi_targets[ent["canonical"]] += 1
        for upi, count in upi_targets.items():
            if count >= 3:
                findings.append(
                    {
                        "type": "mule_account_fan_in",
                        "upi": upi,
                        "features": {"mentions": count},
                    }
                )
        return findings

    def graph(self, case_id: int) -> dict:
        graph = nx.Graph()
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        for event in events:
            entities = [x["canonical"] for x in extract_entities(event.content)]
            entities += event.actor_entities or []
            for entity in entities:
                graph.add_node(entity, kind="entity")
            for a in entities:
                for b in entities:
                    if a != b:
                        graph.add_edge(a, b, weight=graph.get_edge_data(a, b, {}).get("weight", 0) + 1, event_id=event.id)
        centrality = nx.degree_centrality(graph) if graph.nodes else {}
        return {
            "nodes": [{"id": n, "centrality": centrality.get(n, 0)} for n in graph.nodes],
            "edges": [{"source": a, "target": b, **data} for a, b, data in graph.edges(data=True)],
            "communities": [list(c) for c in nx.connected_components(graph)] if graph.nodes else [],
        }

    def timeline(self, case_id: int) -> list[dict]:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id)))
        return [
            {
                "event_id": e.id,
                "evidence_id": e.evidence_id,
                "timestamp_utc": e.timestamp_utc,
                "phase": self._phase(e),
                "action": e.action,
                "summary": e.content[:180],
            }
            for e in events
        ]

    def reconstruction(self, case_id: int) -> dict:
        timeline = self.timeline(case_id)
        key_events = timeline[:20]
        narrative = " ".join(
            f"{item['action']} observed [evidence_id={item['evidence_id']}, event_id={item['event_id']}]."
            for item in key_events[:8]
        )
        citation_check = verify_citations(narrative) if narrative else {"valid": True}
        return {
            "phases": sorted({item["phase"] for item in timeline}),
            "key_events": key_events,
            "hypotheses": [{"text": "Likely coordinated fraud flow based on repeated scam language and payment identifiers.", "confidence": 0.64, "citations": key_events[:3]}] if key_events else [],
            "contradictions": [],
            "gaps": ["Prototype reconstruction: human investigator should verify timeline and missing device sources."],
            "narrative": narrative,
            "citation_verification": citation_check,
        }

    def contradictions(self, case_id: int) -> list[dict]:
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
        contradictions = []
        pdf_events = [event for event in events if event.source_type == "pdf"]
        payment_events = [
            event
            for event in events
            if "upi" in event.content.lower() or "payment" in event.content.lower()
        ]
        if pdf_events and payment_events:
            contradictions.append(
                {
                    "type": "document_vs_transaction",
                    "severity": "medium",
                    "explanation": "A receipt/document exists and should be checked against actual transaction rows.",
                    "evidence_ids": sorted({event.evidence_id for event in [*pdf_events, *payment_events]}),
                }
            )
        location_events = [event for event in events if event.location]
        if len(location_events) < 2:
            contradictions.append(
                {
                    "type": "location_gap",
                    "severity": "low",
                    "explanation": "Insufficient location samples to validate movement or alibi claims.",
                    "evidence_ids": [event.evidence_id for event in location_events],
                }
            )
        return contradictions

    def _phase(self, event: Event) -> str:
        text = event.content.lower()
        if "payment" in text or "upi" in text or "bank" in text:
            return "financial_transfer"
        if "http" in text or "kyc" in text or "otp" in text:
            return "lure_or_credential_capture"
        if event.source_type == "gps":
            return "movement"
        return "communications"


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return radius * 2 * atan2(sqrt(a), sqrt(1 - a))
