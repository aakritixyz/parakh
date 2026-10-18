import hashlib
import json
from datetime import UTC, datetime

from app.models.case import Case
from app.models.evidence import DocumentExtraction, Event, Evidence
from app.services.authenticity_service import AuthenticityService
from app.services.fraud_service import ContradictionService, FraudService


def _evidence(db, case_id, path, filename, source_type, content):
    path.write_bytes(content)
    item = Evidence(
        case_id=case_id,
        filename=filename,
        content_type="application/pdf",
        mime="application/pdf",
        source_type=source_type,
        sha256=hashlib.sha256(content).hexdigest(),
        md5=hashlib.md5(content).hexdigest(),
        size_bytes=len(content),
        storage_path=str(path),
        storage_key=filename,
    )
    db.add(item)
    db.flush()
    return item


def test_receipt_signals_contradiction_and_lead_feedback(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    case = Case(title="Riya synthetic fraud case")
    db.add(case)
    db.flush()
    receipt_bytes = b"%PDF-1.4 /Producer (Tool A) /Creator (Tool B) %%EOF appended %%EOF"
    receipt = _evidence(
        db, case.id, tmp_path / "receipt.pdf", "refund_receipt.pdf", "receipt", receipt_bytes
    )
    near_copy = _evidence(
        db,
        case.id,
        tmp_path / "receipt-copy.pdf",
        "refund_receipt_resaved.pdf",
        "document",
        receipt_bytes + b" ",
    )
    bank = _evidence(db, case.id, tmp_path / "bank.csv", "bank.csv", "bank_statement", b"bank")
    db.add(
        DocumentExtraction(
            case_id=case.id,
            evidence_id=receipt.id,
            engine="test-ocr",
            engine_version="1",
            fields={
                "amount": {"value": "50,000", "confidence": 0.98},
                "utr": {"value": "DEMO-UPI-001", "confidence": 0.98},
                "payee": {"value": "Riya", "confidence": 0.9},
            },
        )
    )
    db.add(
        Event(
            case_id=case.id,
            evidence_id=bank.id,
            source_type="bank_statement",
            event_type="transaction",
            action="debit",
            timestamp_utc=datetime(2026, 9, 12, 3, 55, tzinfo=UTC),
            content=json.dumps(
                {"type": "debit", "amount": "25000", "utr": "DEMO-UPI-001", "counterparty": "Arjun"}
            ),
            raw_ref="row:4",
        )
    )
    db.add(
        Event(
            case_id=case.id,
            evidence_id=receipt.id,
            source_type="whatsapp_chat",
            event_type="message",
            action="message",
            timestamp_utc=datetime(2026, 9, 12, 4, 12, tzinfo=UTC),
            content="Refund approved, double money guaranteed",
            raw_ref="line:23",
        )
    )
    db.commit()

    report = AuthenticityService(db).report(receipt)
    assert report.suspicion_score >= 50
    assert report.score_range[0] < report.score_range[1]
    assert any(item.signal.startswith("ocr_bank_mismatch") for item in report.findings)
    assert report.similar_documents[0]["evidence_id"] == near_copy.id

    contradiction = ContradictionService(db).analyse(case.id)["contradictions"][0]
    assert contradiction["match"]["reference_match"] is True
    results = {item["name"]: item["result"] for item in contradiction["alternatives"]}
    assert results["wrong device clock"] == "ruled out for this mismatch"
    assert results["altered document"] == "remains plausible"

    board = FraudService(db).board(case.id)
    assert board["ranked"][0]["title"] == "Document manipulation suspected"
    assert {item["title"] for item in board["ranked"][:3]} == {
        "Document manipulation suspected",
        "Possible mule or collection account",
        "Coordinated scam communication",
    }
    dismissed = FraudService(db).update_lead(
        case.id,
        board["ranked"][0]["id"],
        "investigator",
        "dismissed",
        None,
        "Reviewed and dismissed",
    )
    assert all(item["title"] != "Document manipulation suspected" for item in dismissed["ranked"])
