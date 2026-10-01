from app.ml.citations import verify_citations
from app.ml.entities import extract_entities
from app.models.evidence import Event
from app.services.analysis_service import AnalysisService


def test_india_entity_patterns_mask_aadhaar():
    values = extract_entities("Call +91 9876543210 UPI arjun@upi Aadhaar 1234 5678 9012 IFSC HDFC0001234 PAN ABCDE1234F")
    assert any(v["canonical"] == "+919876543210" for v in values)
    assert any(v["canonical"] == "XXXX-XXXX-9012" for v in values)


def test_fraud_rules(db):
    db.add(Event(case_id=1, evidence_id=1, source_type="whatsapp_chat", content="guaranteed return urgent payment arjun@upi arjun@upi arjun@upi"))
    db.commit()
    findings = AnalysisService(db).fraud_rules(1)
    assert any(f["type"] == "scam_language" for f in findings)
    assert any(f["type"] == "mule_account_fan_in" for f in findings)


def test_citation_enforcement():
    assert verify_citations("Payment happened [evidence_id=1, event_id=2].")["valid"]
    assert not verify_citations("Payment happened without support.")["valid"]
