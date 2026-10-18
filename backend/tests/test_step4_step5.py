from datetime import UTC, datetime

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.models.investigation import Owner
from app.services.event_search_service import EventSearchService
from app.services.identity_service import IdentityService


def _case_records(db):
    case = Case(title="Riya: investment scam complaint")
    db.add(case)
    db.flush()
    owner = Owner(case_id=case.id, display_name="Riya")
    db.add(owner)
    db.flush()
    evidence = Evidence(
        case_id=case.id,
        filename="bank_statement.csv",
        content_type="text/csv",
        mime="text/csv",
        source_type="bank_statement",
        sha256="a" * 64,
        md5="b" * 32,
        size_bytes=100,
        storage_path="/vault/a",
        storage_key="a" * 64,
        owner_id=owner.id,
    )
    db.add(evidence)
    db.flush()
    db.add_all(
        [
            Event(
                case_id=case.id,
                evidence_id=evidence.id,
                owner_id=owner.id,
                source_app="bank",
                source_type="bank_statement",
                event_type="transaction",
                action="debit",
                timestamp_utc=datetime(2026, 9, 12, 4, 10, tzinfo=UTC),
                actor_entities=["Agent Arjun"],
                content="Paid INR 25000 to arjun.collect@demo",
                raw_ref="row:4",
                parser_name="bank_csv",
                parser_version="1",
            ),
            Event(
                case_id=case.id,
                evidence_id=evidence.id,
                owner_id=owner.id,
                source_app="whatsapp",
                source_type="chat",
                event_type="message",
                action="message",
                timestamp_utc=datetime(2026, 9, 12, 4, 12, tzinfo=UTC),
                actor_entities=["Riya"],
                content="paise wapas bhejo, refund kab aayega?",
                raw_ref="line:20",
                parser_name="whatsapp",
                parser_version="1",
            ),
        ]
    )
    db.flush()
    return case, evidence


def test_alias_merge_is_ranked_reasoned_reversible_and_audited(db):
    case, _ = _case_records(db)
    service = IdentityService(db)
    overview = service.overview(case.id)
    match = next(
        item
        for item in overview["suggestions"]
        if item["party"] == "Agent Arjun" and item["identifier"] == "arjun.collect@demo"
    )
    assert match["confidence"] >= 0.7
    assert any("Shared token: arjun" in reason for reason in match["reasons"])
    service.confirm(case.id, match["id"], "investigator")
    service.unmerge(case.id, match["id"], "investigator")
    assert list(db.scalars(select(AuditLog.action))) == ["alias.merged", "alias.unmerged"]


def test_shared_search_filters_and_receipt_detail(db):
    case, evidence = _case_records(db)
    service = EventSearchService(db)
    result = service.search(
        case.id,
        {
            "facets": {
                "owner": "Riya",
                "type": "payment",
                "identifier": "arjun.collect@demo",
                "source": evidence.filename,
            }
        },
    )
    assert result["total_matching"] == 1
    assert result["facets"]["types"] == [{"value": "transaction", "count": 1}]
    assert result["histogram"] == [{"bucket": "2026-09-12", "count": 1}]
    detail = service.detail(case.id, result["items"][0]["event_id"])
    assert detail["source"]["reference"] == "row:4"
    assert detail["source"]["sha256"] == "a" * 64
    refund = service.search(case.id, {"q": "paise wapas"})
    assert refund["total_matching"] == 1
    assert "refund" in refund["items"][0]["content"]
