"""Bounded synthetic checks of frozen pretrained models; no training on case data."""
import json
from pathlib import Path

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, precision_score, recall_score

from app.services.offline_models import ROOT, local_model


def main():
    embedding, nli = local_model("embeddings"), local_model("entailment")
    cases = [("paise wapas", "Please refund my money", "The weather is sunny"),
             ("ओटीपी भेजो", "Send the one time password", "Dinner is ready"),
             ("bank transfer", "A payment was sent to the account", "The train arrives tomorrow"),
             ("call record", "The telephone call lasted sixty seconds", "A book is on the table"),
             ("location history", "GPS coordinates show the device trail", "The password was changed")]
    retrieval = []
    for case, (query, relevant, irrelevant) in enumerate(cases):
        scores = embedding.embed([relevant, irrelevant]) @ embedding.embed([query], query=True)[0]
        retrieval.append({"case_id": f"MODEL-SYN-51026-{case}", "query": query, "correct_top_one": bool(scores[0] > scores[1]), "scores": list(map(float, scores))})
    labels, scores = [], []
    for index, name in enumerate(["Meera", "Kabir", "Asha", "Neha", "Kunal"]):
        amount = (index+1)*1000
        premise = f"{name} paid INR {amount} to the shop. No refund was received."
        for label, hypothesis in [(1, f"{name} paid INR {amount} to the shop."), (0, f"{name} received a refund of INR {amount}.")]:
            labels.append(label)
            scores.append(nli.entail(premise, hypothesis)["entailment"])
    fractions, means = calibration_curve(labels, scores, n_bins=5)
    metrics = {"label": "on synthetic data", "precision": float(precision_score(labels, np.asarray(scores) >= .85, zero_division=0)), "recall": float(recall_score(labels, np.asarray(scores) >= .85, zero_division=0)), "pr_auc": float(average_precision_score(labels, scores)), "calibration_curve": [{"mean_predicted": float(x), "fraction_positive": float(y)} for x, y in zip(means, fractions, strict=True)], "samples": len(labels), "limit": "Tiny synthetic smoke set; no deployment-accuracy estimate"}
    retrieval_metrics = {"label": "on synthetic data", "top_one_accuracy": sum(item["correct_top_one"] for item in retrieval)/len(retrieval), "queries": len(retrieval), "limit": "Tiny multilingual synthetic smoke set; relevance scores are not calibrated probabilities"}
    report = {"seed": 51026, "time_limit_seconds": 120, "assumptions": "Frozen models; no training; five independent synthetic retrieval cases; ten synthetic entailment pairs; threshold .85", "fallback": "BM25 and exact excerpts if models unavailable", "retrieval": retrieval, "embedding_metrics": retrieval_metrics, "entailment_metrics": metrics}
    for kind, measured in [("embeddings", retrieval_metrics), ("entailment", metrics)]:
        path = ROOT / kind / "manifest.json"
        card = json.loads(path.read_text())
        card["metrics"] = measured
        path.write_text(json.dumps(card, indent=2))
    destination = Path(__file__).resolve().parents[2] / "docs" / "validation" / "offline-models.json"
    destination.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
