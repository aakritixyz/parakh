import hashlib
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import select

from app.models.evidence import Event
from app.services import alias_model_service
from app.services.assistant_service import AssistantService, RetrievedItem
from app.services.document_extraction_service import (
    DocumentExtractionService,
    extract_receipt_fields,
)
from app.services.event_search_service import EventSearchService
from app.services.monte_carlo import event_ordering
from tests.test_step4_step5 import _case_records
from tests.test_step15_assistant import source


def test_semantic_validator_rejects_same_amount_opposite_claim(db, monkeypatch):
    evidence = source(db)
    event = Event(id=1, case_id=1, evidence_id=evidence.id, event_type="transaction", content="Riya paid INR 25000 to arjun@upi", raw_ref="row:4")
    item = RetrievedItem(evidence, event.content, 1, event=event)
    from app.services import assistant_service
    model = SimpleNamespace(entail=lambda *args: {"entailment": .02, "contradiction": .97})
    monkeypatch.setattr(assistant_service, "local_model", lambda kind: model)
    assert not AssistantService._validate_claims([{"text": "Riya received a refund of INR 25000 from arjun@upi", "citations": [item.citation]}], [item])
    citation = {**item.citation, "sha256": "f" * 64}
    assert not AssistantService._validate_claims([{"text": "Riya paid INR 25000", "citations": [citation]}], [item])


def test_clock_samples_repeat_widen_and_preserve_same_device_order():
    start = datetime(2026, 9, 1, tzinfo=UTC)
    events = [SimpleNamespace(id=1, evidence_id=1, timestamp_utc=start),
              SimpleNamespace(id=2, evidence_id=2, timestamp_utc=start + timedelta(seconds=15)),
              SimpleNamespace(id=3, evidence_id=2, timestamp_utc=start + timedelta(seconds=20))]
    full = event_ordering(events, 2, 0, [-10, 10], 1)
    assert full == event_ordering(events, 2, 0, [-10, 10], 1)
    low = event_ordering(events, 2, 0, [-10, 10], .1)
    assert low["events"][2]["ordering_probability"] < full["events"][2]["ordering_probability"]
    assert next(pair for pair in low["pairs"] if pair["before_event_id"] == 2)["probability"] == 1
    assert events[1].timestamp_utc == start + timedelta(seconds=15)


def test_sql_index_refreshes_after_event_edit_and_reparse(db):
    case, _ = _case_records(db)
    service = EventSearchService(db)
    assert service.search(case.id, {"q": "refund"})["total_matching"] == 1
    event = db.scalar(select(Event).where(Event.event_type == "message"))
    event.content = "meeting tomorrow"
    db.flush()
    assert service.search(case.id, {"q": "refund"})["total_matching"] == 0
    assert service.search(case.id, {"q": "meeting"})["total_matching"] == 1


def test_alias_model_split_calibration_and_exact_shap(tmp_path, monkeypatch):
    card = alias_model_service.train_alias(tmp_path)
    groups = [set(value) for value in card["case_split"].values()]
    assert not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
    import joblib
    monkeypatch.setattr(alias_model_service, "load_alias", lambda: (joblib.load(tmp_path / "model.joblib"), card))
    result = alias_model_service.alias_prediction({"normalised_edit_similarity": .9, "jaro_winkler": .95, "shared_devices": 1})
    assert sum(result["shap"].values()) == pytest.approx(result["confidence"] - result["base_value"])
    assert card["metrics"]["label"] == "on synthetic data"


@pytest.mark.skipif(os.environ.get("PARAKH_TEST_MODELS") != "1", reason="Explicit local runtime integration")
def test_real_offline_embeddings_nli_and_scanned_receipt(tmp_path):
    from app.services.offline_models import local_model
    model = local_model("embeddings")
    passages = model.embed(["Please refund my money", "The weather is sunny"])
    scores = passages @ model.embed(["paise wapas"], query=True)[0]
    assert scores[0] > scores[1]
    result = local_model("entailment").entail("Riya paid INR 25000 to Arjun. No refund was received.", "Riya received a refund of INR 25000.")
    assert result["entailment"] < .85
    import pymupdf as fitz
    pack = next((__import__('pathlib').Path(__file__).resolve().parents[2] / "evidence").rglob("*receipt*.pdf"))
    with fitz.open(pack) as original:
        bitmap = original[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
    scanned = tmp_path / "scanned.pdf"
    with fitz.open() as output:
        page = output.new_page(width=bitmap.width, height=bitmap.height)
        page.insert_image(page.rect, stream=bitmap.tobytes("png"))
        output.save(scanned)
    before = hashlib.sha256(scanned.read_bytes()).hexdigest()
    text, boxes, used_ocr = DocumentExtractionService._pdf_text(scanned)
    fields = extract_receipt_fields(text, boxes)
    assert used_ocr and boxes
    assert all(name in fields for name in ("amount", "time", "payee"))
    assert all(0 < fields[name]["confidence"] <= 1 for name in ("amount", "time", "payee"))
    assert all(0 <= value <= 1 for box in boxes for value in box["bbox"])
    assert before == hashlib.sha256(scanned.read_bytes()).hexdigest()
    np.testing.assert_allclose(model.embed(["Please refund my money"])[0], passages[0], atol=1e-5)
