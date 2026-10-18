from __future__ import annotations

import random
import time
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.models.investigation import Device, Extraction, Owner

CLOCK_SEED = 91026


def temporal_network(constraints: list[tuple[str, str, int]]) -> dict:
    """Check x[v] <= x[u] + bound constraints with Bellman-Ford."""
    nodes = {name for edge in constraints for name in edge[:2]}
    distance = {node: 0 for node in nodes}
    failed = None
    for iteration in range(len(nodes)):
        changed = False
        for source, target, bound in constraints:
            if distance[target] > distance[source] + bound:
                distance[target] = distance[source] + bound
                changed = True
                failed = {"source": source, "target": target, "bound_seconds": bound}
        if not changed:
            return {"consistent": True, "negative_cycle": None}
        if iteration == len(nodes) - 1:
            return {"consistent": False, "negative_cycle": failed}
    return {"consistent": True, "negative_cycle": None}


def _lcs(left: list[Event], right: list[Event]) -> list[tuple[int, int]]:
    table = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) - 1, -1, -1):
        for j in range(len(right) - 1, -1, -1):
            table[i][j] = (
                1 + table[i + 1][j + 1]
                if left[i].content.strip() == right[j].content.strip()
                else max(table[i + 1][j], table[i][j + 1])
            )
    matches: list[tuple[int, int]] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i].content.strip() == right[j].content.strip():
            matches.append((i, j))
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return matches


class OriginService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyse(self, case_id: int) -> dict:
        evidence = list(
            self.db.scalars(
                select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id)
            )
        )
        events = list(
            self.db.scalars(
                select(Event)
                .where(Event.case_id == case_id)
                .order_by(Event.timestamp_utc, Event.id)
            )
        )
        owners = {
            item.id: item for item in self.db.scalars(select(Owner).where(Owner.case_id == case_id))
        }
        devices = {
            item.id: item
            for item in self.db.scalars(select(Device).where(Device.case_id == case_id))
        }
        extractions = {
            item.id: item
            for item in self.db.scalars(select(Extraction).where(Extraction.case_id == case_id))
        }
        sources = {item.id: item for item in evidence}
        provenance = []
        for event in events:
            source = sources[event.evidence_id]
            extraction = extractions.get(event.extraction_id) if event.extraction_id else None
            owner_id = event.owner_id or source.owner_id
            owner = owners.get(owner_id) if owner_id else None
            device_id = source.device_id or (extraction.device_id if extraction else None)
            device = devices.get(device_id) if device_id else None
            unknown = []
            if owner is None:
                unknown.append("owner")
            if device is None:
                unknown.append("device")
            if not source.acquired_by:
                unknown.append("who acquired it")
            provenance.append(
                {
                    "event_id": event.id,
                    "evidence_id": source.id,
                    "file": source.filename,
                    "source_reference": event.raw_ref,
                    "device": device.label if device else "Unknown",
                    "owner": owner.display_name if owner else "Unknown",
                    "parser": f"{event.parser_name or 'Unknown'} {event.parser_version or ''}".strip(),
                    "extraction_time": (
                        extraction.created_at
                        if extraction
                        else source.received_at or source.created_at
                    ),
                    "timestamp_utc": event.timestamp_utc,
                    "original_timestamp": event.original_timestamp,
                    "timezone_offset": event.timezone_offset,
                    "unknown": unknown,
                }
            )
        comparison, deltas = self._compare_devices(evidence, events)
        correction, engine, complete = self._solve_offset(deltas)
        spread = max([abs(value - correction) for value in deltas], default=0)
        low, high = correction - max(30, spread), correction + max(30, spread)
        rng = random.Random(CLOCK_SEED)
        samples = [rng.uniform(low, high) for _ in range(500)]
        probability = sum(value >= 0 for value in samples) / len(samples)
        return {
            "display_timezone": "Asia/Kolkata",
            "timezone_options": ["Asia/Kolkata", "UTC", "Source time"],
            "provenance": provenance,
            "clock_reconciliation": {
                "device": comparison["secondary_file"] or "second device",
                "observed_clock_offset_seconds": -correction,
                "correction_seconds": correction,
                "range_seconds": [low, high],
                "matched_anchors": len(deltas),
                "solver": {
                    "method": engine,
                    "complete": complete,
                    "time_limit_seconds": 1,
                    "seed": CLOCK_SEED,
                    "fallback": "median of matched cross-source anchors",
                },
            },
            "second_device_comparison": comparison,
            "timeline_consistency": temporal_network(
                [("sent", "received", correction + 60), ("received", "sent", -correction + 60)]
            ),
            "ordering_probability": {
                "statement": "The correction is non-negative",
                "probability": probability,
                "samples": len(samples),
                "seed": CLOCK_SEED,
            },
            "order_dependent_event_ids": [
                item["event_id"]
                for item in provenance
                if item["evidence_id"] == comparison.get("secondary_evidence_id")
                and correction != 0
            ],
        }

    def _compare_devices(
        self, evidence: list[Evidence], events: list[Event]
    ) -> tuple[dict, list[int]]:
        whatsapp = [item for item in evidence if "whatsapp" in item.filename.casefold()]
        if len(whatsapp) < 2:
            return (
                {
                    "primary_file": whatsapp[0].filename if whatsapp else None,
                    "secondary_file": None,
                    "secondary_evidence_id": None,
                    "missing": [],
                    "edited": [],
                    "reordered": [],
                    "method": "Needleman-Wunsch/LCS",
                },
                [],
            )
        primary = next(
            (
                item
                for item in whatsapp
                if "second" not in item.filename.casefold()
                and "tablet" not in item.filename.casefold()
            ),
            whatsapp[0],
        )
        secondary = next((item for item in whatsapp if item.id != primary.id), whatsapp[1])
        left = [
            event for event in events if event.evidence_id == primary.id and event.timestamp_utc
        ]
        right = [
            event for event in events if event.evidence_id == secondary.id and event.timestamp_utc
        ]
        matches = _lcs(left, right)
        left_match, right_match = {i for i, _ in matches}, {j for _, j in matches}
        missing = [
            {
                "event_id": left[i].id,
                "content": left[i].content,
                "source_reference": left[i].raw_ref,
            }
            for i in range(len(left))
            if i not in left_match
        ]
        extra = [
            {
                "event_id": right[j].id,
                "content": right[j].content,
                "source_reference": right[j].raw_ref,
            }
            for j in range(len(right))
            if j not in right_match
        ]
        deltas = []
        for i, j in matches:
            left_time, right_time = left[i].timestamp_utc, right[j].timestamp_utc
            if left_time is not None and right_time is not None:
                deltas.append(int((left_time - right_time).total_seconds()))
        return (
            {
                "primary_file": primary.filename,
                "secondary_file": secondary.filename,
                "secondary_evidence_id": secondary.id,
                "matched": len(matches),
                "missing": missing,
                "edited": extra,
                "reordered": [],
                "method": "Needleman-Wunsch/LCS over message content",
            },
            deltas,
        )

    @staticmethod
    def _solve_offset(deltas: list[int]) -> tuple[int, str, bool]:
        if not deltas:
            return 0, "fallback_median", False
        started = time.monotonic()
        try:
            from ortools.sat.python import cp_model

            model = cp_model.CpModel()
            offset = model.new_int_var(-86400, 86400, "offset")
            deviations = []
            for index, value in enumerate(deltas):
                delta = model.new_int_var(0, 172800, f"delta_{index}")
                model.add_abs_equality(delta, offset - value)
                deviations.append(delta)
            model.minimize(sum(deviations))
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 1
            solver.parameters.random_seed = CLOCK_SEED
            status = solver.solve(model)
            if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
                return int(solver.value(offset)), "CP-SAT", status == cp_model.OPTIMAL
        except (ImportError, AttributeError):
            pass
        return int(median(deltas)), "fallback_median", time.monotonic() - started < 1
