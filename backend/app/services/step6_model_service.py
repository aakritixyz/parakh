from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score

from app.services.ml_foundation_service import BACKEND_ROOT, assert_case_disjoint, split_by_case

MODEL_NAME = "hinglish-scam-classifier"
MODEL_VERSION = "1.0.0"
SEED = 61026

POSITIVE = [
    "OTP bhejo jaldi KYC update karna hai",
    "double money guaranteed return aaj hi",
    "paisa double hoga abhi payment karo",
    "ओटीपी भेजो केवाईसी अपडेट जरूरी है",
    "पैसा दोगुना होगा तुरंत भेजो",
    "kyc updte kro otp bhejoo",
    "guaranteed profit limited slot jaldi",
]
NEGATIVE = [
    "invoice mil gaya thank you",
    "kal meeting ka time confirm karna",
    "bank statement attached for review",
    "घर पहुँचकर फोन करना",
    "known vendor payment approved",
    "refund received and verified in account",
    "please update the project document",
]


def generate_classifier_rows(seed: int = SEED, case_count: int = 300) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for index in range(case_count):
        label = int(rng.random() < 0.5)
        examples = POSITIVE if label else NEGATIVE
        for row_index in range(rng.randint(2, 4)):
            text = rng.choice(examples)
            if rng.random() < 0.35:
                text = text.replace("update", "updte").replace("bhejo", "bhejoo")
            rows.append(
                {
                    "case_id": f"TEXT-SYN-{seed}-{index:04d}",
                    "event_id": row_index,
                    "text": text,
                    "labels": {"scam": label},
                }
            )
    return rows


def train_hinglish_classifier(output_root: Path, seed: int = SEED) -> dict:
    rows = generate_classifier_rows(seed)
    splits = split_by_case(rows, seed)
    assert_case_disjoint(splits)
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=3000)
    train_x = vectorizer.fit_transform(row["text"] for row in splits["train"])
    train_y = np.asarray([row["labels"]["scam"] for row in splits["train"]])
    model = LogisticRegression(random_state=seed, max_iter=500).fit(train_x, train_y)
    validation_x = vectorizer.transform(row["text"] for row in splits["validation"])
    validation_y = np.asarray([row["labels"]["scam"] for row in splits["validation"]])
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        model.predict_proba(validation_x)[:, 1], validation_y
    )
    test_x = vectorizer.transform(row["text"] for row in splits["test"])
    test_y = np.asarray([row["labels"]["scam"] for row in splits["test"]])
    scores = np.asarray(calibrator.predict(model.predict_proba(test_x)[:, 1]))
    predictions = scores >= 0.5
    fraction_positive, mean_predicted = calibration_curve(test_y, scores, n_bins=8)
    metrics = {
        "label": "on synthetic data",
        "precision": round(float(precision_score(test_y, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(test_y, predictions, zero_division=0)), 4),
        "pr_auc": round(float(average_precision_score(test_y, scores)), 4),
        "calibration_curve": [
            {"mean_predicted": round(float(x), 4), "fraction_positive": round(float(y), 4)}
            for x, y in zip(mean_predicted, fraction_positive, strict=True)
        ],
    }
    names = vectorizer.get_feature_names_out()
    top = np.argsort(model.coef_[0])[::-1][:12]
    feature_reasons = [
            {"feature": str(names[index]), "weight": round(float(model.coef_[0][index]), 4)}
            for index in top
    ]
    explanations = {
        "tree": {
            "method": "logistic-regression character-feature weights",
            "values": {item["feature"]: item["weight"] for item in feature_reasons},
        },
        "top_words": feature_reasons,
    }
    output = output_root / f"{MODEL_NAME}-{MODEL_VERSION}"
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "model.joblib"
    joblib.dump(
        {"vectorizer": vectorizer, "model": model, "calibrator": calibrator, "seed": seed},
        artifact,
    )
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    try:
        stored_path = str(artifact.relative_to(BACKEND_ROOT))
    except ValueError:
        stored_path = str(artifact)
    card = {
        "name": MODEL_NAME,
        "version": MODEL_VERSION,
        "licence": "Internal evaluation only",
        "training_data": f"Generated English, Hindi and Hinglish text cases; seed {seed}. Riya excluded.",
        "known_limits": [
            "A lead generator, never a finding.",
            "Offline multilingual character n-gram embeddings are not a fine-tuned language model.",
            "Metrics are on synthetic data and do not estimate performance on real investigations.",
        ],
        "metrics": metrics,
        "explanations": explanations,
        "artifact_path": stored_path,
        "artifact_sha256": digest,
        "evaluation_label": "on synthetic data",
        "seed": seed,
        "offline_only": True,
    }
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (output / "model_card.json").write_text(json.dumps(card, indent=2) + "\n")
    return card
