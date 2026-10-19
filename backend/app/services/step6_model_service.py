from __future__ import annotations

import hashlib
import json
import random
import re
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score

from app.services.ml_foundation_service import BACKEND_ROOT, assert_case_disjoint, split_by_case
from app.services.offline_models import ModelUnavailable, local_model

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


class OfflineE5Vectorizer:
    def __init__(self):
        self.cache = {}
        self.model_sha256 = local_model("embeddings").card["artifact_sha256"]

    def transform(self, texts):
        texts = list(texts)
        model = local_model("embeddings")
        if model.card["artifact_sha256"] != self.model_sha256:
            raise ModelUnavailable("Classifier embedding model checksum changed")
        missing = sorted(set(texts) - self.cache.keys())
        if missing:
            self.cache.update(zip(missing, model.embed(missing), strict=True))
        return np.asarray([self.cache[text] for text in texts])

    def fit_transform(self, texts):
        return self.transform(texts)


def top_words(bundle: dict, text: str) -> list[dict]:
    vectorizer = bundle["vectorizer"]
    if isinstance(vectorizer, OfflineE5Vectorizer):
        words = list(dict.fromkeys(re.findall(r"[\w]+", text)))[:16]
        variants = [text] + [re.sub(r"\b" + re.escape(word) + r"\b", "", text) for word in words]
        scores = bundle["model"].predict_proba(vectorizer.transform(variants))[:, 1]
        return sorted([{"word": word, "weight": float(scores[0]-score)} for word, score in zip(words, scores[1:], strict=True)], key=lambda item: -item["weight"])[:5]
    vector = vectorizer.transform([text])
    weighted = vector.multiply(bundle["model"].coef_[0]).toarray()[0]
    names = vectorizer.get_feature_names_out()
    return [{"word": str(names[index]), "weight": float(weighted[index])} for index in np.argsort(weighted)[::-1][:5] if weighted[index] > 0]


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
    started = time.monotonic()
    try:
        vectorizer = OfflineE5Vectorizer()
        representation = "pretrained multilingual-e5-small + logistic regression"
    except ModelUnavailable:
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=3000)
        representation = "character n-gram fallback; pretrained embeddings unavailable"
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
    bundle = {"vectorizer": vectorizer, "model": model, "calibrator": calibrator, "seed": seed, "representation": representation}
    feature_reasons = top_words(bundle, POSITIVE[0])
    explanations = {"tree": {"method": "word occlusion of embedding classifier" if isinstance(vectorizer, OfflineE5Vectorizer) else "character feature weights", "values": {item["word"]: item["weight"] for item in feature_reasons}}, "top_words": feature_reasons}
    if time.monotonic() - started > 120:
        raise TimeoutError("Synthetic classifier training exceeded 120 seconds; retain previous model and phrase rules")
    output = output_root / f"{MODEL_NAME}-{MODEL_VERSION}"
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "model.joblib"
    joblib.dump(
        bundle,
        artifact,
    )
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    try:
        stored_path = str(artifact.relative_to(BACKEND_ROOT))
    except ValueError:
        stored_path = str(artifact)
    card = {
        "name": MODEL_NAME,
        "version": "2.0.0" if isinstance(vectorizer, OfflineE5Vectorizer) else MODEL_VERSION,
        "licence": "Internal evaluation only",
        "training_data": f"Generated English, Hindi and Hinglish text cases; seed {seed}. Riya excluded.",
        "known_limits": [
            "A lead generator, never a finding.",
            representation + "; no fine tuning on case data",
            "Fixed seed; 120 second training limit; keep prior model and phrase rules if incomplete",
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
