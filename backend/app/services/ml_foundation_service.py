from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml import ModelRecord
from app.services.audit_service import AuditService

FEATURES = ["amount", "urgency", "new_payee", "refund_claim", "device_count"]
DEFAULT_SEED = 51026
MODEL_NAME = "synthetic-scam-baseline"
MODEL_VERSION = "1.0.0"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def generate_synthetic_cases(seed: int = DEFAULT_SEED, case_count: int = 240) -> list[dict]:
    """Generate labelled cases. The hand-checked Riya pack is never read here."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for case_number in range(case_count):
        case_id = f"SYN-{seed}-{case_number:04d}"
        scam = rng.random() < 0.48
        mule = rng.random() < (0.62 if scam else 0.08)
        altered = rng.random() < (0.58 if scam else 0.06)
        same_person = rng.random() < 0.52
        for event_number in range(rng.randint(2, 5)):
            amount = round(rng.uniform(8_000, 90_000) if scam else rng.uniform(100, 28_000), 2)
            urgency = int(rng.random() < (0.78 if scam else 0.12))
            new_payee = int(rng.random() < (0.72 if scam else 0.18))
            refund_claim = int(rng.random() < (0.55 if scam else 0.05))
            device_count = rng.randint(2, 5) if mule else rng.randint(1, 2)
            words = ["payment", "account"]
            words += ["urgent", "refund", "verify"] if scam else ["invoice", "known", "confirmed"]
            rows.append(
                {
                    "case_id": case_id,
                    "event_id": event_number,
                    "features": [amount, urgency, new_payee, refund_claim, device_count],
                    "text": " ".join(words),
                    "labels": {
                        "scam": int(scam),
                        "mule": int(mule),
                        "altered_receipt": int(altered),
                        "same_person": int(same_person),
                    },
                }
            )
    return rows


def split_by_case(rows: list[dict], seed: int = DEFAULT_SEED) -> dict[str, list[dict]]:
    case_ids = sorted({row["case_id"] for row in rows})
    random.Random(seed).shuffle(case_ids)
    train_end = int(len(case_ids) * 0.7)
    validation_end = int(len(case_ids) * 0.85)
    groups = {
        "train": set(case_ids[:train_end]),
        "validation": set(case_ids[train_end:validation_end]),
        "test": set(case_ids[validation_end:]),
    }
    return {name: [row for row in rows if row["case_id"] in ids] for name, ids in groups.items()}


def assert_case_disjoint(splits: dict[str, list[dict]]) -> None:
    ids = {name: {row["case_id"] for row in rows} for name, rows in splits.items()}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        overlap = ids[left] & ids[right]
        if overlap:
            raise ValueError(f"Case leakage between {left} and {right}: {sorted(overlap)[:3]}")


def top_words(rows: list[dict], limit: int = 8) -> list[dict]:
    vectorizer = TfidfVectorizer(max_features=100)
    matrix = vectorizer.fit_transform(row["text"] for row in rows)
    labels = np.array([row["labels"]["scam"] for row in rows], dtype=bool)
    difference = np.asarray(matrix[labels].mean(axis=0) - matrix[~labels].mean(axis=0)).ravel()
    names = vectorizer.get_feature_names_out()
    return [
        {"word": str(names[index]), "weight": round(float(difference[index]), 4)}
        for index in np.argsort(difference)[::-1][:limit]
    ]


def tree_explanation(model, sample: list[float]) -> dict:
    """Use local SHAP when installed; otherwise return an explicit importance fallback."""
    try:
        if os.environ.get("PARAKH_ENABLE_SHAP") != "1":
            raise ImportError
        import shap  # type: ignore[import-not-found]

        values = shap.TreeExplainer(model).shap_values(np.asarray([sample]))
        flat = np.asarray(values).reshape(-1)
        return {"method": "SHAP", "values": dict(zip(FEATURES, flat.tolist(), strict=True))}
    except (ImportError, RuntimeError, TypeError, ValueError):
        return {
            "method": "feature_importance_fallback",
            "values": dict(zip(FEATURES, model.feature_importances_.tolist(), strict=True)),
            "limit": "Install the vetted local SHAP package to calculate per-row SHAP values.",
        }


def run_baseline(output_root: Path, seed: int = DEFAULT_SEED) -> dict:
    rows = generate_synthetic_cases(seed)
    splits = split_by_case(rows, seed)
    assert_case_disjoint(splits)
    arrays = {
        name: (
            np.asarray([row["features"] for row in items], dtype=float),
            np.asarray([row["labels"]["scam"] for row in items], dtype=int),
        )
        for name, items in splits.items()
    }
    model = GradientBoostingClassifier(random_state=seed, n_estimators=60, max_depth=2)
    model.fit(*arrays["train"])
    validation_raw = model.predict_proba(arrays["validation"][0])[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(validation_raw, arrays["validation"][1])
    test_raw = model.predict_proba(arrays["test"][0])[:, 1]
    scores = np.asarray(calibrator.predict(test_raw))
    labels = arrays["test"][1]
    predictions = scores >= 0.5
    fraction_positive, mean_predicted = calibration_curve(labels, scores, n_bins=8)
    metrics = {
        "label": "on synthetic data",
        "precision": round(float(precision_score(labels, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(labels, predictions, zero_division=0)), 4),
        "pr_auc": round(float(average_precision_score(labels, scores)), 4),
        "calibration_curve": [
            {"mean_predicted": round(float(x), 4), "fraction_positive": round(float(y), 4)}
            for x, y in zip(mean_predicted, fraction_positive, strict=True)
        ],
    }
    output = output_root / f"{MODEL_NAME}-{MODEL_VERSION}"
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "model.joblib"
    joblib.dump({"model": model, "calibrator": calibrator, "features": FEATURES}, artifact)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "seed": seed,
        "case_count": len({row["case_id"] for row in rows}),
        "row_count": len(rows),
        "labels": ["scam", "mule", "altered_receipt", "same_person"],
        "split_case_counts": {
            name: len({row["case_id"] for row in items}) for name, items in splits.items()
        },
        "riya_pack_used_for_training": False,
    }
    explanations = {
        "tree": tree_explanation(model, arrays["test"][0][0].tolist()),
        "top_words": top_words(splits["train"]),
    }
    try:
        stored_artifact_path = str(artifact.relative_to(BACKEND_ROOT))
    except ValueError:
        stored_artifact_path = str(artifact)
    card = {
        "name": MODEL_NAME,
        "version": MODEL_VERSION,
        "licence": "Internal evaluation only",
        "training_data": f"Generated synthetic cases; seed {seed}. Riya excluded.",
        "known_limits": [
            "A lead generator, never a finding.",
            "Metrics do not estimate performance on real investigations.",
            "Synthetic patterns may be easier than real-world patterns.",
        ],
        "metrics": metrics,
        "explanations": explanations,
        "artifact_path": stored_artifact_path,
        "artifact_sha256": digest,
        "evaluation_label": "on synthetic data",
        "seed": seed,
        "offline_only": True,
    }
    for name, value in (("dataset_manifest.json", manifest), ("metrics.json", metrics), ("model_card.json", card)):
        (output / name).write_text(json.dumps(value, indent=2) + "\n")
    return card


def load_offline_model(card: dict):
    path = Path(card["artifact_path"])
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != card["artifact_sha256"]:
        raise ValueError("Local model artifact is missing or its SHA-256 does not match the card")
    return joblib.load(path)


def register_model(db: Session, card: dict, actor: str = "operator-cli") -> ModelRecord:
    record = db.scalar(
        select(ModelRecord).where(
            ModelRecord.name == card["name"], ModelRecord.version == card["version"]
        )
    )
    if record is None:
        record = ModelRecord(**card)
        db.add(record)
        db.flush()
    else:
        for key, value in card.items():
            setattr(record, key, value)
    AuditService(db).log(
        action="model.registered",
        actor=actor,
        target_type="model",
        target_id=f"{card['name']}:{card['version']}",
        payload={"seed": card["seed"], "metrics": card["metrics"], "offline_only": True},
    )
    db.commit()
    return record
