import json
from datetime import UTC, datetime, timedelta

from app.models.case import Case
from app.models.evidence import Event, Evidence
from app.services.correlation_service import CorrelationService


def _source(db, case_id, identifier, filename, source_type):
    item = Evidence(
        case_id=case_id,
        filename=filename,
        content_type="text/plain",
        mime="text/plain",
        source_type=source_type,
        sha256=f"{identifier:064x}",
        md5=f"{identifier:032x}",
        size_bytes=1,
        storage_path=f"/sealed/{identifier}",
        storage_key=str(identifier),
    )
    db.add(item)
    db.flush()
    return item


def test_graph_stays_phases_and_clock_confidence(db):
    case = Case(title="Synthetic correlation case")
    db.add(case)
    db.flush()
    primary = _source(db, case.id, 1, "whatsapp_riya_android.txt", "whatsapp")
    tablet = _source(db, case.id, 2, "whatsapp_second_device_tablet.txt", "whatsapp")
    bank = _source(db, case.id, 3, "bank.csv", "bank_statement")
    gps = _source(db, case.id, 4, "gps.json", "location_history")
    telecom = _source(db, case.id, 5, "tower.csv", "call_records")
    base = datetime(2026, 9, 12, 3, 30, tzinfo=UTC)
    for index, content in enumerate(
        ["Guaranteed investment return", "Trust this safe proof", "OTP bhejo"]
    ):
        db.add(
            Event(
                case_id=case.id,
                evidence_id=primary.id,
                source_type="whatsapp",
                event_type="message",
                timestamp_utc=base + timedelta(minutes=index),
                content=content,
                raw_ref=f"line:{index + 1}",
            )
        )
    tablet_event = Event(
        case_id=case.id,
        evidence_id=tablet.id,
        source_type="whatsapp",
        event_type="message",
        timestamp_utc=base - timedelta(minutes=28),
        content="OTP bhejo",
        raw_ref="line:1",
    )
    db.add(tablet_event)
    rows = [
        ("DEMO-ACCT-RIYA-001", "debit", "DEMO-COLLECT", "U1", 4),
        ("DEMO-COLLECT", "credit", "DEMO-ACCT-RIYA-001", "U1", 5),
        ("DEMO-COLLECT", "debit", "cashout.end@demo", "U2", 8),
    ]
    for account, direction, counterparty, utr, minute in rows:
        db.add(
            Event(
                case_id=case.id,
                evidence_id=bank.id,
                source_type="bank_statement",
                event_type="transaction",
                action=direction,
                timestamp_utc=base + timedelta(minutes=minute),
                content=json.dumps(
                    {
                        "account": account,
                        "type": direction,
                        "counterparty": counterparty,
                        "utr": utr,
                        "amount": "25000",
                    }
                ),
                raw_ref=f"row:{minute}",
            )
        )
    for index, (lat, lon) in enumerate(
        [(28.62, 77.36), (28.6201, 77.3601), (28.625, 77.364), (28.6251, 77.3641)]
    ):
        db.add(
            Event(
                case_id=case.id,
                evidence_id=gps.id,
                source_type="gps",
                event_type="location",
                timestamp_utc=base + timedelta(minutes=10 + index),
                location={"lat": lat, "lon": lon},
                raw_ref=f"location:{index + 1}",
            )
        )
    for index, tower in enumerate(["T1", "T2"]):
        db.add(
            Event(
                case_id=case.id,
                evidence_id=telecom.id,
                source_type="cdr_ipdr",
                event_type="telecom",
                timestamp_utc=base + timedelta(minutes=20 + index),
                content=json.dumps(
                    {
                        "caller": "RIYA",
                        "called": "ARJUN",
                        "cell_id": tower,
                        "tower_lat": "28.62",
                        "tower_lon": "77.36",
                        "coverage_radius_m": "1500",
                        "duration_sec": "30",
                    }
                ),
                raw_ref=f"row:{index + 1}",
            )
        )
    db.commit()

    full = CorrelationService(db).analyse(case.id, clock_confidence=1)
    low = CorrelationService(db).analyse(case.id, clock_confidence=0.2)
    assert full["graph"]["shortest_path"]["nodes"] == [
        "account:DEMO-ACCT-RIYA-001",
        "account:DEMO-COLLECT",
        "account:cashout.end@demo",
    ]
    assert [item["samples"] for item in full["map"]["stay_points"]] == [2, 2]
    assert [item["name"] for item in full["timeline"]["phases"]] == [
        "lure",
        "trust_building",
        "credential_or_otp_request",
        "payment",
        "onward_movement",
    ]
    full_table = {item["event_id"]: item for item in full["timeline"]["all_events"]}
    low_table = {item["event_id"]: item for item in low["timeline"]["all_events"]}
    assert (
        low_table[tablet_event.id]["clock_interval_seconds"][1] - low_table[tablet_event.id]["clock_interval_seconds"][0]
        > full_table[tablet_event.id]["clock_interval_seconds"][1] - full_table[tablet_event.id]["clock_interval_seconds"][0]
    )
