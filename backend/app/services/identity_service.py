from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from email.utils import parseaddr

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ml.entities import extract_entities
from app.models.evidence import Event, Evidence
from app.models.investigation import (
    AliasSuggestion,
    Identifier,
    IdentifierAlias,
    Owner,
    Party,
    PartyIdentifier,
)
from app.normalize import extract_domain
from app.services.alias_model_service import alias_prediction
from app.services.audit_service import AuditService
from app.services.offline_models import ModelUnavailable


class IdentityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def overview(self, case_id: int) -> dict:
        self._materialize(case_id)
        confirmed_count = self.db.scalar(
            select(func.count(AliasSuggestion.id)).where(
                AliasSuggestion.case_id == case_id, AliasSuggestion.status == "confirmed"
            )
        ) or 0
        party_confirmed: dict[int, int] = {
            party_id: count
            for party_id, count in self.db.execute(
                select(AliasSuggestion.party_id, func.count(AliasSuggestion.id))
                .where(
                    AliasSuggestion.case_id == case_id,
                    AliasSuggestion.status == "confirmed",
                )
                .group_by(AliasSuggestion.party_id)
            )
        }
        parties = list(self.db.scalars(select(Party).where(Party.case_id == case_id)))
        identifiers = list(
            self.db.scalars(
                select(Identifier)
                .join(AliasSuggestion, AliasSuggestion.identifier_id == Identifier.id)
                .where(AliasSuggestion.case_id == case_id)
                .distinct()
            )
        )
        party_map = {item.id: item for item in parties}
        identifier_map = {item.id: item for item in identifiers}
        suggestions = list(
            self.db.scalars(
                select(AliasSuggestion).where(AliasSuggestion.case_id == case_id)
            )
        )
        ranked: list[dict] = []
        model_card = None
        decisions = list(self.db.scalars(select(AliasSuggestion).where(AliasSuggestion.case_id == case_id, AliasSuggestion.status.in_(["confirmed", "reverted"]))))
        for suggestion in suggestions:
            party = party_map.get(suggestion.party_id)
            identifier = identifier_map.get(suggestion.identifier_id)
            if not party or not identifier:
                continue
            feedback_bonus = min(0.08, party_confirmed.get(party.id, 0) * 0.03)
            score = suggestion.confidence
            prediction = None
            try:
                prediction = alias_prediction(suggestion.features)
                model_card = prediction["model_card"]
                score = prediction["confidence"]
            except ModelUnavailable:
                pass
            # Feedback is an auditable priority signal, not retraining on the golden case.
            related = [item for item in decisions if item.party_id == suggestion.party_id]
            positive = sum(item.status == "confirmed" for item in related)
            negative = sum(item.status == "reverted" for item in related)
            utility = (1 + positive) / (2 + positive + negative)
            priority = score * 0.8 + utility * 0.2
            ranked.append(
                {
                    "id": suggestion.id,
                    "party_id": party.id,
                    "party": party.display_name,
                    "identifier_id": identifier.id,
                    "identifier_type": identifier.type,
                    "identifier": identifier.normalized_value,
                    "confidence": round(score, 3),
                    "base_confidence": suggestion.confidence,
                    "status": suggestion.status,
                    "reasons": suggestion.reasons,
                    "features": suggestion.features,
                    "feedback_bonus": round(feedback_bonus, 3),
                    "priority_score": round(priority, 5),
                    "model_name": prediction["model_card"]["name"] if prediction else "deterministic heuristic fallback",
                    "model_version": prediction["model_card"]["version"] if prediction else "1",
                    "shap": prediction["shap"] if prediction else {},
                    "top_reasons": prediction["top_reasons"] if prediction else suggestion.reasons,
                    "explanation_method": "exact interventional SHAP" if prediction else "heuristic",
                    "feedback": {"positive_labels": positive, "negative_labels": negative, "priority_utility": utility, "base_model_retrained_on_case": False},
                }
            )
        ranked.sort(key=lambda item: (-item["priority_score"], item["party"], item["identifier"]))
        links = list(
            self.db.execute(
                select(PartyIdentifier, Party, Identifier)
                .join(Party, Party.id == PartyIdentifier.party_id)
                .join(Identifier, Identifier.id == PartyIdentifier.identifier_id)
                .where(Party.case_id == case_id)
            )
        )
        domains = sorted(
            {item.normalized_value for item in identifier_map.values() if item.type == "domain"}
        )
        return {
            "owners": [
                {"id": item.id, "display_name": item.display_name, "notes": item.notes}
                for item in self.db.scalars(select(Owner).where(Owner.case_id == case_id))
            ],
            "parties": [
                {"id": item.id, "display_name": item.display_name, "kind": item.kind}
                for item in parties
            ],
            "identifiers": [
                {
                    "id": item.id,
                    "type": item.type,
                    "value": item.normalized_value,
                    "raw_value": item.raw_value,
                    "masked": item.masked_for_display,
                }
                for item in identifiers
            ],
            "suggestions": ranked,
            "links": [
                {
                    "party_id": party.id,
                    "party": party.display_name,
                    "identifier_id": identifier.id,
                    "identifier": identifier.normalized_value,
                    "confidence": link.confidence,
                    "source": link.source,
                }
                for link, party, identifier in links
            ],
            "lookalike_domains": lookalike_domains(domains),
            "matcher": {
                "kind": "calibrated_gradient_boosted" if model_card else "deterministic_heuristic_fallback",
                "version": model_card["version"] if model_card else "1",
                "training": "generated synthetic cases only; investigator feedback changes review priority",
                "ml_status": "ready" if model_card else "local_model_unavailable",
                "model_card": model_card,
                "labels_recorded": confirmed_count + sum(item.status == "reverted" for item in suggestions),
                "limits": "Suggestions are leads. Shared names, timing or devices do not establish identity.",
            },
        }

    def confirm(self, case_id: int, suggestion_id: int, actor: str) -> dict:
        suggestion = self._suggestion(case_id, suggestion_id)
        link = self.db.scalar(
            select(PartyIdentifier).where(
                PartyIdentifier.party_id == suggestion.party_id,
                PartyIdentifier.identifier_id == suggestion.identifier_id,
            )
        )
        if link is None:
            link = PartyIdentifier(
                party_id=suggestion.party_id,
                identifier_id=suggestion.identifier_id,
                confidence=suggestion.confidence,
                source="investigator_confirmed_alias",
            )
            self.db.add(link)
        suggestion.status = "confirmed"
        suggestion.feedback_count += 1
        AuditService(self.db).log(
            action="alias.merged",
            actor=actor,
            case_id=case_id,
            target_type="alias_suggestion",
            target_id=str(suggestion.id),
            payload={
                "party_id": suggestion.party_id,
                "identifier_id": suggestion.identifier_id,
                "confidence": suggestion.confidence,
                "reasons": suggestion.reasons,
                "reversible": True,
                "label": 1, "features": suggestion.features, "model_version": "alias-gbt-1.0",
            },
        )
        self.db.flush()
        return {"suggestion_id": suggestion.id, "status": suggestion.status}

    def unmerge(self, case_id: int, suggestion_id: int, actor: str) -> dict:
        suggestion = self._suggestion(case_id, suggestion_id)
        self.db.execute(
            delete(PartyIdentifier).where(
                PartyIdentifier.party_id == suggestion.party_id,
                PartyIdentifier.identifier_id == suggestion.identifier_id,
                PartyIdentifier.source == "investigator_confirmed_alias",
            )
        )
        suggestion.status = "reverted"
        suggestion.feedback_count += 1
        AuditService(self.db).log(
            action="alias.unmerged",
            actor=actor,
            case_id=case_id,
            target_type="alias_suggestion",
            target_id=str(suggestion.id),
            payload={
                "party_id": suggestion.party_id,
                "identifier_id": suggestion.identifier_id,
                "restored_separate_records": True,
                "label": 0, "features": suggestion.features, "model_version": "alias-gbt-1.0",
            },
        )
        self.db.flush()
        return {"suggestion_id": suggestion.id, "status": suggestion.status}

    def _suggestion(self, case_id: int, suggestion_id: int) -> AliasSuggestion:
        suggestion = self.db.get(AliasSuggestion, suggestion_id)
        if not suggestion or suggestion.case_id != case_id:
            raise ValueError("Alias suggestion not found")
        return suggestion

    def _materialize(self, case_id: int) -> None:
        party_by_name = {
            item.display_name.casefold(): item
            for item in self.db.scalars(select(Party).where(Party.case_id == case_id))
        }
        identifier_by_key = {
            (item.type, item.normalized_value): item for item in self.db.scalars(select(Identifier))
        }
        cooccurrence: defaultdict[tuple[int, int], set[int]] = defaultdict(set)
        observed_identifiers: set[int] = set()
        party_times: defaultdict[int, list[float]] = defaultdict(list)
        identifier_times: defaultdict[int, list[float]] = defaultdict(list)
        party_devices: defaultdict[int, set[int]] = defaultdict(set)
        identifier_devices: defaultdict[int, set[int]] = defaultdict(set)
        party_contacts: defaultdict[int, set[str]] = defaultdict(set)
        identifier_contacts: defaultdict[int, set[str]] = defaultdict(set)
        sources = {item.id: item for item in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
        for event in self.db.scalars(select(Event).where(Event.case_id == case_id)):
            event_parties: list[Party] = []
            for raw_name in event.actor_entities or []:
                parsed_name, _ = parseaddr(raw_name)
                name = (parsed_name or raw_name).strip()
                if not name:
                    continue
                party = party_by_name.get(name.casefold())
                if party is None:
                    party = Party(case_id=case_id, display_name=name, kind="observed_name")
                    self.db.add(party)
                    self.db.flush()
                    party_by_name[name.casefold()] = party
                event_parties.append(party)
            found = extract_entities(event.content + " " + " ".join(event.actor_entities or []))
            for entity in list(found):
                if entity["kind"] in {"url", "email"}:
                    domain = extract_domain(entity["canonical"])
                    if domain:
                        found.append(
                            {
                                "kind": "domain",
                                "value": domain,
                                "canonical": domain,
                                "masked": False,
                            }
                        )
            for entity in found:
                key = (entity["kind"], entity["canonical"])
                identifier = identifier_by_key.get(key)
                if identifier is None:
                    identifier = Identifier(
                        type=entity["kind"],
                        normalized_value=entity["canonical"],
                        raw_value=entity["value"],
                        masked_for_display=entity["masked"],
                    )
                    self.db.add(identifier)
                    self.db.flush()
                    identifier_by_key[key] = identifier
                elif entity["value"] != identifier.raw_value:
                    existing_alias = self.db.scalar(
                        select(IdentifierAlias).where(
                            IdentifierAlias.identifier_id == identifier.id,
                            IdentifierAlias.alias == entity["value"],
                        )
                    )
                    if existing_alias is None:
                        self.db.add(
                            IdentifierAlias(
                                identifier_id=identifier.id,
                                alias=entity["value"],
                                reason="normalised_variant",
                            )
                        )
                observed_identifiers.add(identifier.id)
                if event.timestamp_utc:
                    identifier_times[identifier.id].append(event.timestamp_utc.timestamp())
                source = sources.get(event.evidence_id)
                if source and source.device_id:
                    identifier_devices[identifier.id].add(source.device_id)
                identifier_contacts[identifier.id].update(event.actor_entities or [])
                for party in event_parties:
                    if source and source.device_id:
                        party_devices[party.id].add(source.device_id)
                    party_contacts[party.id].update(name for name in event.actor_entities or [] if name != party.display_name)
                    cooccurrence[(party.id, identifier.id)].add(event.id)
                    if event.timestamp_utc:
                        party_times[party.id].append(event.timestamp_utc.timestamp())

        existing_pairs = {
            (item.party_id, item.identifier_id): item
            for item in self.db.scalars(
                select(AliasSuggestion).where(AliasSuggestion.case_id == case_id)
            )
        }
        candidate_index: defaultdict[str, set[int]] = defaultdict(set)
        local_identifiers = {item.id: item for item in identifier_by_key.values() if item.id in observed_identifiers}
        for identifier in local_identifiers.values():
            form = normal_form(identifier.normalized_value.split("@", 1)[0])
            for token in set(form.split()):
                candidate_index["token:" + token].add(identifier.id)
                candidate_index["sound:" + _phonetic_key(token)].add(identifier.id)
            for trigram in {form[i:i+3] for i in range(max(1, len(form)-2))}:
                candidate_index["tri:" + trigram].add(identifier.id)
        for party in party_by_name.values():
            form = normal_form(party.display_name)
            candidate_ids = {identifier_id for (party_id, identifier_id), value in cooccurrence.items() if party_id == party.id and value}
            for token in form.split():
                candidate_ids |= candidate_index["token:" + token] | candidate_index["sound:" + _phonetic_key(token)]
            for trigram in {form[i:i+3] for i in range(max(1, len(form)-2))}:
                candidate_ids |= candidate_index["tri:" + trigram]
            for identifier in (local_identifiers[value] for value in sorted(candidate_ids)):

                features = alias_features(
                    party.display_name,
                    identifier.normalized_value,
                    len(cooccurrence[(party.id, identifier.id)]),
                )
                features["shared_devices"] = len(party_devices[party.id] & identifier_devices[identifier.id])
                features["shared_contact_count"] = len(party_contacts[party.id] & identifier_contacts[identifier.id])
                from bisect import bisect_left
                times = sorted(set(identifier_times[identifier.id]))
                gaps: list[float] = []
                for instant in set(party_times[party.id]):
                    position = bisect_left(times, instant)
                    gaps.extend(abs(instant - times[index]) for index in (position-1, position) if 0 <= index < len(times))
                features["cooccurrence_timing"] = 1 / (1 + min(gaps) / 300) if gaps else 0.0
                if not features["blocked_candidate"]:
                    continue
                score, reasons = alias_score(features)
                if score < 0.42:
                    continue
                suggestion = existing_pairs.get((party.id, identifier.id))
                if suggestion is None:
                    suggestion = AliasSuggestion(
                        case_id=case_id,
                        party_id=party.id,
                        identifier_id=identifier.id,
                        confidence=score,
                        reasons=reasons,
                        features=features,
                    )
                    self.db.add(suggestion)
                elif suggestion.status == "suggested":
                    suggestion.confidence = score
                    suggestion.reasons = reasons
                    suggestion.features = features
        self.db.flush()


def normal_form(value: str) -> str:
    replacements = {"पैसा": "paisa", "पैसे": "paise"}
    value = replacements.get(value.casefold(), value.casefold())
    try:
        from anyascii import anyascii
        value = anyascii(value)
    except ImportError:
        pass
    value = unicodedata.normalize("NFKD", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def damerau_levenshtein(left: str, right: str) -> int:
    rows = len(left) + 1
    cols = len(right) + 1
    matrix = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        matrix[i][0] = i
    for j in range(cols):
        matrix[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                matrix[i][j] = min(matrix[i][j], matrix[i - 2][j - 2] + cost)
    return matrix[-1][-1]


def jaro_winkler(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    distance = max(len(left), len(right)) // 2 - 1
    left_matches = [False] * len(left)
    right_matches = [False] * len(right)
    matches = 0
    for i, char in enumerate(left):
        for j in range(max(0, i - distance), min(i + distance + 1, len(right))):
            if not right_matches[j] and char == right[j]:
                left_matches[i] = True
                right_matches[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    left_order = [left[i] for i in range(len(left)) if left_matches[i]]
    right_order = [right[j] for j in range(len(right)) if right_matches[j]]
    transpositions = sum(a != b for a, b in zip(left_order, right_order, strict=False)) / 2
    jaro = (matches / len(left) + matches / len(right) + (matches - transpositions) / matches) / 3
    prefix = 0
    for a, b in zip(left[:4], right[:4], strict=False):
        if a != b:
            break
        prefix += 1
    return jaro + prefix * 0.1 * (1 - jaro)


def alias_features(party: str, identifier: str, shared_events: int) -> dict:
    party_form = normal_form(party)
    identifier_form = normal_form(identifier.split("@", 1)[0].replace(".", " ").replace("-", " "))
    party_tokens = set(party_form.split())
    identifier_tokens = set(identifier_form.split())
    max_len = max(1, len(party_form), len(identifier_form))
    distance = damerau_levenshtein(party_form, identifier_form)
    ignored_tokens = {"agent", "demo", "example", "parakh", "com", "org", "net"}
    shared_tokens = sorted((party_tokens & identifier_tokens) - ignored_tokens)
    phonetic_match = bool(
        party_tokens
        and identifier_tokens
        and {_phonetic_key(item) for item in party_tokens - ignored_tokens}
        & {_phonetic_key(item) for item in identifier_tokens - ignored_tokens}
    )
    return {
        "damerau_levenshtein": distance,
        "normalised_edit_similarity": round(1 - distance / max_len, 4),
        "jaro_winkler": round(jaro_winkler(party_form, identifier_form), 4),
        "shared_tokens": shared_tokens,
        "phonetic_match": phonetic_match,
        "shared_event_count": shared_events,
        "shared_devices": 0,
        "cooccurrence_timing": shared_events,
        "blocked_candidate": bool(shared_tokens or phonetic_match or shared_events or distance <= 3),
    }


def alias_score(features: dict) -> tuple[float, list[str]]:
    score = (
        features["normalised_edit_similarity"] * 0.12
        + features["jaro_winkler"] * 0.18
        + (0.25 if features["shared_event_count"] else 0)
        + (0.4 if features["shared_tokens"] else 0)
        + (0.05 if features["phonetic_match"] and not features["shared_tokens"] else 0)
    )
    reasons = []
    if features["shared_tokens"]:
        reasons.append(f"Shared token: {', '.join(features['shared_tokens'])}")
    if features["shared_event_count"]:
        reasons.append(f"Co-occurs in {features['shared_event_count']} source event(s)")
    if features["phonetic_match"]:
        reasons.append("Transliterated phonetic form matches")
    reasons.append(f"Jaro-Winkler {features['jaro_winkler']:.2f}")
    reasons.append(f"Damerau-Levenshtein distance {features['damerau_levenshtein']}")
    return round(min(0.99, score), 3), reasons


def _phonetic_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", normal_form(value))
    if not cleaned:
        return ""
    return cleaned[0] + re.sub(r"[aeiouyhw]", "", cleaned[1:])


def lookalike_domains(domains: list[str]) -> list[dict]:
    output = []
    for index, left in enumerate(domains):
        for right in domains[index + 1 :]:
            distance = damerau_levenshtein(left, right)
            if distance <= 3:
                output.append(
                    {
                        "left": left,
                        "right": right,
                        "distance": distance,
                        "status": "heuristic",
                        "reason": "Small edit distance; investigator review required.",
                    }
                )
    return output
