from __future__ import annotations

import hashlib
import random
import re
import statistics
import time
from collections import Counter, deque
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.models.ml import ModelRecord
from app.services.ml_foundation_service import load_offline_model

SEED = 61026
FDR_ALPHA = 0.05
PERMUTATIONS = 250
IST = timezone(timedelta(hours=5, minutes=30))
PHRASES = {
    "otp bhejo": "Requests for an OTP can enable account takeover.",
    "ओटीपी भेजो": "Hindi request to send an OTP.",
    "double money": "Promises to double money are a common scam cue.",
    "paisa double": "Hinglish promise to double money.",
    "पैसा दोगुना": "Hindi promise to double money.",
    "kyc update": "Unsolicited KYC-update pressure can indicate phishing.",
    "केवाईसी अपडेट": "Hindi KYC-update pressure.",
    "guaranteed return": "Guaranteed-return wording is a scam cue.",
    "jaldi payment": "Hinglish urgency around payment.",
}


class AhoCorasick:
    def __init__(self, phrases: list[str]) -> None:
        self.goto: list[dict[str, int]] = [{}]
        self.fail = [0]
        self.output: list[list[str]] = [[]]
        for phrase in phrases:
            state = 0
            for char in phrase:
                if char not in self.goto[state]:
                    self.goto[state][char] = self._new_state()
                state = self.goto[state][char]
            self.output[state].append(phrase)
        queue = deque(self.goto[0].values())
        while queue:
            state = queue.popleft()
            for char, target in self.goto[state].items():
                queue.append(target)
                fallback = self.fail[state]
                while fallback and char not in self.goto[fallback]:
                    fallback = self.fail[fallback]
                self.fail[target] = self.goto[fallback].get(char, 0)
                self.output[target].extend(self.output[self.fail[target]])

    def _new_state(self) -> int:
        self.goto.append({})
        self.fail.append(0)
        self.output.append([])
        return len(self.goto) - 1

    def find(self, text: str) -> list[str]:
        state = 0
        found: list[str] = []
        for char in text.casefold():
            while state and char not in self.goto[state]:
                state = self.fail[state]
            state = self.goto[state].get(char, 0)
            found.extend(self.output[state])
        return sorted(set(found))


def levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, a in enumerate(left, 1):
        current = [row]
        for column, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (a != b)))
        previous = current
    return previous[-1]


def fuzzy_phrases(text: str) -> list[str]:
    tokens = re.findall(r"[\w]+", text.casefold(), re.UNICODE)
    found: list[str] = []
    for phrase in PHRASES:
        target = phrase.split()
        for size in {max(1, len(target) - 1), len(target), len(target) + 1}:
            for index in range(max(0, len(tokens) - size + 1)):
                window = " ".join(tokens[index : index + size])
                allowed = max(1, round(len(phrase) * 0.18))
                if levenshtein(window, phrase) <= allowed:
                    found.append(phrase)
                    break
            if phrase in found:
                break
    return sorted(set(found))


def simhash(text: str) -> int:
    tokens = re.findall(r"\w+", text.casefold(), re.UNICODE)
    vector = [0] * 64
    for token in tokens:
        digest = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += 1 if digest & (1 << bit) else -1
    return sum((1 << bit) for bit, value in enumerate(vector) if value >= 0)


def benjamini_hochberg(p_values: list[float], alpha: float = FDR_ALPHA) -> list[bool]:
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    cutoff = -1
    for rank, (_, value) in enumerate(ordered, 1):
        if value <= alpha * rank / max(1, len(p_values)):
            cutoff = rank
    accepted = [False] * len(p_values)
    for rank, (index, _) in enumerate(ordered, 1):
        accepted[index] = rank <= cutoff
    return accepted


def _max_window_count(values: list[float], width: float = 900.0) -> int:
    left = 0
    maximum = 0
    for right, value in enumerate(values):
        while value - values[left] > width:
            left += 1
        maximum = max(maximum, right - left + 1)
    return maximum


def permutation_burst_p_value(
    timestamps: list[float], *, seed: int = SEED, permutations: int = PERMUTATIONS, limit_seconds: float = 1.0
) -> tuple[float, bool]:
    if len(timestamps) < 5 or max(timestamps) == min(timestamps):
        return 1.0, True
    observed = _max_window_count(sorted(timestamps))
    start, end = min(timestamps), max(timestamps)
    rng = random.Random(seed)
    extreme = 0
    completed = 0
    deadline = time.monotonic() + limit_seconds
    for _ in range(permutations):
        if time.monotonic() > deadline:
            break
        shuffled = sorted(rng.uniform(start, end) for _ in timestamps)
        extreme += _max_window_count(shuffled) >= observed
        completed += 1
    if completed < 30:
        return 1.0, False
    return (extreme + 1) / (completed + 1), completed == permutations


def _mad(values: list[float]) -> tuple[float, float]:
    median = statistics.median(values) if values else 0.0
    mad = statistics.median(abs(item - median) for item in values) if values else 0.0
    return float(median), float(mad)


def _support(event: Event, evidence: Evidence) -> dict:
    return {
        "event_id": event.id,
        "evidence_id": evidence.id,
        "file": evidence.filename,
        "reference": event.raw_ref,
        "timestamp": event.timestamp_utc,
        "sha256": evidence.sha256,
    }


def _timestamp(event: Event) -> datetime:
    if event.timestamp_utc is None:
        raise ValueError("Timed event is missing timestamp")
    return event.timestamp_utc


class PatternService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyse(self, case_id: int) -> dict:
        events = list(
            self.db.scalars(
                select(Event)
                .where(Event.case_id == case_id)
                .order_by(Event.timestamp_utc, Event.id)
            )
        )
        evidence = {
            item.id: item
            for item in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id))
        }
        communications = [
            event
            for event in events
            if event.event_type in {"message", "call", "email"}
            or event.source_app in {"whatsapp", "email", "phone"}
        ]
        phrase_flags = self._phrase_flags(communications, evidence)
        template_flags = self._template_flags(communications, evidence)
        behaviour_flags = self._behaviour_flags(communications, evidence)
        ml_flags, classifier = self._ml_flags(communications, evidence)
        isolation_flags = self._isolation_flags(communications, evidence)
        return {
            "flags": phrase_flags + template_flags + behaviour_flags + ml_flags + isolation_flags,
            "summary": {
                "events_checked": len(communications),
                "flag_count": len(phrase_flags + template_flags + behaviour_flags + ml_flags + isolation_flags),
                "fdr_alpha": FDR_ALPHA,
            },
            "classifier": classifier,
            "assumptions": {
                "timezone": "Asia/Kolkata",
                "burst_window_minutes": 15,
                "permutations": PERMUTATIONS,
                "seed": SEED,
                "time_limit_seconds": 1.0,
            },
            "fallback": "Incomplete permutation runs return p=1 and are not called significant.",
        }

    def _phrase_flags(self, events: list[Event], evidence: dict[int, Evidence]) -> list[dict]:
        matcher = AhoCorasick(list(PHRASES))
        output = []
        for event in events:
            matches = sorted(set(matcher.find(event.content) + fuzzy_phrases(event.content)))
            for phrase in matches:
                output.append(
                    {
                        "type": "scam_phrase",
                        "title": f"Scam-language cue: {phrase}",
                        "why": PHRASES[phrase],
                        "method": "Aho-Corasick + fuzzy Levenshtein n-grams",
                        "status": "heuristic lead",
                        "confidence": 0.9 if phrase in event.content.casefold() else 0.72,
                        "support": [_support(event, evidence[event.evidence_id])],
                        "caveat": "Legitimate support messages can contain the same words; wording alone does not establish fraud.",
                    }
                )
        return output

    def _template_flags(self, events: list[Event], evidence: dict[int, Evidence]) -> list[dict]:
        groups: list[list[Event]] = []
        for event in [item for item in events if len(item.content) >= 12]:
            fingerprint = simhash(event.content)
            for group in groups:
                if (fingerprint ^ simhash(group[0].content)).bit_count() <= 8:
                    group.append(event)
                    break
            else:
                groups.append([event])
        return [
            {
                "type": "repeated_template",
                "title": f"Near-duplicate message template repeated {len(group)} times",
                "why": "SimHash distance is at most 8 bits across these messages.",
                "method": "SimHash",
                "status": "heuristic lead",
                "confidence": min(0.95, 0.55 + len(group) * 0.06),
                "support": [_support(item, evidence[item.evidence_id]) for item in group[:12]],
                "caveat": "Automated reminders and normal copied replies can also repeat.",
            }
            for group in groups
            if len(group) >= 3
        ]

    def _behaviour_flags(self, events: list[Event], evidence: dict[int, Evidence]) -> list[dict]:
        timed = [event for event in events if event.timestamp_utc]
        if not timed:
            return []
        by_hour = Counter(_timestamp(event).astimezone(IST).replace(minute=0, second=0, microsecond=0) for event in timed)
        median, mad = _mad([float(value) for value in by_hour.values()])
        candidates = []
        p_values = []
        for hour, count in by_hour.items():
            bucket = [event for event in timed if _timestamp(event).astimezone(IST).replace(minute=0, second=0, microsecond=0) == hour]
            if count < max(5, median + 3 * max(1.0, mad)):
                continue
            relevant = [_timestamp(event).timestamp() for event in timed]
            p_value, complete = permutation_burst_p_value(relevant)
            candidates.append((hour, count, bucket, p_value, complete))
            p_values.append(p_value)
        accepted = benjamini_hochberg(p_values)
        output = []
        for (hour, count, bucket, p_value, complete), significant in zip(candidates, accepted, strict=True):
            if not significant:
                continue
            odd = hour.hour < 5
            output.append(
                {
                    "type": "late_night_burst" if odd else "communication_burst",
                    "title": f"{'Late-night ' if odd else ''}activity burst: {count} events in one hour",
                    "why": f"Count exceeds median {median:.1f} with MAD {mad:.1f}; permutation p={p_value:.4f} after FDR control.",
                    "method": "median/MAD + Monte Carlo permutation + Benjamini-Hochberg",
                    "status": "significant anomaly",
                    "confidence": round(1 - p_value, 4),
                    "support": [_support(item, evidence[item.evidence_id]) for item in bucket],
                    "caveat": "Emergencies, travel and scheduled campaigns can create legitimate bursts.",
                    "test": {"p_value": p_value, "fdr_alpha": FDR_ALPHA, "complete": complete, "seed": SEED},
                }
            )
        return output + self._change_point(timed, evidence)

    def _change_point(self, events: list[Event], evidence: dict[int, Evidence]) -> list[dict]:
        contacts = [(event.actor_entities or ["unknown"])[0] for event in events]
        if len(contacts) < 8:
            return []
        novelty = []
        seen: set[str] = set()
        for contact in contacts:
            novelty.append(0.0 if contact in seen else 1.0)
            seen.add(contact)
        mean = statistics.mean(novelty)
        cumulative = 0.0
        peak = (0.0, 0)
        for index, value in enumerate(novelty):
            cumulative = max(0.0, cumulative + value - mean - 0.15)
            peak = max(peak, (cumulative, index))
        if peak[0] < 1.5:
            return []
        event = events[peak[1]]
        return [{
            "type": "contact_change",
            "title": "Sudden contact-pattern change",
            "why": f"CUSUM peak {peak[0]:.2f} follows a run of new contacts.",
            "method": "CUSUM",
            "status": "heuristic lead",
            "confidence": min(0.9, 0.5 + peak[0] / 10),
            "support": [_support(event, evidence[event.evidence_id])],
            "caveat": "A new workgroup or restored address book can cause the same pattern.",
        }]

    def _ml_flags(self, events: list[Event], evidence: dict[int, Evidence]) -> tuple[list[dict], dict]:
        record = self.db.scalar(select(ModelRecord).where(ModelRecord.name == "hinglish-scam-classifier"))
        if record is None:
            return [], {"status": "planned", "reason": "Run the offline Step 6 classifier command."}
        bundle = load_offline_model({"artifact_path": record.artifact_path, "artifact_sha256": record.artifact_sha256})
        output = []
        for event in events:
            vector = bundle["vectorizer"].transform([event.content])
            raw = bundle["model"].predict_proba(vector)[:, 1]
            probability = float(bundle["calibrator"].predict(raw)[0])
            if probability < 0.7:
                continue
            weighted = vector.multiply(bundle["model"].coef_[0]).toarray()[0]
            names = bundle["vectorizer"].get_feature_names_out()
            reasons = [str(names[index]) for index in np.argsort(weighted)[::-1][:5] if weighted[index] > 0]
            output.append({
                "type": "ml_scam_language",
                "title": f"Classifier scam-language lead · {probability:.0%}",
                "why": f"Top character features: {', '.join(reasons) or 'mixed multilingual pattern'}.",
                "method": f"{record.name} {record.version}",
                "status": "ML lead",
                "confidence": round(probability, 4),
                "support": [_support(event, evidence[event.evidence_id])],
                "caveat": "A calibrated synthetic-data score is not a finding and may not transfer to real cases.",
            })
        return output, {"status": "active", "name": record.name, "version": record.version, "metrics": record.metrics, "label": record.evaluation_label}

    def _isolation_flags(self, events: list[Event], evidence: dict[int, Evidence]) -> list[dict]:
        from sklearn.ensemble import IsolationForest

        timed = [event for event in events if event.timestamp_utc]
        if len(timed) < 12:
            return []
        gaps = [0.0]
        gaps.extend((_timestamp(timed[index]) - _timestamp(timed[index - 1])).total_seconds() for index in range(1, len(timed)))
        contacts: set[str] = set()
        features = []
        for event, gap in zip(timed, gaps, strict=True):
            contact = (event.actor_entities or ["unknown"])[0]
            new_contact = float(contact not in contacts)
            contacts.add(contact)
            local_hour = _timestamp(event).astimezone(IST).hour
            features.append([local_hour, min(gap, 86400) / 3600, new_contact])
        model = IsolationForest(random_state=SEED, contamination=0.1, n_estimators=80).fit(features)
        scores = -model.score_samples(features)
        threshold = float(np.quantile(scores, 0.9))
        medians = np.median(features, axis=0)
        output = []
        for event, feature, score in zip(timed, features, scores, strict=True):
            if score < threshold:
                continue
            differences = np.abs(np.asarray(feature) - medians)
            reason_index = int(np.argmax(differences))
            reason = ["unusual local hour", "unusual response gap", "new-contact rate changed"][reason_index]
            output.append({
                "type": "isolation_forest",
                "title": "Unsupervised activity anomaly",
                "why": f"Highest deviation: {reason}; anomaly score {score:.3f}.",
                "method": "Isolation Forest",
                "status": "ML lead",
                "confidence": round(min(0.95, 0.5 + max(0.0, score - threshold)), 4),
                "support": [_support(event, evidence[event.evidence_id])],
                "caveat": "Rare activity is not necessarily suspicious; review the cited source and context.",
            })
        return output
