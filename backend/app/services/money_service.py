from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime

import networkx as nx
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.services.pattern_service import benjamini_hochberg

SEED = 71026
TIME_LIMIT_SECONDS = 1.0
FDR_ALPHA = 0.05
RULES = {"fifo", "proportional", "lifo"}


class MoneyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyse(self, case_id: int, rule: str = "fifo") -> dict:
        if rule not in RULES:
            raise ValueError("Tracing rule must be fifo, proportional or lifo")
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
        transactions: list[dict] = []
        for event in (item for item in events if item.event_type == "transaction"):
            item = self._normalise(event, evidence[event.evidence_id])
            if item is not None:
                transactions.append(item)
        documents = [item for item in events if item.event_type == "document"]
        for item in transactions:
            item["representations"] = [item["support"]]
            for document in documents:
                source = evidence[document.evidence_id]
                if item["utr"] in document.content and source.filename.casefold().endswith(".pdf"):
                    item["representations"].append(
                        {
                            "evidence_id": source.id,
                            "file": source.filename,
                            "reference": document.raw_ref,
                            "timestamp": document.timestamp_utc,
                            "sha256": source.sha256,
                        }
                    )
        graph, transfers = self._flow_graph(transactions)
        pass_through = self._pass_through(transactions)
        allocations, solver = self._allocate(transactions, rule)
        return {
            "transactions": transactions,
            "graph": {
                "nodes": [{"id": node} for node in graph.nodes],
                "edges": transfers,
                "choke_points": self._choke_points(graph),
                "cycles": [cycle for cycle in nx.simple_cycles(graph) if len(cycle) > 1],
                "gnn_mule_detection": "planned_t3",
            },
            "patterns": {
                "pass_through": pass_through,
                "fan_in": self._fan(graph, incoming=True),
                "fan_out": self._fan(graph, incoming=False),
                "benford": self._benford(transactions),
            },
            "tracing": {
                "rule": rule,
                "available_rules": sorted(RULES),
                "directly_shown": [
                    {
                        "text": f"{item['direction'].title()} INR {item['amount']:.2f} in {item['account']} with {item['counterparty']}",
                        "support": item["support"],
                    }
                    for item in transactions
                ],
                "possible": allocations,
                "unexplained": [
                    "Allocation of a particular incoming payment to a later outgoing transfer is not shown by the records.",
                    "Legal ownership or control of recipient accounts is not established by transaction rows alone.",
                    "Cash withdrawals and transfers outside the uploaded statement window remain unexplained.",
                ],
                "solver": solver,
                "warning": "Possible allocations are accounting assumptions. They do not establish that outgoing money was Riya's.",
            },
            "anomalies": self._transaction_anomalies(transactions),
            "assumptions": {
                "seed": SEED,
                "time_limit_seconds": TIME_LIMIT_SECONDS,
                "currency_minor_unit": "paise",
                "conservation": True,
                "timing": "an inflow must precede an allocated outflow",
            },
        }

    @staticmethod
    def _normalise(event: Event, evidence: Evidence) -> dict | None:
        try:
            row = json.loads(event.content)
        except (json.JSONDecodeError, TypeError):
            return None
        direction = str(row.get("type") or event.direction or event.action).casefold()
        if direction not in {"credit", "debit"}:
            return None
        try:
            amount = float(str(row.get("amount", "0")).replace(",", ""))
            balance = float(str(row.get("balance", "0")).replace(",", ""))
        except ValueError:
            return None
        return {
            "event_id": event.id,
            "timestamp": event.timestamp_utc,
            "account": str(row.get("account") or "unknown"),
            "counterparty": str(row.get("counterparty") or "unknown"),
            "direction": direction,
            "amount": amount,
            "currency": str(row.get("currency") or "INR"),
            "utr": str(row.get("utr") or "not supplied"),
            "vpa": str(row.get("vpa") or (row.get("counterparty") if "@" in str(row.get("counterparty")) else "")),
            "ifsc": str(row.get("ifsc") or ""),
            "balance": balance,
            "support": {
                "evidence_id": evidence.id,
                "file": evidence.filename,
                "reference": event.raw_ref,
                "timestamp": event.timestamp_utc,
                "sha256": evidence.sha256,
            },
        }

    @staticmethod
    def _flow_graph(transactions: list[dict]) -> tuple[nx.DiGraph, list[dict]]:
        graph = nx.DiGraph()
        credits_by_utr = {item["utr"]: item for item in transactions if item["direction"] == "credit"}
        transfers: list[dict] = []
        seen: set[str] = set()
        for item in transactions:
            if item["direction"] != "debit":
                continue
            paired = credits_by_utr.get(item["utr"])
            target = paired["account"] if paired else item["counterparty"]
            source = item["account"]
            edge_id = item["utr"]
            if edge_id in seen:
                continue
            seen.add(edge_id)
            amount = int(round(item["amount"] * 100))
            graph.add_edge(source, target, capacity=amount, amount=item["amount"], utr=edge_id)
            transfers.append(
                {
                    "source": source,
                    "target": target,
                    "amount": item["amount"],
                    "utr": edge_id,
                    "support": [item["support"], paired["support"]] if paired else [item["support"]],
                }
            )
        return graph, transfers

    @staticmethod
    def _pass_through(transactions: list[dict]) -> list[dict]:
        by_account: defaultdict[str, list[dict]] = defaultdict(list)
        for item in transactions:
            by_account[item["account"]].append(item)
        output = []
        for account, rows in by_account.items():
            credits = [item for item in rows if item["direction"] == "credit" and item["timestamp"]]
            debits = [item for item in rows if item["direction"] == "debit" and item["timestamp"]]
            for debit in debits:
                eligible = [credit for credit in credits if credit["timestamp"] <= debit["timestamp"]]
                if not eligible:
                    continue
                latest = max(eligible, key=lambda item: item["timestamp"])
                minutes = (debit["timestamp"] - latest["timestamp"]).total_seconds() / 60
                if minutes <= 30:
                    output.append(
                        {
                            "account": account,
                            "minutes": round(minutes, 2),
                            "incoming_amount": latest["amount"],
                            "outgoing_amount": debit["amount"],
                            "support": [latest["support"], debit["support"]],
                            "caveat": "Close timing shows pass-through behaviour, not ownership of the outgoing funds.",
                        }
                    )
        return output

    def _allocate(self, transactions: list[dict], rule: str) -> tuple[list[dict], dict]:
        accounts = sorted({item["account"] for item in transactions})
        allocations: list[dict] = []
        started = time.monotonic()
        incomplete = False
        for account in accounts:
            credits = [item for item in transactions if item["account"] == account and item["direction"] == "credit"]
            debits = [item for item in transactions if item["account"] == account and item["direction"] == "debit"]
            if not credits or not debits:
                continue
            if rule == "proportional":
                allocations.extend(self._proportional(account, credits, debits))
            else:
                try:
                    allocations.extend(self._min_cost_allocation(account, credits, debits, rule))
                except nx.NetworkXError:
                    allocations.extend(self._greedy_allocation(account, credits, debits, rule))
                if time.monotonic() - started > TIME_LIMIT_SECONDS:
                    incomplete = True
                    break
        solver = self._cp_sat_validate(allocations, transactions, started)
        solver["incomplete"] = incomplete or solver["incomplete"]
        return allocations, solver

    def _min_cost_allocation(self, account: str, credits: list[dict], debits: list[dict], rule: str) -> list[dict]:
        graph = nx.DiGraph()
        total = min(
            sum(int(round(item["amount"] * 100)) for item in credits),
            sum(int(round(item["amount"] * 100)) for item in debits),
        )
        graph.add_node("source", demand=-total)
        graph.add_node("sink", demand=total)
        ordered = credits if rule == "fifo" else list(reversed(credits))
        order_rank = {credit["event_id"]: rank for rank, credit in enumerate(ordered)}
        for rank, credit in enumerate(ordered):
            node = f"credit:{credit['event_id']}"
            graph.add_node(node, demand=0)
            graph.add_edge(
                "source",
                node,
                capacity=int(round(credit["amount"] * 100)),
                weight=rank * max(1, len(debits) + 1),
            )
        for rank, debit in enumerate(debits):
            node = f"debit:{debit['event_id']}"
            graph.add_node(node, demand=0)
            graph.add_edge(node, "sink", capacity=int(round(debit["amount"] * 100)), weight=rank)
            for credit in credits:
                if credit["timestamp"] and debit["timestamp"] and credit["timestamp"] > debit["timestamp"]:
                    continue
                graph.add_edge(
                    f"credit:{credit['event_id']}",
                    node,
                    capacity=min(int(round(credit["amount"] * 100)), int(round(debit["amount"] * 100))),
                    weight=rank * (len(credits) - order_rank[credit["event_id"]]),
                )
        _, flow = nx.network_simplex(graph)
        output = []
        credit_map = {item["event_id"]: item for item in credits}
        debit_map = {item["event_id"]: item for item in debits}
        for credit_id, credit in credit_map.items():
            for target, value in flow[f"credit:{credit_id}"].items():
                if not target.startswith("debit:") or not value:
                    continue
                debit = debit_map[int(target.split(":", 1)[1])]
                output.append(self._allocation(account, credit, debit, value, rule))
        return output

    def _greedy_allocation(self, account: str, credits: list[dict], debits: list[dict], rule: str) -> list[dict]:
        output = []
        ordered = credits if rule == "fifo" else list(reversed(credits))
        remaining = {item["event_id"]: int(round(item["amount"] * 100)) for item in ordered}
        for debit in debits:
            needed = int(round(debit["amount"] * 100))
            for credit in ordered:
                if credit["timestamp"] and debit["timestamp"] and credit["timestamp"] > debit["timestamp"]:
                    continue
                value = min(needed, remaining[credit["event_id"]])
                if value:
                    output.append(self._allocation(account, credit, debit, value, rule))
                    remaining[credit["event_id"]] -= value
                    needed -= value
                if not needed:
                    break
        return output

    def _proportional(self, account: str, credits: list[dict], debits: list[dict]) -> list[dict]:
        output = []
        remaining = {item["event_id"]: int(round(item["amount"] * 100)) for item in credits}
        for debit in debits:
            eligible = [item for item in credits if not item["timestamp"] or not debit["timestamp"] or item["timestamp"] <= debit["timestamp"]]
            total = sum(remaining[item["event_id"]] for item in eligible)
            needed = min(int(round(debit["amount"] * 100)), total)
            assigned = 0
            for index, credit in enumerate(eligible):
                if index == len(eligible) - 1:
                    value = needed - assigned
                else:
                    value = min(remaining[credit["event_id"]], round(needed * remaining[credit["event_id"]] / max(1, total)))
                if value:
                    output.append(self._allocation(account, credit, debit, value, "proportional"))
                    remaining[credit["event_id"]] -= value
                    assigned += value
        return output

    @staticmethod
    def _allocation(account: str, credit: dict, debit: dict, value: int, rule: str) -> dict:
        return {
            "account": account,
            "rule": rule,
            "amount": value / 100,
            "from_utr": credit["utr"],
            "to_utr": debit["utr"],
            "from_event_id": credit["event_id"],
            "to_event_id": debit["event_id"],
            "to": debit["counterparty"],
            "support": [credit["support"], debit["support"]],
            "status": "possible under stated assumptions",
        }

    @staticmethod
    def _cp_sat_validate(allocations: list[dict], transactions: list[dict], started: float) -> dict:
        try:
            from ortools.sat.python import cp_model  # type: ignore[import-not-found]
        except ImportError:
            return {
                "engine": "deterministic conservation fallback",
                "status": "fallback",
                "incomplete": False,
                "reason": "OR-Tools CP-SAT is unavailable; the selected allocation rule was applied directly.",
                "seed": SEED,
                "time_limit_seconds": TIME_LIMIT_SECONDS,
            }
        model = cp_model.CpModel()
        variables = []
        for index, allocation in enumerate(allocations):
            value = int(round(allocation["amount"] * 100))
            variables.append(model.new_int_var(value, value, f"allocation_{index}"))
        if variables:
            model.add(sum(variables) <= sum(int(round(item["amount"] * 100)) for item in transactions if item["direction"] == "credit"))
        by_credit: defaultdict[int, list] = defaultdict(list)
        by_debit: defaultdict[int, list] = defaultdict(list)
        for variable, allocation in zip(variables, allocations, strict=True):
            by_credit[allocation["from_event_id"]].append(variable)
            by_debit[allocation["to_event_id"]].append(variable)
        amounts = {item["event_id"]: int(round(item["amount"] * 100)) for item in transactions}
        for event_id, group in by_credit.items():
            model.add(sum(group) <= amounts[event_id])
        for event_id, group in by_debit.items():
            model.add(sum(group) <= amounts[event_id])
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.01, TIME_LIMIT_SECONDS - (time.monotonic() - started))
        solver.parameters.random_seed = SEED
        status = solver.solve(model)
        complete = status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
        return {
            "engine": "OR-Tools CP-SAT",
            "status": solver.status_name(status),
            "incomplete": not complete,
            "reason": "Allocation constraints checked for conservation and non-negative fixed rule allocations.",
            "seed": SEED,
            "time_limit_seconds": TIME_LIMIT_SECONDS,
        }

    @staticmethod
    def _choke_points(graph: nx.DiGraph) -> list[dict]:
        sources = [node for node in graph if graph.in_degree(node) == 0 and graph.out_degree(node)]
        sinks = [node for node in graph if graph.out_degree(node) == 0 and graph.in_degree(node)]
        counts: Counter[str] = Counter()
        for source in sources:
            for sink in sinks:
                if not nx.has_path(graph, source, sink):
                    continue
                _, partition = nx.minimum_cut(graph, source, sink, capacity="capacity")
                reachable, blocked = partition
                for left in reachable:
                    for right in graph.successors(left):
                        if right in blocked and left not in {source}:
                            counts[left] += 1
        return [{"account": node, "cut_paths": count, "method": "max-flow/min-cut"} for node, count in counts.most_common()]

    @staticmethod
    def _fan(graph: nx.DiGraph, *, incoming: bool) -> list[dict]:
        output = []
        for node in graph:
            count = graph.in_degree(node) if incoming else graph.out_degree(node)
            if count >= 2:
                output.append({"account": node, "count": count, "type": "fan-in" if incoming else "fan-out"})
        return output

    @staticmethod
    def _benford(transactions: list[dict]) -> dict:
        digits = [int(str(item["amount"]).lstrip("0." )[0]) for item in transactions if item["amount"] > 0]
        if len(digits) < 50:
            return {"status": "weak heuristic", "sample_size": len(digits), "result": "insufficient sample", "caveat": "Benford analysis is unreliable on small or constrained transaction sets."}
        observed = Counter(digits)
        deviation = sum(abs(observed[digit] / len(digits) - math.log10(1 + 1 / digit)) for digit in range(1, 10))
        return {"status": "weak heuristic", "sample_size": len(digits), "absolute_deviation": round(deviation, 4), "caveat": "A Benford deviation does not establish manipulation."}

    @staticmethod
    def _transaction_anomalies(transactions: list[dict]) -> list[dict]:
        from sklearn.ensemble import IsolationForest

        if len(transactions) < 8:
            return []
        known: set[str] = set()
        features = []
        labels = []
        previous_credit: dict[str, datetime] = {}
        for item in transactions:
            timestamp = item["timestamp"]
            hour = timestamp.hour if timestamp else 0
            novelty = float(item["counterparty"] not in known)
            known.add(item["counterparty"])
            hold = 24.0
            if item["direction"] == "credit" and timestamp:
                previous_credit[item["account"]] = timestamp
            elif timestamp and item["account"] in previous_credit:
                hold = min(24.0, (timestamp - previous_credit[item["account"]]).total_seconds() / 3600)
            features.append([math.log1p(item["amount"]), hour, novelty, hold])
            labels.append(["amount", "hour", "counterparty novelty", "hold time"])
        model = IsolationForest(random_state=SEED, n_estimators=100, contamination=0.15).fit(features)
        scores = -model.score_samples(features)
        medians = np.median(features, axis=0)
        mads = np.median(np.abs(np.asarray(features) - medians), axis=0)
        minimum_scales = np.asarray([0.5, 1.0, 1.0, 1.0])
        robust_distances = np.max(
            np.abs(np.asarray(features) - medians)
            / np.maximum(minimum_scales, 1.4826 * mads),
            axis=1,
        )
        p_values = [min(1.0, math.exp(-float(distance))) for distance in robust_distances]
        accepted = benjamini_hochberg(p_values, FDR_ALPHA)
        output = []
        for item, feature, score, p_value, significant, names in zip(transactions, features, scores, p_values, accepted, labels, strict=True):
            if not significant:
                continue
            reason_index = int(np.argmax(np.abs(np.asarray(feature) - medians)))
            output.append({
                "title": "Unusual transfer",
                "reason": f"Largest feature deviation: {names[reason_index]}; Isolation Forest score {score:.3f}.",
                "confidence": round(1 - p_value, 4),
                "p_value": round(p_value, 4),
                "fdr_alpha": FDR_ALPHA,
                "support": item["support"],
                "caveat": "An unusual transfer is a review lead, not proof of laundering or fraud.",
            })
        return output
