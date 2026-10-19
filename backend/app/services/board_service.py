from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict, deque
from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field, model_validator

BOARD_SCHEMA_VERSION = 1
BOARD_SEED = 51026

CardKind = Literal["person", "identifier", "message", "event", "bank", "call", "document", "location", "finding", "note"]
LinkStatus = Literal["established", "possible", "hypothesis", "contradicted", "not_established"]


class Receipt(BaseModel):
    evidence_id: int | None = None
    file: str = Field(default="", max_length=500)
    reference: str = Field(default="", max_length=500)
    sha256: str = Field(default="", max_length=64)


class BoardCard(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    kind: CardKind
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=5000)
    timestamp: str | None = None
    source_badge: str = Field(default="", max_length=120)
    receipt: Receipt | None = None
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)
    locked: bool = False
    community: int = Field(default=0, ge=0, le=10000)
    size: float = Field(default=1, ge=0.5, le=4)
    selected: bool = False

    @model_validator(mode="after")
    def evidence_receipt(self):
        if self.kind != "note" and self.receipt is None:
            raise ValueError("Only investigator notes may exist without a source receipt")
        if self.kind == "note":
            self.source_badge = "Investigator note, not evidence"
        return self


class BoardLink(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=240)
    type: str = Field(min_length=1, max_length=80)
    status: LinkStatus
    auto: bool = False
    support: list[str] = Field(default_factory=list, max_length=50)
    reasons: list[str] = Field(default_factory=list, max_length=20)
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_name: str | None = Field(default=None, max_length=120)
    model_version: str | None = Field(default=None, max_length=80)


class BoardZone(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    x: float
    y: float
    width: float = Field(gt=20, le=100000)
    height: float = Field(gt=20, le=100000)
    community: int = Field(default=0, ge=0, le=10000)


class BoardState(BaseModel):
    schema_version: Literal[1] = 1
    seed: int = BOARD_SEED
    cards: list[BoardCard] = Field(default_factory=list, max_length=5000)
    links: list[BoardLink] = Field(default_factory=list, max_length=15000)
    zones: list[BoardZone] = Field(default_factory=list, max_length=500)
    exhibit_ids: list[str] = Field(default_factory=list, max_length=1000)
    caption: str = Field(default="", max_length=1000)
    viewport: dict = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})

    @model_validator(mode="after")
    def references(self):
        ids = [item.id for item in self.cards]
        if len(ids) != len(set(ids)):
            raise ValueError("Card IDs must be unique")
        links = [item.id for item in self.links]
        if len(links) != len(set(links)):
            raise ValueError("Link IDs must be unique")
        known = set(ids)
        for link in self.links:
            if link.source not in known or link.target not in known or link.source == link.target:
                raise ValueError("Links must join two existing, distinct cards")
            if not link.auto and not link.support and link.status != "not_established":
                link.status = "not_established"
        return self


def empty_board() -> dict:
    return BoardState().model_dump(mode="json")


def canonical_hash(state: dict) -> str:
    validated = BoardState.model_validate(state).model_dump(mode="json")
    canonical = json.dumps(validated, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def graph_from(state: BoardState) -> nx.Graph:
    graph = nx.Graph()
    for card in state.cards:
        graph.add_node(card.id, timestamp=card.timestamp or "")
    for link in state.links:
        if link.status != "contradicted":
            weight = {"established": 1.0, "possible": 1.8, "hypothesis": 2.5, "not_established": 4.0}.get(link.status, 3.0)
            graph.add_edge(link.source, link.target, id=link.id, weight=weight, status=link.status)
    return graph


def shortest_path(state: BoardState, source: str, target: str) -> dict:
    graph = graph_from(state)
    try:
        nodes = nx.shortest_path(graph, source, target, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {"nodes": [], "links": [], "complete": True, "status": "no_path"}
    edges = [graph[nodes[index]][nodes[index + 1]]["id"] for index in range(len(nodes) - 1)]
    return {"nodes": nodes, "links": edges, "complete": True, "status": "ready"}


def connect_selected(state: BoardState, selected: list[str], time_limit_ms: int = 1000) -> dict:
    """Deterministic Steiner approximation by a metric-closure MST with a hard wall-clock budget."""
    started = time.monotonic()
    graph = graph_from(state)
    terminals = sorted(set(selected))
    if len(terminals) < 2 or any(item not in graph for item in terminals):
        return {"nodes": terminals, "links": [], "complete": True, "status": "select_two_or_more", "algorithm": "metric-closure Steiner approximation"}
    closure = nx.Graph()
    paths: dict[tuple[str, str], list[str]] = {}
    complete = True
    for index, left in enumerate(terminals):
        for right in terminals[index + 1:]:
            if (time.monotonic() - started) * 1000 >= time_limit_ms:
                complete = False
                break
            try:
                path = nx.shortest_path(graph, left, right, weight="weight")
                distance = nx.path_weight(graph, path, weight="weight")
                closure.add_edge(left, right, weight=distance)
                paths[(left, right)] = path
            except nx.NetworkXNoPath:
                continue
        if not complete:
            break
    if closure.number_of_edges() == 0:
        return {"nodes": terminals, "links": [], "complete": complete, "status": "no_path", "algorithm": "metric-closure Steiner approximation"}
    tree_nodes: set[str] = set()
    tree_links: set[str] = set()
    for left, right in nx.minimum_spanning_edges(closure, data=False):
        path = paths.get((left, right)) or paths.get((right, left), [])
        tree_nodes.update(path)
        tree_links.update(graph[path[i]][path[i + 1]]["id"] for i in range(len(path) - 1))
    return {"nodes": sorted(tree_nodes), "links": sorted(tree_links), "complete": complete,
            "status": "ready" if complete else "incomplete", "algorithm": "metric-closure Steiner approximation",
            "time_limit_ms": time_limit_ms}


def communities_and_centrality(state: BoardState) -> dict:
    graph = graph_from(state)
    if not graph:
        return {"communities": {}, "betweenness": {}}
    groups = nx.community.louvain_communities(graph, seed=state.seed, weight="weight")
    communities = {node: index for index, group in enumerate(groups) for node in sorted(group)}
    centrality = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    return {"communities": communities, "betweenness": {key: round(value, 6) for key, value in centrality.items()}}


def neighbours(state: BoardState, selected: list[str], depth: int = 1) -> dict:
    graph = graph_from(state)
    seen = set(selected)
    frontier = deque((node, 0) for node in selected if node in graph)
    while frontier:
        node, distance = frontier.popleft()
        if distance >= depth:
            continue
        for adjacent in sorted(graph.neighbors(node)):
            if adjacent not in seen:
                seen.add(adjacent)
                frontier.append((adjacent, distance + 1))
    links = sorted(data["id"] for left, right, data in graph.edges(data=True) if left in seen and right in seen)
    return {"nodes": sorted(seen), "links": links, "depth": depth}


def time_respecting_path(state: BoardState, source: str, target: str) -> dict:
    graph = graph_from(state)
    queue = deque([(source, [source])])
    visited = {source}
    while queue:
        node, path = queue.popleft()
        if node == target:
            links = [graph[path[i]][path[i + 1]]["id"] for i in range(len(path) - 1)]
            return {"nodes": path, "links": links, "complete": True, "status": "ready"}
        current_time = graph.nodes[node].get("timestamp", "")
        for adjacent in sorted(graph.neighbors(node)):
            adjacent_time = graph.nodes[adjacent].get("timestamp", "")
            if adjacent not in visited and (not current_time or not adjacent_time or adjacent_time >= current_time):
                visited.add(adjacent)
                queue.append((adjacent, [*path, adjacent]))
    return {"nodes": [], "links": [], "complete": True, "status": "no_time_respecting_path"}


def auto_arrange(state: BoardState, time_limit_ms: int = 1200) -> dict:
    graph = graph_from(state)
    locked = {item.id: (item.x, item.y) for item in state.cards if item.locked}
    started = time.monotonic()
    fallback = "none"
    if graph.number_of_nodes() > 500:
        positions = _grid(sorted(graph.nodes))
        fallback = "grid"
    else:
        try:
            positions = nx.spring_layout(graph, seed=state.seed, iterations=80, pos=locked or None, fixed=list(locked) or None, scale=900)
            if (time.monotonic() - started) * 1000 > time_limit_ms:
                raise TimeoutError
        except (ValueError, nx.NetworkXError, TimeoutError):
            positions = _radial(sorted(graph.nodes))
            fallback = "radial"
    for key, value in locked.items():
        positions[key] = value
    metrics = communities_and_centrality(state)
    return {"positions": {key: {"x": round(float(value[0]), 2), "y": round(float(value[1]), 2)} for key, value in positions.items()},
            **metrics, "seed": state.seed, "time_limit_ms": time_limit_ms, "fallback": fallback,
            "complete": fallback == "none", "algorithm": "seeded force-directed" if fallback == "none" else fallback}


def _grid(nodes: list[str]) -> dict[str, tuple[float, float]]:
    width = max(1, math.ceil(math.sqrt(len(nodes))))
    return {node: ((index % width) * 260.0, (index // width) * 180.0) for index, node in enumerate(nodes)}


def _radial(nodes: list[str]) -> dict[str, tuple[float, float]]:
    count = max(1, len(nodes))
    return {node: (700 * math.cos(2 * math.pi * index / count), 700 * math.sin(2 * math.pi * index / count)) for index, node in enumerate(nodes)}


def find_gaps(state: BoardState) -> list[dict]:
    """Leads only: surface strong identifier overlap without an existing link."""
    connected = {frozenset((link.source, link.target)) for link in state.links}
    tokens: dict[str, set[str]] = defaultdict(set)
    for card in state.cards:
        text = f"{card.title} {card.body}".casefold()
        for token in text.replace("/", " ").replace(",", " ").split():
            if len(token) >= 7 and ("@" in token or any(char.isdigit() for char in token)):
                tokens[token.strip(".()[]")] .add(card.id)
    leads = []
    for token, cards in sorted(tokens.items()):
        ordered = sorted(cards)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                if frozenset((left, right)) not in connected:
                    leads.append({"id": f"gap-{left}-{right}", "source": left, "target": right,
                                  "status": "lead", "finding": False, "confidence": 0.72,
                                  "model_name": "alias-matcher", "model_version": "step4-existing",
                                  "top_reasons": [f"Shared identifier {token}", "No board string currently records the relationship"],
                                  "notice": "Suggested missing link; this is a lead, never a finding."})
    return leads[:100]
