import json
from datetime import UTC, datetime, timedelta

from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.services.money_service import MoneyService


def _transaction(db, case_id, evidence_id, index, timestamp, account, direction, amount, counterparty, utr, balance):
    db.add(
        Event(
            case_id=case_id,
            evidence_id=evidence_id,
            source_app="bank",
            source_type="bank_upi_statement",
            event_type="transaction",
            action=direction,
            timestamp_utc=timestamp,
            content=json.dumps(
                {
                    "account": account,
                    "type": direction,
                    "amount": str(amount),
                    "currency": "INR",
                    "counterparty": counterparty,
                    "utr": utr,
                    "balance": str(balance),
                }
            ),
            raw_ref=f"row:{index}",
            parser_name="csv_records",
            parser_version="2",
        )
    )


def test_onward_flow_rules_and_odd_transfer_are_explained(db):
    case = Case(title="Synthetic money case")
    db.add(case)
    db.flush()
    evidence = Evidence(
        case_id=case.id,
        filename="bank.csv",
        content_type="text/csv",
        mime="text/csv",
        source_type="bank_statement",
        sha256="a" * 64,
        md5="b" * 32,
        size_bytes=100,
        storage_path="/vault/a",
        storage_key="a" * 64,
    )
    db.add(evidence)
    db.flush()
    base = datetime(2026, 9, 12, 3, 55, tzinfo=UTC)
    rows = [
        ("RIYA", "debit", 25000, "arjun.collect@demo", "IN-1", 57500, 0),
        ("COLLECT", "credit", 25000, "RIYA", "IN-1", 25000, 5),
        ("RIYA", "debit", 25000, "arjun.collect@demo", "IN-2", 32500, 480),
        ("COLLECT", "credit", 25000, "RIYA", "IN-2", 50000, 485),
        ("COLLECT", "debit", 30000, "cashout.one@demo", "OUT-1", 20000, 660),
        ("COLLECT", "debit", 19500, "cashout.two@demo", "OUT-2", 500, 780),
        ("RIYA", "debit", 499, "GROCERY", "CARD-1", 32001, 7200),
        ("RIYA", "debit", 9999999, "ODD-DESTINATION", "ODD-1", 0, 10800),
    ]
    for index, (account, direction, amount, counterparty, utr, balance, seconds) in enumerate(rows, 2):
        _transaction(db, case.id, evidence.id, index, base + timedelta(seconds=seconds), account, direction, amount, counterparty, utr, balance)
    db.flush()
    fifo = MoneyService(db).analyse(case.id, "fifo")
    lifo = MoneyService(db).analyse(case.id, "lifo")
    onward = {(edge["amount"], edge["target"]) for edge in fifo["graph"]["edges"]}
    assert (30000.0, "cashout.one@demo") in onward
    assert (19500.0, "cashout.two@demo") in onward
    assert fifo["tracing"]["possible"] != lifo["tracing"]["possible"]
    assert fifo["tracing"]["directly_shown"] and fifo["tracing"]["unexplained"]
    assert fifo["patterns"]["pass_through"]
    assert fifo["anomalies"]
    assert "Largest feature deviation" in fifo["anomalies"][0]["reason"]
