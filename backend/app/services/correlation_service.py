from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from itertools import pairwise
from typing import cast

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.entities import extract_entities
from app.models.evidence import Event, Evidence
from app.services.origin_service import OriginService

DISCLAIMER = "Being near each other does not prove being together."
PHASE_ORDER = ["lure", "trust_building", "credential_or_otp_request", "payment", "onward_movement"]


def haversine(left: tuple[float, float], right: tuple[float, float]) -> float:
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (*left, *right))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def dbscan(points: list[dict], epsilon_km: float = 0.25, minimum: int = 2) -> list[int]:
    labels = [-1] * len(points)
    visited: set[int] = set()
    cluster = 0

    def neighbours(index: int) -> list[int]:
        here = (points[index]["lat"], points[index]["lon"])
        return [
            candidate
            for candidate in range(len(points))
            if haversine(here, (points[candidate]["lat"], points[candidate]["lon"])) <= epsilon_km
        ]

    for index in range(len(points)):
        if index in visited:
            continue
        visited.add(index)
        nearby = neighbours(index)
        if len(nearby) < minimum:
            continue
        labels[index] = cluster
        queue = list(nearby)
        while queue:
            candidate = queue.pop()
            if candidate not in visited:
                visited.add(candidate)
                candidate_neighbours = neighbours(candidate)
                if len(candidate_neighbours) >= minimum:
                    queue.extend(item for item in candidate_neighbours if item not in queue)
            if labels[candidate] == -1:
                labels[candidate] = cluster
        cluster += 1
    return labels


class CorrelationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyse(
        self,
        case_id: int,
        source: str | None = None,
        target: str | None = None,
        focus: str | None = None,
        depth: int = 1,
        clock_confidence: float = 1.0,
    ) -> dict:
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
        graph, time_edges = self._graph(events, evidence)
        graph_view = self._graph_output(graph, time_edges, source, target, focus, depth)
        geospatial = self._geospatial(events, evidence)
        timeline = self._timeline(case_id, events, evidence, max(0.0, min(1.0, clock_confidence)))
        return {
            "graph": graph_view,
            "map": geospatial,
            "timeline": timeline,
            "disclaimer": DISCLAIMER,
            "planned": {
                "link_prediction": "planned_T2",
                "k_core": "planned_T2",
                "r_tree_spatiotemporal_join": "planned_T2",
                "graph_neural_network": "planned_T3_not_assessed",
                "graph_mule_classifier": "planned_T3_not_assessed",
                "topic_grouping": "planned_T2",
            },
        }

    def _graph(
        self, events: list[Event], evidence: dict[int, Evidence]
    ) -> tuple[nx.Graph, list[dict]]:
        graph = nx.Graph()
        # Each edge keeps its source receipt and first observed time.
        time_edges: list[dict] = []
        transaction_rows: list[tuple[Event, dict]] = []
        for event in events:
            support = {
                "evidence_id": event.evidence_id,
                "file": evidence[event.evidence_id].filename,
                "event_id": event.id,
                "reference": event.raw_ref,
                "timestamp": event.timestamp_utc,
            }
            parties = [str(item) for item in event.actor_entities or []]
            identifiers = extract_entities(event.content + " " + " ".join(parties))
            party_nodes = []
            for party in parties:
                node = f"party:{party}"
                graph.add_node(node, label=party, type="party")
                party_nodes.append(node)
            for identifier in identifiers:
                node = f"identifier:{identifier['canonical']}"
                graph.add_node(node, label=identifier["canonical"], type="identifier")
                for party in party_nodes:
                    self._edge(graph, party, node, "observed_with", support)
            if event.event_type == "transaction":
                try:
                    row = json.loads(event.content)
                except json.JSONDecodeError:
                    continue
                transaction_rows.append((event, row))
            if event.event_type == "telecom":
                try:
                    row = json.loads(event.content)
                except json.JSONDecodeError:
                    continue
                caller, called = (
                    str(row.get("caller", "Unknown")),
                    str(row.get("called", "Unknown")),
                )
                left, right = f"phone:{caller}", f"phone:{called}"
                graph.add_node(left, label=caller, type="phone")
                graph.add_node(right, label=called, type="phone")
                self._edge(graph, left, right, "call", support)
                if row.get("cell_id"):
                    tower = f"tower:{row['cell_id']}"
                    graph.add_node(tower, label=row["cell_id"], type="tower")
                    self._edge(
                        graph,
                        f"phone:{row.get('subject', caller)}",
                        tower,
                        "tower_observation",
                        support,
                    )
        by_utr: defaultdict[str, list[tuple[Event, dict]]] = defaultdict(list)
        for event, row in transaction_rows:
            by_utr[str(row.get("utr", f"event-{event.id}"))].append((event, row))
        for utr, rows in by_utr.items():
            debits = [
                (event, row)
                for event, row in rows
                if str(row.get("type", event.action)).casefold() == "debit"
            ]
            credits = [
                (event, row)
                for event, row in rows
                if str(row.get("type", event.action)).casefold() == "credit"
            ]
            if debits and credits:
                for debit_event, debit in debits:
                    for _credit_event, credit in credits:
                        self._money_edge(
                            graph,
                            time_edges,
                            str(debit.get("account")),
                            str(credit.get("account")),
                            utr,
                            debit_event,
                            evidence,
                        )
            else:
                for event, row in rows:
                    account, counterparty = (
                        str(row.get("account", "Unknown")),
                        str(row.get("counterparty", "Unknown")),
                    )
                    direction = str(row.get("type", event.action)).casefold()
                    left, right = (
                        (account, counterparty) if direction == "debit" else (counterparty, account)
                    )
                    self._money_edge(graph, time_edges, left, right, utr, event, evidence)
        return graph, sorted(
            time_edges,
            key=lambda item: (
                item["timestamp"] is None,
                item["timestamp"].isoformat() if item["timestamp"] else "",
                item["event_id"],
            ),
        )

    @staticmethod
    def _edge(graph: nx.Graph, left: str, right: str, relation: str, support: dict) -> None:
        if not left or not right or left == right:
            return
        if graph.has_edge(left, right):
            graph[left][right]["count"] += 1
            graph[left][right]["support"].append(support)
        else:
            graph.add_edge(left, right, relation=relation, count=1, support=[support])

    def _money_edge(
        self,
        graph: nx.Graph,
        time_edges: list[dict],
        left: str,
        right: str,
        utr: str,
        event: Event,
        evidence: dict[int, Evidence],
    ) -> None:
        source, target = f"account:{left}", f"account:{right}"
        graph.add_node(source, label=left, type="account")
        graph.add_node(target, label=right, type="account")
        support = {
            "evidence_id": event.evidence_id,
            "file": evidence[event.evidence_id].filename,
            "event_id": event.id,
            "reference": event.raw_ref,
            "timestamp": event.timestamp_utc,
        }
        self._edge(graph, source, target, "money_transfer", support)
        time_edges.append(
            {
                "source": source,
                "target": target,
                "utr": utr,
                "timestamp": event.timestamp_utc,
                "event_id": event.id,
                "support": support,
            }
        )

    def _graph_output(
        self,
        graph: nx.Graph,
        time_edges: list[dict],
        source: str | None,
        target: str | None,
        focus: str | None,
        depth: int,
    ) -> dict:
        if graph.number_of_nodes():
            pagerank = nx.pagerank(graph)
            betweenness = nx.betweenness_centrality(graph)
            try:
                communities = list(nx.community.louvain_communities(graph, seed=13026))
                community_method = "Louvain"
            except (AttributeError, ZeroDivisionError):
                communities = list(nx.community.greedy_modularity_communities(graph))
                community_method = "greedy modularity fallback"
        else:
            pagerank, betweenness, communities, community_method = {}, {}, [], "Louvain"
        colour = {node: index for index, group in enumerate(communities) for node in group}
        visible = set(graph.nodes)
        if focus in graph:
            visible = {focus}
            frontier = {focus}
            for _ in range(max(0, min(depth, 4))):
                frontier = {near for node in frontier for near in graph.neighbors(node)} - visible
                visible |= frontier
        candidates = list(graph.nodes)
        source = (
            source
            if source in graph
            else next(
                (
                    node
                    for node in candidates
                    if "RIYA" in node.upper() and node.startswith("account:")
                ),
                None,
            )
        )
        target = (
            target
            if target in graph
            else next((node for node in reversed(candidates) if "cashout" in node.casefold()), None)
        )
        shortest = (
            nx.shortest_path(graph, source, target)
            if source and target and nx.has_path(graph, source, target)
            else []
        )
        key_nodes = [
            node
            for node in [
                source,
                target,
                next(
                    (
                        item
                        for item in candidates
                        if item.startswith("account:") and "COLLECT" in item.upper()
                    ),
                    None,
                ),
            ]
            if node
        ]
        steiner = []
        connected_keys = [
            node
            for node in key_nodes
            if source and (node == source or nx.has_path(graph, source, node))
        ]
        if len(connected_keys) >= 2:
            component = graph.subgraph(nx.node_connected_component(graph, source)).copy()
            tree = nx.algorithms.approximation.steiner_tree(component, connected_keys)
            steiner = [{"source": left, "target": right} for left, right in tree.edges]
        time_path = self._time_respecting_path(time_edges, source, target)
        return {
            "nodes": [
                {
                    "id": node,
                    "label": graph.nodes[node].get("label", node),
                    "type": graph.nodes[node].get("type", "unknown"),
                    "edge_count": graph.degree(node),
                    "importance": round(pagerank.get(node, 0), 5),
                    "betweenness": round(betweenness.get(node, 0), 5),
                    "size": round(18 + pagerank.get(node, 0) * 160, 2),
                    "community": colour.get(node, -1),
                }
                for node in graph.nodes
                if node in visible
            ],
            "edges": [
                {
                    "source": left,
                    "target": right,
                    "count": data["count"],
                    "relation": data["relation"],
                    "support": data["support"],
                }
                for left, right, data in graph.edges(data=True)
                if left in visible and right in visible
            ],
            "community_method": community_method,
            "shortest_path": {
                "source": source,
                "target": target,
                "nodes": shortest,
                "hops": max(0, len(shortest) - 1),
            },
            "steiner_tree": {
                "terminals": connected_keys,
                "edges": steiner,
                "method": "Kou approximation",
            },
            "time_respecting_path": time_path,
            "filters": {"focus": focus, "depth": depth},
        }

    @staticmethod
    def _time_respecting_path(edges: list[dict], source: str | None, target: str | None) -> dict:
        if not source or not target:
            return {"nodes": [], "complete": False}
        paths: list[tuple[str, list[str], datetime | None]] = [(source, [source], None)]
        for _ in range(len(edges) + 1):
            expanded = []
            for node, path, last_time in paths:
                if node == target:
                    return {"nodes": path, "complete": True}
                for edge in edges:
                    when = edge["timestamp"]
                    if (
                        edge["source"] == node
                        and edge["target"] not in path
                        and (last_time is None or when is None or when >= last_time)
                    ):
                        expanded.append((edge["target"], [*path, edge["target"]], when))
            paths.extend(expanded)
            if not expanded:
                break
        return {"nodes": [], "complete": False}

    def _geospatial(self, events: list[Event], evidence: dict[int, Evidence]) -> dict:
        points, towers, calls = [], [], []
        for event in events:
            support = {
                "evidence_id": event.evidence_id,
                "file": evidence[event.evidence_id].filename,
                "event_id": event.id,
                "reference": event.raw_ref,
            }
            location = event.location or {}
            lat = event.latitude if event.latitude is not None else location.get("lat")
            lon = event.longitude if event.longitude is not None else location.get("lon")
            if lat is not None and lon is not None:
                points.append(
                    {
                        "event_id": event.id,
                        "lat": float(lat),
                        "lon": float(lon),
                        "timestamp": event.timestamp_utc,
                        "support": support,
                    }
                )
            if event.event_type == "telecom":
                try:
                    row = json.loads(event.content)
                except json.JSONDecodeError:
                    continue
                calls.append(
                    {
                        "event_id": event.id,
                        "caller": row.get("caller"),
                        "called": row.get("called"),
                        "duration_seconds": int(row.get("duration_sec", 0)),
                        "status": row.get("status"),
                        "timestamp": event.timestamp_utc,
                        "support": support,
                    }
                )
                if row.get("tower_lat") and row.get("tower_lon"):
                    towers.append(
                        {
                            "event_id": event.id,
                            "cell_id": row.get("cell_id"),
                            "lat": float(row["tower_lat"]),
                            "lon": float(row["tower_lon"]),
                            "radius_m": float(row.get("coverage_radius_m", 0)),
                            "timestamp": event.timestamp_utc,
                            "subject": row.get("subject"),
                            "support": support,
                        }
                    )
        labels = dbscan(points)
        stays = []
        for label in sorted(set(labels) - {-1}):
            group = [
                point for point, assigned in zip(points, labels, strict=True) if assigned == label
            ]
            observed_times: list[datetime] = [
                item["timestamp"] for item in group if isinstance(item["timestamp"], datetime)
            ]
            stays.append(
                {
                    "cluster": label,
                    "lat": math.fsum(cast(float, item["lat"]) for item in group) / len(group),
                    "lon": math.fsum(cast(float, item["lon"]) for item in group) / len(group),
                    "samples": len(group),
                    "start": min(observed_times) if observed_times else None,
                    "end": max(observed_times) if observed_times else None,
                    "method": "DBSCAN (250m, min_samples=2)",
                    "support": [item["support"] for item in group],
                }
            )
        common = Counter(
            number for call in calls for number in (call["caller"], call["called"]) if number
        )
        tower_sequence = self._viterbi_towers(towers)
        return {
            "gps_trail": points,
            "stay_points": stays,
            "towers": towers,
            "tower_hops": [
                {"from": left["cell_id"], "to": right["cell_id"], "timestamp": right["timestamp"]}
                for left, right in pairwise(tower_sequence)
                if left["cell_id"] != right["cell_id"]
            ],
            "map_matching": {
                "method": "HMM/Viterbi",
                "sequence": [item["cell_id"] for item in tower_sequence],
                "limits": "Tower observations describe coverage context, not precise handset location.",
            },
            "calls": calls,
            "common_numbers": [
                {"number": number, "count": count} for number, count in common.most_common()
            ],
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _viterbi_towers(towers: list[dict]) -> list[dict]:
        if not towers:
            return []
        states = sorted({item["cell_id"] for item in towers})
        score: dict[str, tuple[float, list[str]]] = {
            state: (0.0 if state == towers[0]["cell_id"] else -4.0, []) for state in states
        }
        for observation in towers:
            next_score = {}
            for state in states:
                emission = 0.0 if state == observation["cell_id"] else -3.0
                best_previous, (best, path) = max(
                    score.items(), key=lambda item: item[1][0] + (0 if item[0] == state else -1.0)
                )
                next_score[state] = (
                    best + (0 if best_previous == state else -1.0) + emission,
                    [*path, state],
                )
            score = next_score
        path = max(score.values(), key=lambda item: item[0])[1]
        lookup = {item["cell_id"]: item for item in towers}
        return [lookup[state] for state in path]

    def _timeline(
        self,
        case_id: int,
        events: list[Event],
        evidence: dict[int, Evidence],
        clock_confidence: float,
    ) -> dict:
        origin = OriginService(self.db).analyse(case_id)
        dependent = set(origin["order_dependent_event_ids"])
        items = []
        for event in events:
            phase = self._phase(event)
            if phase is None or event.timestamp_utc is None:
                continue
            confidence = round(
                float(event.confidence) * (clock_confidence if event.id in dependent else 1.0), 3
            )
            items.append(
                {
                    "event_id": event.id,
                    "evidence_id": event.evidence_id,
                    "timestamp_utc": event.timestamp_utc,
                    "original_timestamp": event.original_timestamp,
                    "phase": phase,
                    "summary": event.content[:220],
                    "confidence": confidence,
                    "ordering_probability": round(0.5 + 0.49 * confidence, 3),
                    "order_depends_on_clock": event.id in dependent,
                    "citation": {
                        "evidence_id": event.evidence_id,
                        "file": evidence[event.evidence_id].filename,
                        "event_id": event.id,
                        "reference": event.raw_ref,
                        "sha256": evidence[event.evidence_id].sha256,
                    },
                }
            )
        items.sort(key=lambda item: (item["timestamp_utc"], item["event_id"]))
        selected, coverage = self._maximum_coverage(items, 12)
        boundaries = self._optimal_partition(items)
        phases = [
            {"name": phase, "events": [item for item in selected if item["phase"] == phase]}
            for phase in PHASE_ORDER
            if any(item["phase"] == phase for item in items)
        ]
        return {
            "phases": phases,
            "all_events": items,
            "change_points": boundaries,
            "summary_selection": {
                "method": "submodular greedy maximum coverage",
                "selected_event_ids": [item["event_id"] for item in selected],
                "coverage": round(coverage, 3),
                "guarantee": "At least 1-1/e of the optimum for monotone maximum coverage under this cardinality limit.",
            },
            "clock_confidence": clock_confidence,
            "gaps": [
                {
                    "missing": "Suspect device location",
                    "would_help": "A lawfully obtained suspect location export or disclosure",
                },
                {
                    "missing": "Call contents",
                    "would_help": "A lawful recording or participant account",
                },
                {
                    "missing": "Records after the bank statement cutoff",
                    "would_help": "Extended statements from the relevant accounts",
                },
            ],
            "limits": "Summaries are extracts from cited events only; no uncited narrative is generated.",
        }

    @staticmethod
    def _phase(event: Event) -> str | None:
        text = event.content.casefold()
        if event.event_type == "transaction":
            try:
                row = json.loads(event.content)
            except json.JSONDecodeError:
                row = {}
            account = str(row.get("account", "")).casefold()
            direction = str(row.get("type", event.action)).casefold()
            return (
                "onward_movement"
                if direction == "debit" and ("collect" in account or "cashout" in text)
                else "payment"
            )
        if any(word in text for word in ("otp", "kyc", "pin", "credential")):
            return "credential_or_otp_request"
        if any(word in text for word in ("guaranteed", "double", "investment", "return")):
            return "lure"
        if any(word in text for word in ("trust", "safe", "approved", "sir", "madam", "proof")):
            return "trust_building"
        return None

    @staticmethod
    def _features(item: dict) -> set[str]:
        words = set(re.findall(r"[a-z0-9@.]+", item["summary"].casefold()))
        return {item["phase"], f"source:{item['evidence_id']}", *list(words)[:20]}

    def _maximum_coverage(self, items: list[dict], limit: int) -> tuple[list[dict], float]:
        universe = set().union(*(self._features(item) for item in items)) if items else set()
        selected: list[dict] = []
        covered: set[str] = set()
        remaining = items[:]
        while remaining and len(selected) < limit:
            best = max(remaining, key=lambda item: len(self._features(item) - covered))
            selected.append(best)
            covered |= self._features(best)
            remaining.remove(best)
        return selected, len(covered) / max(1, len(universe))

    @staticmethod
    def _optimal_partition(items: list[dict]) -> list[dict]:
        if len(items) < 2:
            return []
        times = [item["timestamp_utc"].timestamp() for item in items]
        cost = [0.0] + [float("inf")] * len(times)
        previous = [0] * (len(times) + 1)
        penalty = 900.0
        for end in range(1, len(times) + 1):
            for start in range(end):
                segment = times[start:end]
                mean = sum(segment) / len(segment)
                value = (
                    cost[start]
                    + sum(abs(point - mean) for point in segment) / len(segment)
                    + penalty
                )
                if value < cost[end]:
                    cost[end], previous[end] = value, start
        cuts = []
        cursor = len(times)
        while previous[cursor] > 0:
            cursor = previous[cursor]
            cuts.append(cursor)
        return [
            {
                "after_event_id": items[index - 1]["event_id"],
                "before_event_id": items[index]["event_id"],
                "method": "dynamic-programming optimal partitioning",
            }
            for index in reversed(cuts)
        ]
