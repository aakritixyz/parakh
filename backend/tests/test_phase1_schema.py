import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import inspect, select

from app.core.database import Base
from app.models.investigation import Extraction
from app.services.evidence_service import EvidenceService
from app.storage.content_addressed import ContentAddressedStorage


def test_phase1_tables_are_registered(db):
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    assert {
        "devices",
        "extractions",
        "owners",
        "parties",
        "identifiers",
        "threads",
        "artifacts",
        "jobs",
        "authenticity_reports",
    } <= tables
    event_columns = {column.name for column in Base.metadata.tables["events"].columns}
    assert {"event_type", "extraction_id", "dedupe_hash", "parser_name"} <= event_columns


def test_ingest_creates_extraction_and_links_events(db, tmp_path: Path):
    storage = ContentAddressedStorage(tmp_path / "storage")
    service = EvidenceService(db, storage)
    upload = UploadFile(
        filename="whatsapp_chat.txt",
        file=BytesIO(b"12/09/2026, 09:10 - Riya: paid arjun@upi"),
    )

    evidence = asyncio.run(service.ingest(1, upload, "tester", "phase1-upload"))
    db.commit()

    extraction = db.scalar(select(Extraction).where(Extraction.evidence_id == evidence.id))
    assert extraction is not None
    assert extraction.parse_status == "complete"
    assert evidence.events
    assert evidence.events[0].extraction_id == extraction.id
    assert evidence.events[0].event_type == "message"
    assert evidence.events[0].parser_name == "WhatsAppParser"
