"""Local pretrained vectors, persisted by model and source content hash."""
from __future__ import annotations

import hashlib
import os
import tempfile
import time

import numpy as np

from app.services.offline_models import ROOT, ModelUnavailable, local_model

CACHE = ROOT.parent / "embeddings"


def rank_documents(case_id: int, documents: list[tuple[int, str]], query: str, budget: float = 5.0) -> tuple[list[tuple[int, float]], dict]:
    started = time.monotonic()
    try:
        model = local_model("embeddings")
    except ModelUnavailable as exc:
        return [], {"status": "unavailable", "reason": str(exc), "complete": False, "fallback": "BM25 only; no vector hits invented"}
    root = CACHE / str(case_id) / (model.card["artifact_sha256"] + "-single-v2")
    root.mkdir(parents=True, exist_ok=True)
    vectors = []
    identifiers = []
    complete = True
    pending = []
    for identifier, text in documents:
        key = hashlib.sha256(text.encode()).hexdigest()
        path = root / f"{identifier}-{key}.npy"
        if path.is_file():
            try:
                vector = np.load(path, allow_pickle=False)
                if vector.shape == (int(model.config["hidden_size"]),) and np.isfinite(vector).all():
                    identifiers.append(identifier)
                    vectors.append(vector)
                    continue
            except (OSError, ValueError):
                pass
        pending.append((identifier, text, path))
    # Only explicit provisioning/indexing may do a large cold corpus build.
    if len(pending) > 500 and budget <= 5:
        complete = False
        pending = []
    for start in range(0, len(pending), 8):
        if time.monotonic() - started >= budget:
            complete = False
            break
        batch = pending[start:start+8]
        embedded = model.embed([item[1] for item in batch])
        for (identifier, _, path), vector in zip(batch, embedded, strict=True):
            descriptor, temporary = tempfile.mkstemp(dir=root, suffix=".npy")
            with os.fdopen(descriptor, "wb") as output:
                np.save(output, vector, allow_pickle=False)
            os.replace(temporary, path)
            identifiers.append(identifier)
            vectors.append(vector)
    ranked = []
    if vectors:
        query_vector = model.embed([query], query=True)[0]
        scores = np.asarray(vectors) @ query_vector
        ranked = sorted(zip(identifiers, map(float, scores), strict=True), key=lambda item: (-item[1], item[0]))
    return ranked, {"status": "ready" if complete else "partial", "complete": complete,
                    "reason": "Hash-checked pretrained multilingual-e5-small, CPU; no network calls",
                    "model_card": model.card, "indexed": len(vectors), "total": len(documents),
                    "seed": 51026, "time_limit_seconds": budget, "version": "e5-onnx-2",
                    "assumptions": "E5 query/passage prefixes, masked mean pooling, cosine similarity; scores are relevance leads",
                    "fallback": "BM25 for unindexed documents; run python -m scripts.index_embeddings for large corpora"}


def rank_persisted_index(case_id: int, query: str) -> tuple[list[tuple[int, float]], dict]:
    try:
        model = local_model("embeddings")
    except ModelUnavailable as exc:
        return [], {"status": "unavailable", "reason": str(exc), "complete": False}
    import json
    root = CACHE / str(case_id) / (model.card["artifact_sha256"] + "-single-v2")
    try:
        manifest = json.loads((root / "index.json").read_text())
        matrix_path = root / manifest["matrix_file"]
        if not matrix_path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Invalid vector index path")
        vectors = np.load(matrix_path, mmap_mode="r", allow_pickle=False)
        if vectors.shape[0] != len(manifest["event_ids"]):
            raise ValueError("Index dimension mismatch")
        scores = vectors @ model.embed([query], query=True)[0]
        top = np.argsort(-scores, kind="stable")[:250]
        return [(manifest["event_ids"][int(i)], float(scores[i])) for i in top], {
            "status": "ready", "complete": True, "model_card": model.card,
            "indexed": len(scores), "reason": "Memory-mapped offline pretrained index; cosine + RRF",
            "seed": 51026, "version": "e5-onnx-2", "time_limit_seconds": 5,
        }
    except (OSError, ValueError, KeyError):
        return [], {"status": "index_required", "complete": False, "model_card": model.card,
                    "reason": "Run python -m scripts.index_embeddings for this large case; BM25 remains available", "fallback": "BM25 only"}
