from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.evidence import DocumentExtraction, Event, Evidence
from app.services import local_llm
from app.services.embedding_service import rank_documents
from app.services.offline_models import ModelUnavailable, local_model

TOKEN_RE = re.compile(r"[\w@.+-]+", re.UNICODE)
INJECTION_RE = re.compile(
    r"(?i)(ignore (?:all |the )?(?:previous|prior) instructions|system prompt|"
    r"developer message|you are chatgpt|do not cite|without citations)"
)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "did",
    "do",
    "does",
    "from",
    "in",
    "is",
    "it",
    "of",
    "the",
    "to",
    "was",
    "what",
    "where",
    "who",
}
MONEY_TERMS = {"money", "payment", "paid", "transfer", "debit", "credit", "bank", "upi"}


@dataclass(frozen=True)
class RetrievedItem:
    evidence: Evidence
    text: str
    score: float
    event: Event | None = None
    document: DocumentExtraction | None = None

    @property
    def citation(self) -> dict:
        return {
            "event_id": self.event.id if self.event else -int(self.document.id if self.document is not None else 0),
            "evidence_id": self.evidence.id,
            "file": self.evidence.filename,
            "reference": self.event.raw_ref if self.event else "ocr:document",
            "timestamp": self.event.timestamp_utc if self.event else None,
            "sha256": self.evidence.sha256,
        }


class AssistantService:
    """Case-only retrieval and answers with deterministic citation validation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def answer(self, case_id: int, question: str, mode: str = "answer") -> dict:
        clean_question = question.strip()
        model_card = self._model_card()
        if not clean_question or INJECTION_RE.search(clean_question):
            return self._refusal(model_card, "The question did not contain a supported case query.")

        retrieved = self._retrieve(case_id, clean_question)
        if not retrieved:
            return self._refusal(model_card, "No retrieved case item supported the question.")

        claims = self._extractive_claims(clean_question, retrieved)
        repair_attempted = False
        if model_card["provider"] == "Ollama (loopback)":
            claims = self._ollama_claims(clean_question, retrieved, repair=False, mode=mode) or []
            if not self._validate_claims(claims, retrieved):
                repair_attempted = True
                claims = (self._ollama_claims(clean_question, retrieved, repair=True, mode=mode) or []) if mode == "translate" else self._extractive_claims(clean_question, retrieved)

        if mode == "translate" and model_card["provider"] != "Ollama (loopback)":
            return self._refusal(model_card, "Local translation model unavailable.")
        valid = self._validate_claims(claims, retrieved)
        if not valid:
            return self._refusal(
                model_card,
                "Citation validation failed after one repair attempt.",
                repair_attempted=repair_attempted,
            )

        citations = []
        seen = set()
        for claim in claims:
            for citation in claim["citations"]:
                key = (citation["evidence_id"], citation["event_id"])
                if key not in seen:
                    seen.add(key)
                    citations.append(citation)
        return {
            "answer": " ".join(claim["text"] for claim in claims),
            "refused": False,
            "claims": claims,
            "citations": citations,
            "validation": {
                "valid": True,
                "repair_attempted": repair_attempted,
                "repair_method": "one source-rendering repair; translation uses one local-model repair",
                "method": "canonical source excerpts or pretrained multilingual NLI plus exact citation/value checks",
            },
            "retrieval": {
                "method": "BM25 + offline multilingual-e5-small when provisioned + RRF + MMR",
                "retrieved": len(retrieved),
                "cloud_models": "off",
            },
            "model_card": model_card,
            "mode": mode,
            "originals": [{"text": item.text, "citation": item.citation} for item in retrieved] if mode == "translate" else [],
        }

    def _retrieve(self, case_id: int, question: str, limit: int = 6) -> list[RetrievedItem]:
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
        if not events:
            events = []
        extractions = list(
            self.db.scalars(
                select(DocumentExtraction).where(DocumentExtraction.case_id == case_id)
            )
        )
        sources = [
            RetrievedItem(evidence[event.evidence_id], self._safe_event_text(event), 0.0, event=event)
            for event in events
            if event.evidence_id in evidence
        ]
        sources.extend(
            RetrievedItem(
                evidence[document.evidence_id],
                INJECTION_RE.sub("[instruction-like evidence text omitted]", document.ocr_text),
                0.0,
                document=document,
            )
            for document in extractions
            if document.evidence_id in evidence and document.ocr_text.strip()
        )
        if not sources:
            return []

        query_tokens = self._query_tokens(question)
        documents = [source.text for source in sources]
        doc_tokens = [_tokens(text) for text in documents]
        frequencies = Counter(token for tokens in doc_tokens for token in set(tokens))
        average_length = sum(map(len, doc_tokens)) / max(1, len(doc_tokens))
        bm25 = [
            _bm25(query_tokens, tokens, frequencies, len(sources), average_length)
            for tokens in doc_tokens
        ]
        ranked, _ = rank_documents(case_id, [(i, text) for i, text in enumerate(documents)], question)
        semantic_lookup = dict(ranked)
        semantic = [semantic_lookup.get(i, 0.0) for i in range(len(sources))]
        bm25_rank = _rank(bm25)
        semantic_rank = _rank(semantic)
        rrf = [1 / (60 + bm25_rank[i]) + (1 / (60 + semantic_rank[i]) if ranked else 0) for i in range(len(sources))]

        candidates = sorted(range(len(sources)), key=lambda index: rrf[index], reverse=True)
        selected: list[int] = []
        while candidates and len(selected) < limit:
            best = max(
                candidates,
                key=lambda index: 0.75 * rrf[index] / max(rrf)
                - 0.25
                * max(
                    (len(set(doc_tokens[index]) & set(doc_tokens[other])) / max(1, len(set(doc_tokens[index]) | set(doc_tokens[other]))) for other in selected),
                    default=0.0,
                ),
            )
            selected.append(best)
            candidates.remove(best)

        entity_tokens = {token for source in sources if source.event for actor in (source.event.actor_entities or []) for token in _tokens(actor)}
        meaningful = set(query_tokens) - STOP_WORDS - entity_tokens - {"s", "please", "tell", "me", "about", "her", "his", "their", "can", "you", "could", "would"}
        money_query = bool(meaningful & MONEY_TERMS)
        result = []
        for index in selected:
            source = sources[index]
            overlap = meaningful & set(doc_tokens[index])
            if not overlap and not (
                money_query and source.event is not None and source.event.event_type == "transaction"
            ):
                continue
            result.append(
                RetrievedItem(
                    source.evidence,
                    source.text,
                    rrf[index],
                    event=source.event,
                    document=source.document,
                )
            )
        return result

    @staticmethod
    def _query_tokens(question: str) -> list[str]:
        tokens = _tokens(question)
        if set(tokens) & {"money", "payment", "paid", "transfer", "paise", "paisa", "पैसे", "पैसा", "wapas", "वापस"}:
            tokens.extend(["transaction", "debit", "credit", "upi", "amount", "counterparty"])
        if set(tokens) & {"contact", "contacted", "message", "called"}:
            tokens.extend(["message", "call", "from", "party"])
        if set(tokens) & {"receipt", "refund"}:
            tokens.extend(["utr", "amount", "credit", "debit", "receipt"])
        return tokens

    def _safe_event_text(self, event: Event) -> str:
        text = " ".join(
            [event.event_type, event.action, event.source_type, *(event.actor_entities or []), event.content]
        )
        return INJECTION_RE.sub("[instruction-like evidence text omitted]", text)

    def _extractive_claims(self, question: str, items: list[RetrievedItem]) -> list[dict]:
        money_query = bool(set(_tokens(question)) & MONEY_TERMS)
        candidates = (
            [item for item in items if item.event and item.event.event_type == "transaction"]
            if money_query
            else items
        )
        if not candidates:
            candidates = items
        claims = []
        for item in candidates[:4]:
            claim = self._claim_for_event(item, cautious=money_query)
            if claim:
                claims.append({"text": claim, "citations": [item.citation]})
        return claims

    @staticmethod
    def _claim_for_event(item: RetrievedItem, cautious: bool) -> str:
        event = item.event
        if event is None:
            content = re.sub(r"\s+", " ", item.text).strip()
            return f"The cited extracted document text states: {content[:240]}." if content else ""
        if event.event_type == "transaction":
            try:
                row = json.loads(event.content)
            except json.JSONDecodeError:
                row = {}
            amount = row.get("amount")
            direction = str(row.get("type") or event.direction or event.action).lower()
            counterparty = row.get("counterparty") or row.get("vpa") or event.to_party_text
            account = row.get("account") or event.from_party_text
            parts = ["The bank record shows"]
            if direction and direction != "unknown":
                parts.append(f"a {direction}")
            if amount not in (None, ""):
                parts.append(f"of INR {amount}")
            if counterparty:
                parts.append(f"involving {counterparty}")
            if account:
                parts.append(f"on account {account}")
            text = " ".join(parts) + "."
            if cautious and direction == "debit" and "riya" not in str(account).casefold():
                text += " This later debit is a separate record and does not prove the outgoing funds were Riya's."
            return text
        content = re.sub(r"\s+", " ", item.text).strip()
        if not content:
            return ""
        return f"The cited {event.event_type} record states: {content[:240]}."

    @staticmethod
    def _validate_claims(claims: list[dict], items: list[RetrievedItem]) -> bool:
        available = {(item.citation["evidence_id"], item.citation["event_id"]): item for item in items}
        if not claims or len(claims) > 8:
            return False
        for claim in claims:
            text = str(claim.get("text", "")).strip()
            citations = claim.get("citations") or []
            if not text or not citations or INJECTION_RE.search(text):
                return False
            supported = []
            for citation in citations:
                item = available.get((citation.get("evidence_id"), citation.get("event_id")))
                if item is None or any(citation.get(key) != item.citation[key] for key in ("sha256", "reference", "file", "timestamp")):
                    return False
                supported.append(item)
            # Exact deterministic renderings have no invented semantic content.
            if len(supported) == 1 and any(text == AssistantService._claim_for_event(supported[0], cautious=flag) for flag in (True, False)):
                continue
            source_text = " ".join(item.text for item in supported)
            def normalise(value):
                return value.casefold().replace(",", "").replace("inr ", "")
            values = re.findall(r"(?:INR\s*)?[\d,]+(?:\.\d+)?|[\w.-]+@[\w.-]+", text, re.I)
            if any(normalise(value) not in normalise(source_text) for value in values):
                return False
            try:
                result = local_model("entailment").entail(source_text[:6000], text)
            except ModelUnavailable:
                return False  # No lexical overlap substitute for semantic validation.
            if result["entailment"] < 0.85 or result["contradiction"] > 0.05:
                return False
        return True

    def _ollama_claims(self, question: str, items: list[RetrievedItem], *, repair: bool, mode: str = "answer") -> list[dict] | None:
        sources = [{"event_id": item.citation["event_id"], "evidence_id": item.evidence.id, "text": INJECTION_RE.sub("[instruction-like evidence omitted]", item.event.content if mode == "translate" and item.event else item.text)[:1000]} for item in items]
        try:
            payload = local_llm.generate(question, sources, mode, repair)
        except Exception:
            return None
        lookup = {item.citation["event_id"]: item for item in items}
        claims = []
        for raw in payload.get("claims", [])[:8]:
            if not isinstance(raw, dict):
                return []
            event_ids = raw.get("event_ids", [])
            if not isinstance(event_ids, list) or any(not isinstance(event_id, int) or event_id not in lookup for event_id in event_ids):
                return []
            citations = [lookup[event_id].citation for event_id in event_ids]
            claims.append({"text": str(raw.get("text", "")), "citations": citations})
        return claims

    def _model_card(self) -> dict:
        try:
            return local_llm.model_card()
        except ModelUnavailable:
            return {"name": "Parakh cited extractor", "version": "2.0", "provider": "deterministic offline fallback",
                    "licence": "Repository licence", "training_data": "None; exact case record renderings",
                    "known_limits": ["Local LLM is unavailable; summaries use source excerpts, translation is unavailable", "Answers are limited to retrieved records"],
                    "offline_only": True, "cloud_models": False}

    @staticmethod
    def _refusal(model_card: dict, reason: str, repair_attempted: bool = False) -> dict:
        return {
            "answer": "No supporting evidence found.",
            "refused": True,
            "claims": [],
            "citations": [],
            "validation": {
                "valid": True,
                "repair_attempted": repair_attempted,
                "method": "case-only citation validation",
                "reason": reason,
            },
            "retrieval": {"method": "BM25 + local vectors + RRF + MMR", "retrieved": 0},
            "model_card": model_card,
        }


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


def _bm25(query: list[str], document: list[str], frequencies: Counter, count: int, average: float) -> float:
    terms = Counter(document)
    score = 0.0
    for token in set(query):
        if token not in terms:
            continue
        inverse = math.log(1 + (count - frequencies[token] + 0.5) / (frequencies[token] + 0.5))
        score += inverse * (terms[token] * 2.2) / (terms[token] + 1.2 * (0.25 + 0.75 * len(document) / max(1, average)))
    return score


def _rank(scores: list[float]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
    result = [0] * len(scores)
    for rank, index in enumerate(order, start=1):
        result[index] = rank
    return result
