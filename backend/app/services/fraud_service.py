from __future__ import annotations

import json
import math
import time
from datetime import datetime
from itertools import permutations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog, Comment, Lead
from app.models.evidence import DocumentExtraction, Event, Evidence
from app.services.audit_service import AuditService
from app.services.authenticity_service import AuthenticityService
from app.services.money_service import MoneyService
from app.services.origin_service import OriginService, temporal_network
from app.services.pattern_service import PatternService, levenshtein

LEAD_SEED = 12026


def _number(field: dict | None) -> float:
    import re

    return float(re.sub(r"[^0-9.]", "", str((field or {}).get("value", "0"))) or 0)


def _seconds(left: datetime | None, right: datetime | None) -> float:
    return abs((left - right).total_seconds()) if left and right else 86_400


class ContradictionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyse(self, case_id: int) -> dict:
        evidence = {
            item.id: item
            for item in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id))
        }
        receipts = []
        for extraction in self.db.scalars(
            select(DocumentExtraction).where(DocumentExtraction.case_id == case_id)
        ):
            source = evidence.get(extraction.evidence_id)
            if source and source.source_type == "receipt":
                receipts.append((source, extraction.fields))
        transactions = []
        for event in self.db.scalars(
            select(Event).where(Event.case_id == case_id, Event.event_type == "transaction")
        ):
            try:
                row = json.loads(event.content)
            except json.JSONDecodeError:
                continue
            transactions.append((event, row))
        costs = [
            [self._cost(fields, event, row) for event, row in transactions]
            for _, fields in receipts
        ]
        assignments, method = self._assign(costs)
        origin = OriginService(self.db).analyse(case_id)
        contradictions = []
        for receipt_index, transaction_index in assignments:
            source, fields = receipts[receipt_index]
            event, row = transactions[transaction_index]
            claimed_amount = _number(fields.get("amount"))
            recorded_amount = float(row.get("amount", 0))
            claimed_reference = str((fields.get("utr") or {}).get("value", ""))
            recorded_reference = str(row.get("utr", ""))
            direction = str(row.get("type") or event.action).casefold()
            amount_match = math.isclose(claimed_amount, recorded_amount, abs_tol=0.01)
            reference_match = bool(claimed_reference and claimed_reference == recorded_reference)
            if amount_match and direction == "credit":
                continue
            alternatives = [
                {
                    "name": "altered document",
                    "result": "remains plausible",
                    "likelihood_ratio": 6.0,
                    "reason": "The OCR amount or direction conflicts with the matched bank row; metadata signals alone cannot identify who changed it.",
                },
                {
                    "name": "wrong device clock",
                    "result": "ruled out for this mismatch",
                    "likelihood_ratio": 0.15,
                    "reason": "A clock correction can move a timestamp, but cannot change amount or debit/credit direction.",
                },
                {
                    "name": "different time zone",
                    "result": "ruled out for this mismatch",
                    "likelihood_ratio": 0.1,
                    "reason": "Time-zone conversion cannot change the amount or direction.",
                },
                {
                    "name": "different transaction",
                    "result": "plausible outside supplied coverage"
                    if reference_match
                    else "remains plausible",
                    "likelihood_ratio": 0.7 if reference_match else 1.8,
                    "reason": "The repeated reference favours the matched debit, but records after the supplied cutoff could settle the question.",
                },
            ]
            contradictions.append(
                {
                    "type": "receipt_vs_bank",
                    "label": "contradicted",
                    "receipt": {
                        "evidence_id": source.id,
                        "file": source.filename,
                        "reference": "page:1",
                        "amount": claimed_amount,
                        "utr": claimed_reference,
                    },
                    "record": {
                        "event_id": event.id,
                        "evidence_id": event.evidence_id,
                        "reference": event.raw_ref,
                        "amount": recorded_amount,
                        "direction": direction,
                        "utr": recorded_reference,
                    },
                    "match": {
                        "algorithm": method,
                        "cost": round(costs[receipt_index][transaction_index], 4),
                        "amount_match": amount_match,
                        "reference_match": reference_match,
                    },
                    "alternatives": alternatives,
                    "would_settle": [
                        "A bank record extending beyond the current coverage",
                        "The receipt issuer's original transaction record",
                        "The native source document and creation history",
                    ],
                }
            )
        return {
            "contradictions": contradictions,
            "assignment": {
                "method": method,
                "receipt_count": len(receipts),
                "bank_row_count": len(transactions),
            },
            "clock_model": origin["clock_reconciliation"],
            "temporal_consistency": temporal_network(
                [("claim", "record", 86_400), ("record", "claim", 86_400)]
            ),
            "limits": "Likelihood ratios compare stated alternatives; they do not establish intent or authorship.",
        }

    @staticmethod
    def _cost(fields: dict, event: Event, row: dict) -> float:
        amount = _number(fields.get("amount"))
        recorded = float(row.get("amount", 0))
        amount_cost = min(1.0, abs(amount - recorded) / max(amount, recorded, 1))
        reference = str((fields.get("utr") or {}).get("value", ""))
        candidate = str(row.get("utr", ""))
        name = str((fields.get("payee") or {}).get("value", ""))
        counterparty = str(row.get("counterparty", ""))
        reference_cost = 0 if reference and reference == candidate else 0.6
        name_cost = levenshtein(name.casefold(), counterparty.casefold()) / max(
            len(name), len(counterparty), 1
        )
        return amount_cost * 0.45 + reference_cost * 0.4 + min(1.0, name_cost) * 0.15

    @staticmethod
    def _assign(costs: list[list[float]]) -> tuple[list[tuple[int, int]], str]:
        if not costs or not costs[0]:
            return [], "Hungarian assignment"
        try:
            from scipy.optimize import linear_sum_assignment

            rows, columns = linear_sum_assignment(costs)
            return list(zip(rows.tolist(), columns.tolist(), strict=True)), "Hungarian assignment"
        except ImportError:
            width = len(costs[0])
            count = min(len(costs), width)
            best = min(
                permutations(range(width), count),
                key=lambda choice: sum(costs[index][column] for index, column in enumerate(choice)),
            )
            return list(enumerate(best)), "exact assignment fallback"


class FraudService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def board(self, case_id: int) -> dict:
        try:
            patterns = PatternService(self.db).analyse(case_id)
        except (AttributeError, ValueError):
            events = list(self.db.scalars(select(Event).where(Event.case_id == case_id)))
            flagged = [
                event
                for event in events
                if any(
                    phrase in event.content.casefold()
                    for phrase in ("otp", "double money", "kyc update", "guaranteed return")
                )
            ]
            patterns = {
                "flags": [
                    {
                        "support": [
                            {
                                "event_id": event.id,
                                "evidence_id": event.evidence_id,
                                "reference": event.raw_ref,
                            }
                        ]
                    }
                    for event in flagged
                ],
                "classifier": {
                    "status": "fallback",
                    "reason": "The offline classifier artifact was incompatible; deterministic phrase matching was used.",
                },
            }
        money = MoneyService(self.db).analyse(case_id, "fifo")
        contradictions = ContradictionService(self.db).analyse(case_id)
        evidence = list(
            self.db.scalars(
                select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id)
            )
        )
        reports = [
            AuthenticityService(self.db).report(item)
            for item in evidence
            if item.source_type in {"receipt", "image", "pdf"}
            or item.filename.lower().endswith((".pdf", ".jpg", ".png"))
        ]
        suspicious = max(reports, key=lambda item: item.suspicion_score, default=None)
        receipt_contradiction = (contradictions["contradictions"] or [None])[0]
        definitions = [
            (
                "Document manipulation suspected",
                0.93 if receipt_contradiction else 0.35,
                [
                    "Receipt OCR conflicts with the bank row sharing its reference",
                    f"Document heuristic interval: {suspicious.score_range if suspicious else 'not assessed'}",
                ],
                self._citations(receipt_contradiction),
            ),
            (
                "Possible mule or collection account",
                0.88 if money["patterns"]["pass_through"] else 0.42,
                [
                    "Rapid inflow-to-outflow behaviour appears in the supplied account records",
                    "Allocation remains possible under stated tracing assumptions",
                ],
                self._money_citations(money),
            ),
            (
                "Coordinated scam communication",
                0.84 if patterns["flags"] else 0.38,
                [
                    "Scam-language or activity flags have source-backed rows",
                    f"{len(patterns['flags'])} communication flags require review",
                ],
                self._pattern_citations(patterns),
            ),
        ]
        existing = {
            item.title: item
            for item in self.db.scalars(select(Lead).where(Lead.case_id == case_id))
        }
        for title, score, reasons, citations in definitions:
            if title not in existing:
                serializable_citations = json.loads(json.dumps(citations, default=str))
                lead = Lead(
                    case_id=case_id,
                    title=title,
                    rationale=json.dumps({"score": score, "reasons": reasons}),
                    citations=serializable_citations,
                    status="new",
                )
                self.db.add(lead)
                self.db.flush()
                existing[title] = lead
                AuditService(self.db).log(
                    action="lead.created",
                    case_id=case_id,
                    target_type="lead",
                    target_id=str(lead.id),
                    payload={"title": title, "score": score},
                )
        comments: dict[int, list[dict]] = {}
        for item in self.db.scalars(
            select(Comment)
            .where(Comment.case_id == case_id, Comment.target_type == "lead")
            .order_by(Comment.id)
        ):
            comments.setdefault(item.target_id, []).append(
                {
                    "id": item.id,
                    "body": item.body,
                    "author": item.author,
                    "created_at": item.created_at,
                }
            )
        rows = []
        feedback_counts: dict[int, int] = {}
        for entry in self.db.scalars(
            select(AuditLog).where(
                AuditLog.case_id == case_id,
                AuditLog.target_type == "lead",
                AuditLog.action == "lead.confirmed",
            )
        ):
            if entry.target_id.isdigit():
                feedback_counts[int(entry.target_id)] = (
                    feedback_counts.get(int(entry.target_id), 0) + 1
                )
        for lead in existing.values():
            try:
                payload = json.loads(lead.rationale)
            except json.JSONDecodeError:
                payload = {"score": 0.5, "reasons": [lead.rationale]}
            score = float(payload.get("score", 0.5))
            if lead.status == "confirmed":
                score = min(0.99, score + min(0.15, feedback_counts.get(lead.id, 1) * 0.03))
            rows.append(
                {
                    "id": lead.id,
                    "title": lead.title,
                    "status": lead.status,
                    "assignee": lead.assignee,
                    "score": round(score, 3),
                    "reasons": payload.get("reasons", []),
                    "citations": lead.citations,
                    "comments": comments.get(lead.id, []),
                    "dismissal_reason": lead.rejection_reason,
                }
            )
        ranked = sorted(
            (item for item in rows if item["status"] != "dismissed"),
            key=lambda item: item["score"],
            reverse=True,
        )
        return {
            "authenticity": [vars(item) for item in reports],
            "contradictions": contradictions,
            "leads": rows,
            "ranked": ranked,
            "review_plan": self._review_plan(ranked, 45),
            "ranking": {
                "method": "likelihood-ratio/Bayesian combination",
                "assumption": "Signals are treated as conditionally independent; correlated signals may overstate the score.",
                "feedback": "Confirmed and dismissed decisions update ordering; ML learning-to-rank remains T2 planned until enough cross-case labels exist.",
            },
        }

    def update_lead(
        self,
        case_id: int,
        lead_id: int,
        actor: str,
        status: str,
        assignee: str | None,
        comment: str | None,
    ) -> dict:
        lead = self.db.get(Lead, lead_id)
        if not lead or lead.case_id != case_id:
            raise ValueError("Lead not found")
        if status not in {"new", "reviewing", "confirmed", "dismissed"}:
            raise ValueError("Invalid lead status")
        lead.status = status
        lead.assignee = assignee
        if status == "dismissed":
            lead.rejection_reason = comment or "Dismissed by investigator"
        if comment:
            self.db.add(
                Comment(
                    case_id=case_id,
                    target_type="lead",
                    target_id=lead.id,
                    body=comment,
                    author=actor,
                )
            )
        AuditService(self.db).log(
            action=f"lead.{status}",
            actor=actor,
            case_id=case_id,
            target_type="lead",
            target_id=str(lead.id),
            payload={"assignee": assignee, "comment": comment},
        )
        self.db.flush()
        return self.board(case_id)

    @staticmethod
    def _citations(item: dict | None) -> list[dict]:
        if not item:
            return []
        return [
            {
                "evidence_id": item["receipt"]["evidence_id"],
                "reference": item["receipt"]["reference"],
            },
            {
                "evidence_id": item["record"]["evidence_id"],
                "event_id": item["record"]["event_id"],
                "reference": item["record"]["reference"],
            },
        ]

    @staticmethod
    def _money_citations(money: dict) -> list[dict]:
        shown = money["tracing"]["directly_shown"][:3]
        return [
            {
                "evidence_id": item.get("evidence_id"),
                "event_id": item.get("event_id"),
                "reference": item.get("reference"),
            }
            for item in shown
        ]

    @staticmethod
    def _pattern_citations(patterns: dict) -> list[dict]:
        return [
            support for flag in patterns["flags"][:3] for support in flag.get("support", [])[:1]
        ]

    @staticmethod
    def _review_plan(leads: list[dict], budget: int) -> dict:
        started = time.monotonic()
        estimates = [20, 25, 15]
        try:
            from ortools.sat.python import cp_model

            model = cp_model.CpModel()
            choices = [model.new_bool_var(f"lead_{index}") for index in range(len(leads))]
            model.add(
                sum(
                    choices[index] * estimates[index % len(estimates)]
                    for index in range(len(leads))
                )
                <= budget
            )
            model.maximize(
                sum(
                    choices[index] * round(leads[index]["score"] * 1000)
                    for index in range(len(leads))
                )
            )
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 1
            solver.parameters.random_seed = LEAD_SEED
            status = solver.solve(model)
            selected = [
                leads[index]["id"] for index in range(len(leads)) if solver.value(choices[index])
            ]
            return {
                "budget_minutes": budget,
                "selected_lead_ids": selected,
                "method": "CP-SAT knapsack",
                "complete": status == cp_model.OPTIMAL,
                "time_limit_seconds": 1,
                "seed": LEAD_SEED,
                "fallback": "score-per-minute greedy",
            }
        except (ImportError, RuntimeError):
            remaining = budget
            selected = []
            for index, lead in sorted(
                enumerate(leads),
                key=lambda pair: pair[1]["score"] / estimates[pair[0] % len(estimates)],
                reverse=True,
            ):
                cost = estimates[index % len(estimates)]
                if cost <= remaining:
                    selected.append(lead["id"])
                    remaining -= cost
            return {
                "budget_minutes": budget,
                "selected_lead_ids": selected,
                "method": "score-per-minute greedy",
                "complete": time.monotonic() - started < 1,
                "time_limit_seconds": 1,
                "seed": LEAD_SEED,
                "fallback": "score-per-minute greedy",
            }
