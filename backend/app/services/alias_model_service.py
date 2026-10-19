"""Synthetic-trained alias leads with calibrated scores and exact seven-feature SHAP."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import time
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score

from app.services.ml_foundation_service import assert_case_disjoint, split_by_case
from app.services.offline_models import ROOT, ModelUnavailable

SEED = 41026
FEATURES = ["normalised_edit_similarity", "jaro_winkler", "shared_contact_count", "shared_devices", "cooccurrence_timing", "phonetic_match", "shared_token_match"]
VERSION = "alias-gbt-1.0"


def feature_vector(features: dict) -> list[float]:
    return [float(features.get(name, bool(features.get("shared_tokens")) if name == "shared_token_match" else 0)) for name in FEATURES]


def generate_cases(count: int = 600, seed: int = SEED) -> list[dict]:
    from app.services.identity_service import alias_features
    rng = random.Random(seed)
    names = ["Meera", "Kabir", "Asha", "Vikram", "Neha", "Kunal", "Dev", "Tara", "Ishaan", "Sana"]
    rows = []
    for case in range(count):
        person = rng.choice(names)
        for pair in range(4):
            same = pair % 2 == 0
            other = person if same or rng.random() < 0.2 else rng.choice([name for name in names if name != person])
            handle = other.casefold() + rng.choice([".collect", ".payments", "", "_agent"])
            if same and rng.random() < 0.35:
                handle = handle.replace("a", "4").replace("i", "1")
            features = alias_features("Agent " + person, handle + "@synthetic", rng.randrange(1, 6) if same else rng.randrange(0, 3))
            features.update(shared_contact_count=rng.randrange(1, 5) if same else rng.randrange(0, 3),
                            shared_devices=(rng.randrange(1, 3) if rng.random() > 0.35 else 0) if same else int(rng.random() < 0.15),
                            cooccurrence_timing=rng.uniform(0.0, 1) if same else rng.uniform(0, 0.75))
            rows.append({"case_id": f"ALIAS-SYN-{seed}-{case:05d}", "pair": pair, "features": feature_vector(features), "labels": {"same_person": int(same)}})
    return rows


def train_alias(root: Path | None = None) -> dict:
    root = root or ROOT / "alias"
    root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    rows = generate_cases()
    splits = split_by_case(rows, SEED)
    assert_case_disjoint(splits)
    def arrays(group):
        return np.asarray([row["features"] for row in splits[group]]), np.asarray([row["labels"]["same_person"] for row in splits[group]])
    train_x, train_y = arrays("train")
    valid_x, valid_y = arrays("validation")
    test_x, test_y = arrays("test")
    model = GradientBoostingClassifier(n_estimators=60, max_depth=2, random_state=SEED)
    model.fit(train_x, train_y)
    calibration = IsotonicRegression(out_of_bounds="clip").fit(model.predict_proba(valid_x)[:, 1], valid_y)
    scores = calibration.predict(model.predict_proba(test_x)[:, 1])
    positives, predicted = calibration_curve(test_y, scores, n_bins=8)
    if time.monotonic() - started > 30:
        raise TimeoutError("Alias training exceeded 30 seconds; retain the prior model and labelled heuristic fallback")
    artifact = root / "model.joblib"
    joblib.dump({"model": model, "calibration": calibration, "baseline": train_x.mean(axis=0)}, artifact)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    card = {"name": "parakh-alias-gradient-boosted", "version": VERSION, "licence": "Locally generated model; scikit-learn BSD-3-Clause runtime",
            "training_data": "Generated alias cases only; Riya's pack is excluded", "known_limits": ["Synthetic-data calibration is not real-world identity confidence", "Shared contacts/devices/time are leads, not identity proof", "Exact interventional SHAP uses a fixed synthetic-training mean baseline"],
            "seed": SEED, "time_limit_seconds": 30, "fallback": "Labelled heuristic when the local model is unavailable", "offline_only": True,
            "artifact_sha256": digest, "artifact_path": str(artifact), "feature_names": FEATURES,
            "metrics": {"label": "on synthetic data", "precision": float(precision_score(test_y, scores >= 0.5, zero_division=0)), "recall": float(recall_score(test_y, scores >= 0.5, zero_division=0)), "pr_auc": float(average_precision_score(test_y, scores)), "calibration_curve": [{"mean_predicted": float(p), "fraction_positive": float(y)} for p, y in zip(predicted, positives, strict=True)]},
            "case_split": {key: sorted({row["case_id"] for row in value}) for key, value in splits.items()},
            "explanations": {"tree": {"method": "exact interventional SHAP", "values": {}, "limit": "Fixed synthetic baseline; seven features"}, "top_words": []},
            "evaluation_label": "on synthetic data"}
    (root / "manifest.json").write_text(json.dumps(card, indent=2))
    (root / "generated_cases.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return card


@lru_cache(maxsize=1)
def load_alias():
    root = ROOT / "alias"
    try:
        card = json.loads((root / "manifest.json").read_text())
        path = root / "model.joblib"
        if hashlib.sha256(path.read_bytes()).hexdigest() != card["artifact_sha256"]:
            raise ModelUnavailable("Alias model checksum failed")
        return joblib.load(path), card
    except (OSError, ValueError, KeyError) as exc:
        raise ModelUnavailable("Provision the synthetic alias model first") from exc


def alias_prediction(features: dict) -> dict:
    artifact, card = load_alias()
    values = np.asarray(feature_vector(features))
    baseline = artifact["baseline"]
    size = len(FEATURES)
    masks = np.asarray(list(itertools.product([False, True], repeat=size)))
    samples = np.where(masks, values, baseline)
    scores = artifact["calibration"].predict(artifact["model"].predict_proba(samples)[:, 1])
    lookup = {tuple(mask): value for mask, value in zip(masks, scores, strict=True)}
    shap = []
    for feature in range(size):
        contribution = 0.0
        for mask in masks:
            if mask[feature]:
                continue
            added = mask.copy()
            added[feature] = True
            count = int(mask.sum())
            contribution += (lookup[tuple(added)] - lookup[tuple(mask)]) / (size * math.comb(size - 1, count))
        shap.append(float(contribution))
    return {"confidence": float(scores[-1]), "base_value": float(scores[0]),
            "shap": dict(zip(FEATURES, shap, strict=True)), "model_card": card,
            "top_reasons": [f"{name.replace('_', ' ')}: {value:+.3f}" for name, value in sorted(zip(FEATURES, shap, strict=True), key=lambda item: -abs(item[1]))[:3]]}
