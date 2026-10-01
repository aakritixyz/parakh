import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select

from app.ml.entities import extract_entities
from app.models.evidence import Event
from app.models.investigation import Job
from app.parsers.concrete import CsvParser
from app.parsers.registry import ParserRegistry
from app.services.evidence_service import EvidenceService
from app.storage.content_addressed import ContentAddressedStorage


def test_india_normalization_handles_common_phone_variants():
    values = extract_entities("Call 09876543210 or 91-98765-43210; pay ARJUN@UPI and IFSC hdfc0001234")
    canonicals = {item["canonical"] for item in values}
    assert "+919876543210" in canonicals
    assert "arjun@upi" in canonicals
    assert "HDFC0001234" in canonicals


def test_parser_capabilities_are_declared():
    capabilities = ParserRegistry.capabilities()
    assert any(item["name"] == "whatsapp_text_export" and item["status"] == "beta" for item in capabilities)
    assert all("version" in item and "formats" in item for item in capabilities)


def test_ingest_persists_job_status(db, tmp_path: Path):
    storage = ContentAddressedStorage(tmp_path / "storage")
    service = EvidenceService(db, storage)
    upload = UploadFile(
        filename="whatsapp_chat.txt",
        file=BytesIO(b"12/09/2026, 09:10 - Riya: paid arjun@upi"),
    )

    asyncio.run(service.ingest(1, upload, "tester", "phase2-upload"))
    db.commit()

    job = db.scalar(select(Job).where(Job.type == "ingest_extraction"))
    assert job is not None
    assert job.status == "completed"
    assert job.progress == 100
    assert any("Detected parser" in line for line in job.logs)


def test_ingest_sets_dedupe_hash_and_reparse_replaces_events(db, tmp_path: Path):
    storage = ContentAddressedStorage(tmp_path / "storage")
    service = EvidenceService(db, storage)
    upload = UploadFile(
        filename="whatsapp_chat.txt",
        file=BytesIO(
            b"12/09/2026, 09:10 - Riya: paid arjun@upi\n"
            b"12/09/2026, 09:11 - Arjun: send OTP"
        ),
    )

    evidence = asyncio.run(service.ingest(1, upload, "tester", "phase2-reparse"))
    db.commit()
    first_hashes = [event.dedupe_hash for event in evidence.events]
    assert len(first_hashes) == 2
    assert all(first_hashes)

    result = service.reparse(evidence.id, "tester")
    db.commit()
    events = list(db.scalars(select(Event).where(Event.evidence_id == evidence.id)))
    assert result["deleted"] == 2
    assert result["inserted"] == 2
    assert [event.dedupe_hash for event in events] == first_hashes


def test_csv_schema_detection_prefers_financial_columns(tmp_path: Path):
    path = tmp_path / "statement.csv"
    path.write_text("date,amount,utr,vpa\n2026-09-12,25000,UTR123,arjun@upi\n")
    events = CsvParser().parse(path, case_id=1, evidence_id=2)
    assert events[0].source_type == "bank_upi_statement"
