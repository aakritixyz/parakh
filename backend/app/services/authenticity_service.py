from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

try:
    from pypdf import PdfReader as _PdfReader
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight environments
    PdfReader: Any | None = None
else:
    PdfReader = _PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.services.evidence_service import EvidenceService


@dataclass
class Finding:
    severity: str
    explanation: str
    signal: str


@dataclass
class AuthenticityReport:
    evidence_id: int
    score: int
    findings: list[Finding] = field(default_factory=list)
    stub_detectors: list[str] = field(default_factory=list)


class AuthenticityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def report(self, evidence: Evidence) -> AuthenticityReport:
        findings: list[Finding] = []
        if not EvidenceService(self.db).verify_integrity(evidence)["valid"]:
            findings.append(Finding("critical", "Stored bytes no longer match original SHA-256.", "sha256_mismatch"))
        path = Path(evidence.storage_path)
        if evidence.source_type == "image":
            findings.extend(self._image_findings(path, evidence))
        elif evidence.source_type == "pdf":
            findings.extend(self._pdf_findings(path, evidence))
        elif evidence.source_type == "whatsapp_chat":
            findings.extend(self._chat_findings(evidence.id))
        score = max(0, 100 - sum({"low": 8, "medium": 18, "high": 35, "critical": 70}[f.severity] for f in findings))
        return AuthenticityReport(
            evidence_id=evidence.id,
            score=score,
            findings=findings,
            stub_detectors=["deepfake_detector_interface_stub"],
        )

    def _image_findings(self, path: Path, evidence: Evidence) -> list[Finding]:
        findings = []
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                findings.append(Finding("medium", "Image has no EXIF metadata; it may be stripped or exported.", "missing_exif"))
            software = str(exif.get(305, "")).lower()
            if any(tool in software for tool in ["photoshop", "gimp", "snapseed"]):
                findings.append(Finding("high", "Image software tag suggests editing software.", f"software={software}"))
            if img.format == "JPEG":
                recompressed = path.with_suffix(".ela.jpg")
                img.convert("RGB").save(recompressed, "JPEG", quality=90)
                diff = ImageChops.difference(img.convert("RGB"), Image.open(recompressed))
                mean = sum(ImageStat.Stat(diff).mean) / 3
                recompressed.unlink(missing_ok=True)
                if mean > 12:
                    findings.append(Finding("medium", "Error-level signal is uneven; inspect image manually.", f"ela_mean={mean:.2f}"))
        if evidence.metadata_json.get("size") == [1, 1]:
            findings.append(Finding("low", "Tiny placeholder image detected.", "image_size=1x1"))
        return findings

    def _pdf_findings(self, path: Path, evidence: Evidence) -> list[Finding]:
        findings = []
        raw = path.read_bytes()
        eof_count = raw.count(b"%%EOF")
        if eof_count > 1:
            findings.append(Finding("high", "PDF contains multiple EOF markers, suggesting incremental updates.", f"eof_count={eof_count}"))
        if PdfReader is None:
            findings.append(Finding("low", "PDF metadata parser is unavailable in this environment.", "pypdf_not_installed"))
            return findings
        reader = PdfReader(str(path))
        meta: dict[str, Any] = dict(reader.metadata or {})
        created = str(meta.get("/CreationDate", ""))
        modified = str(meta.get("/ModDate", ""))
        if created and modified and created != modified:
            findings.append(Finding("medium", "PDF creation and modification timestamps differ.", f"created={created}, modified={modified}"))
        producer = str(meta.get("/Producer", "")).lower()
        if "unknown" in producer or "modified" in producer:
            findings.append(Finding("low", "PDF producer metadata is unusual.", f"producer={producer}"))
        return findings

    def _chat_findings(self, evidence_id: int) -> list[Finding]:
        findings = []
        events = list(self.db.scalars(select(Event).where(Event.evidence_id == evidence_id).order_by(Event.id)))
        previous = None
        for event in events:
            if previous and event.timestamp_utc and previous.timestamp_utc and event.timestamp_utc < previous.timestamp_utc:
                findings.append(Finding("high", "Chat timestamps are non-monotonic.", f"event_id={event.id}"))
                break
            previous = event
        if len(events) < 2:
            findings.append(Finding("low", "Chat export contains very few parseable messages.", "low_event_count"))
        return findings
