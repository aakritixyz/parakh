"""Shared reproducible uncertainty sampling. Correlated device errors share one draw."""
from __future__ import annotations

import time
from datetime import timedelta

import numpy as np

SEED = 914026
VERSION = "device-clock-monte-carlo-1.0"


def event_ordering(events: list, secondary_evidence_id: int | None, correction: float,
                   interval: list[float], confidence: float, samples: int = 2000) -> dict:
    started = time.monotonic()
    timed = [event for event in events if event.timestamp_utc is not None]
    rng = np.random.default_rng(SEED)
    centre = correction
    radius = max(1.0, (interval[1] - interval[0]) / 2) / max(0.01, confidence)
    errors = rng.uniform(centre - radius, centre + radius, samples)
    corrected = {event.id: event.timestamp_utc + timedelta(seconds=correction if event.evidence_id == secondary_evidence_id else 0) for event in timed}
    ordered = sorted(timed, key=lambda event: (corrected[event.id], event.id))
    items = {}
    pairs = []
    complete = True
    for index, event in enumerate(ordered):
        if time.monotonic() - started > 1.0:
            complete = False
            break
        dependent = event.evidence_id == secondary_evidence_id
        shift = errors if dependent else np.zeros(samples)
        draws = event.timestamp_utc.timestamp() + shift
        comparisons = []
        for neighbour_index in (index - 1, index + 1):
            if not 0 <= neighbour_index < len(ordered):
                continue
            neighbour = ordered[neighbour_index]
            other = neighbour.timestamp_utc.timestamp() + (errors if neighbour.evidence_id == secondary_evidence_id else np.zeros(samples))
            less = draws < other if neighbour_index > index else draws > other
            probability = float(np.mean(less.astype(float) + (draws == other) * 0.5))
            comparisons.append(probability)
            if neighbour_index > index:
                pairs.append({"before_event_id": event.id, "after_event_id": neighbour.id, "probability": round(probability, 4)})
        items[event.id] = {
            "ordering_probability": round(min(comparisons, default=1.0), 4),
            "reconciled_timestamp_utc": corrected[event.id],
            "clock_interval_seconds": [round(float(np.quantile(shift, 0.025)), 3), round(float(np.quantile(shift, 0.975)), 3)],
            "order_depends_on_clock": dependent and radius > 0,
        }
    return {
        "events": items, "pairs": pairs,
        "method": VERSION, "seed": SEED, "samples": samples,
        "time_limit_seconds": 1.0, "complete": complete,
        "assumptions": "One uniform clock correction per device per draw; primary clock is the reference. Interval widens as clock confidence falls. Simultaneous events split probability equally; timing is not causation.",
        "fallback": "Raw source order with unknown ordering probability for unprocessed events; originals unchanged",
    }
