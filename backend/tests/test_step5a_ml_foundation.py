import json

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.ml import ModelRecord
from app.services.ml_foundation_service import (
    assert_case_disjoint,
    generate_synthetic_cases,
    load_offline_model,
    register_model,
    run_baseline,
    split_by_case,
)


def test_baseline_runs_saves_metrics_and_registers_card(db, tmp_path):
    card = run_baseline(tmp_path, seed=51026)
    folder = tmp_path / "synthetic-scam-baseline-1.0.0"
    metrics = json.loads((folder / "metrics.json").read_text())
    manifest = json.loads((folder / "dataset_manifest.json").read_text())
    assert metrics["label"] == "on synthetic data"
    assert {"precision", "recall", "pr_auc", "calibration_curve"} <= metrics.keys()
    assert manifest["riya_pack_used_for_training"] is False
    assert load_offline_model(card)["features"]
    register_model(db, card, actor="test")
    assert db.scalar(select(ModelRecord)).name == "synthetic-scam-baseline"
    assert db.scalar(select(AuditLog.action)) == "model.registered"


def test_case_split_rejects_leakage():
    splits = split_by_case(generate_synthetic_cases(seed=9, case_count=30), seed=9)
    assert_case_disjoint(splits)
    splits["test"].append(splits["train"][0])
    with pytest.raises(ValueError, match="Case leakage"):
        assert_case_disjoint(splits)
