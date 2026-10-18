import json
import random
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

PDF_READ_ERRORS: tuple[type[Exception], ...] = (ValueError,)
try:
    from pypdf import PdfReader as _PdfReader
    from pypdf.errors import PdfReadError as _PdfReadError
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight environments
    PdfReader: Any | None = None
else:
    PdfReader = _PdfReader
    PDF_READ_ERRORS = (ValueError, _PdfReadError)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.evidence import DocumentExtraction, Event, Evidence
from app.services.evidence_service import EvidenceService


@dataclass
class Finding:
    severity: str
    explanation: str
    signal: str
    weight: float = 0
    contribution: float = 0
    heuristic: bool = True


@dataclass
class AuthenticityReport:
    evidence_id: int
    score: int
    suspicion_score: int
    score_range: list[int]
    findings: list[Finding] = field(default_factory=list)
    similar_documents: list[dict] = field(default_factory=list)
    ocr_claims: dict = field(default_factory=dict)
    ela_overlay: str | None = None
    limits: str = "Heuristic signals support review; they do not establish that a document is fake."
    detector_status: dict = field(default_factory=dict)
    stub_detectors: list[str] = field(default_factory=list)


class AuthenticityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def report(self, evidence: Evidence) -> AuthenticityReport:
        findings: list[Finding] = []
        if not EvidenceService(self.db).verify_integrity(evidence)["valid"]:
            findings.append(
                Finding(
                    "critical", "Stored bytes no longer match original SHA-256.", "sha256_mismatch"
                )
            )
        path = Path(evidence.storage_path)
        ela_overlay = None
        if evidence.source_type == "image" or path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            image_findings, ela_overlay = self._image_findings(path, evidence)
            findings.extend(image_findings)
        elif (
            evidence.source_type in {"pdf", "receipt", "bank_statement", "document"}
            or path.suffix.lower() == ".pdf"
        ):
            findings.extend(self._pdf_findings(path, evidence))
        elif evidence.source_type == "whatsapp_chat":
            findings.extend(self._chat_findings(evidence.id))
        extraction = self.db.scalar(
            select(DocumentExtraction).where(DocumentExtraction.evidence_id == evidence.id)
        )
        ocr_claims = extraction.fields if extraction else {}
        findings.extend(self._claim_findings(evidence, ocr_claims))
        similar = self._similar_documents(evidence)
        if similar:
            best = similar[0]
            findings.append(
                Finding(
                    "medium",
                    f"Near-duplicate content was found in {best['filename']} ({best['similarity']:.0%}).",
                    f"near_duplicate_evidence={best['evidence_id']}",
                )
            )
        weights = {"low": 8.0, "medium": 18.0, "high": 35.0, "critical": 70.0}
        for finding in findings:
            finding.weight = weights[finding.severity]
            finding.contribution = finding.weight
        suspicion = round(min(100.0, sum(item.contribution for item in findings)))
        try:
            seed = int(evidence.sha256[:8], 16)
        except (TypeError, ValueError):
            seed = 0
        rng = random.Random(seed)
        samples = sorted(
            min(100.0, sum(item.weight * rng.betavariate(8, 2) for item in findings))
            for _ in range(1000)
        )
        score_range = [round(samples[25]), round(samples[974])] if samples else [0, 0]
        return AuthenticityReport(
            evidence_id=evidence.id,
            score=max(0, 100 - suspicion),
            suspicion_score=suspicion,
            score_range=score_range,
            findings=findings,
            similar_documents=similar,
            ocr_claims=ocr_claims,
            ela_overlay=ela_overlay,
            detector_status={
                "kind": "weighted_heuristics",
                "samples": 1000,
                "seed": seed,
                "image_embeddings": "planned_T2_not_assessed",
                "neural_tamper_localisation": "planned_T3_not_assessed",
                "deepfake_detection": "planned_T3_not_assessed",
            },
            stub_detectors=["neural_tamper_localisation_planned", "deepfake_detector_planned"],
        )

    def _image_findings(self, path: Path, evidence: Evidence) -> tuple[list[Finding], str | None]:
        findings = []
        overlay = None
        with Image.open(path) as img:
            exif = img.getexif()
            recorded_size = evidence.metadata_json.get("pixel_size") or evidence.metadata_json.get(
                "size"
            )
            if recorded_size and list(img.size) != list(recorded_size):
                findings.append(
                    Finding(
                        "medium",
                        "Decoded image dimensions do not match the recorded thumbnail metadata.",
                        f"thumbnail_dimension_mismatch={recorded_size}->{list(img.size)}",
                    )
                )
            if not exif:
                findings.append(
                    Finding(
                        "medium",
                        "Image has no EXIF metadata; it may be stripped or exported.",
                        "missing_exif",
                    )
                )
            software = str(exif.get(305, "")).lower()
            if any(tool in software for tool in ["photoshop", "gimp", "snapseed"]):
                findings.append(
                    Finding(
                        "high",
                        "Image software tag suggests editing software.",
                        f"software={software}",
                    )
                )
            if img.format == "JPEG":
                derived = Path(get_settings().storage_root) / "derived" / "ela"
                derived.mkdir(parents=True, exist_ok=True)
                recompressed = derived / f"{evidence.id}-ela-source.jpg"
                img.convert("RGB").save(recompressed, "JPEG", quality=90)
                diff = ImageChops.difference(img.convert("RGB"), Image.open(recompressed))
                mean = sum(ImageStat.Stat(diff).mean) / 3
                overlay_path = derived / f"{evidence.id}-ela-overlay.png"
                diff.save(overlay_path)
                overlay = str(overlay_path)
                recompressed.unlink(missing_ok=True)
                if mean > 12:
                    findings.append(
                        Finding(
                            "medium",
                            "Error-level signal is uneven; inspect image manually.",
                            f"ela_mean={mean:.2f}",
                        )
                    )
        if evidence.metadata_json.get("size") == [1, 1]:
            findings.append(Finding("low", "Tiny placeholder image detected.", "image_size=1x1"))
        return findings, overlay

    def _pdf_findings(self, path: Path, evidence: Evidence) -> list[Finding]:
        findings = []
        raw = path.read_bytes()
        eof_count = raw.count(b"%%EOF")
        if eof_count > 1:
            findings.append(
                Finding(
                    "high",
                    "PDF contains multiple EOF markers, suggesting incremental updates.",
                    f"eof_count={eof_count}",
                )
            )
        raw_text = raw.decode("latin-1", errors="ignore")
        tools = re.findall(r"/(?:Producer|Creator)\s*\(([^)]*)\)", raw_text, re.I)
        if len({item.strip().casefold() for item in tools if item.strip()}) > 1:
            findings.append(
                Finding(
                    "medium",
                    "Producer and creator metadata name inconsistent tools.",
                    f"producer_creator={tools}",
                )
            )
        fonts = set(re.findall(r"/BaseFont\s*/([^\s/<>\[\]()]+)", raw_text))
        if len(fonts) > 4:
            findings.append(
                Finding(
                    "low",
                    f"The document uses {len(fonts)} font names; inspect visual consistency.",
                    f"font_count={len(fonts)}",
                )
            )
        if b"/Metadata" not in raw and b"/Info" not in raw:
            findings.append(
                Finding(
                    "low",
                    "Document metadata appears stripped. Export tools may also remove it.",
                    "stripped_metadata",
                )
            )
        if PdfReader is None:
            findings.append(
                Finding(
                    "low",
                    "PDF metadata parser is unavailable in this environment.",
                    "pypdf_not_installed",
                )
            )
            return findings
        try:
            reader = PdfReader(str(path))
            meta: dict[str, Any] = dict(reader.metadata or {})
        except PDF_READ_ERRORS:
            findings.append(
                Finding(
                    "medium",
                    "PDF structure could not be read; original bytes are retained for manual review. This alone does not prove manipulation.",
                    "pdf_unreadable",
                )
            )
            return findings
        created = str(meta.get("/CreationDate", ""))
        modified = str(meta.get("/ModDate", ""))
        if created and modified and created != modified:
            findings.append(
                Finding(
                    "medium",
                    "PDF creation and modification timestamps differ.",
                    f"created={created}, modified={modified}",
                )
            )
        producer = str(meta.get("/Producer", "")).lower()
        if "unknown" in producer or "modified" in producer:
            findings.append(
                Finding("low", "PDF producer metadata is unusual.", f"producer={producer}")
            )
        return findings

    def _claim_findings(self, evidence: Evidence, claims: dict) -> list[Finding]:
        if evidence.source_type != "receipt" or not claims:
            return []
        reference = str((claims.get("utr") or {}).get("value", ""))
        amount_text = str((claims.get("amount") or {}).get("value", "0"))
        amount = float(re.sub(r"[^0-9.]", "", amount_text) or 0)
        events = self.db.scalars(
            select(Event).where(
                Event.case_id == evidence.case_id, Event.event_type == "transaction"
            )
        )
        for event in events:
            try:
                row = json.loads(event.content)
            except json.JSONDecodeError:
                continue
            if reference and str(row.get("utr", "")) == reference:
                recorded = float(row.get("amount", 0))
                direction = str(row.get("type") or event.action).casefold()
                if abs(recorded - amount) > 0.01 or direction != "credit":
                    return [
                        Finding(
                            "high",
                            f"OCR claims an incoming {amount_text} receipt, but the same reference points to a {direction} of INR {recorded:,.2f}.",
                            f"ocr_bank_mismatch_event={event.id}",
                        )
                    ]
        return [
            Finding(
                "medium",
                "No bank row with the OCR reference appears in the supplied coverage.",
                f"ocr_reference_unmatched={reference}",
            )
        ]

    def _similar_documents(self, evidence: Evidence) -> list[dict]:
        source = Path(evidence.storage_path)
        if not source.is_file() or source.stat().st_size > 20_000_000:
            return []
        left = re.sub(rb"\s+", b" ", source.read_bytes()[:2_000_000])
        results = []
        candidates = self.db.scalars(
            select(Evidence).where(Evidence.case_id == evidence.case_id, Evidence.id != evidence.id)
        )
        for candidate in candidates:
            other = Path(candidate.storage_path)
            if not other.is_file() or other.stat().st_size > 20_000_000:
                continue
            right = re.sub(rb"\s+", b" ", other.read_bytes()[:2_000_000])
            method = "rolling fuzzy hash fallback (TLSH/ssdeep unavailable)"
            similarity = SequenceMatcher(None, left, right, autojunk=False).ratio()
            if source.suffix.casefold() in {
                ".jpg",
                ".jpeg",
                ".png",
            } and other.suffix.casefold() in {".jpg", ".jpeg", ".png"}:
                try:
                    left_hash, right_hash = self._dhash(source), self._dhash(other)
                    similarity = 1 - (left_hash ^ right_hash).bit_count() / 64
                    method = "dHash Hamming distance"
                except OSError:
                    pass
            if similarity >= 0.82:
                results.append(
                    {
                        "evidence_id": candidate.id,
                        "filename": candidate.filename,
                        "similarity": round(similarity, 4),
                        "method": method,
                    }
                )
        return sorted(results, key=lambda item: item["similarity"], reverse=True)

    @staticmethod
    def _dhash(path: Path) -> int:
        with Image.open(path) as image:
            pixels = list(image.convert("L").resize((9, 8)).getdata())
        return sum(
            (pixels[row * 9 + column] > pixels[row * 9 + column + 1]) << (row * 8 + column)
            for row in range(8)
            for column in range(8)
        )

    def _chat_findings(self, evidence_id: int) -> list[Finding]:
        findings = []
        events = list(
            self.db.scalars(
                select(Event).where(Event.evidence_id == evidence_id).order_by(Event.id)
            )
        )
        previous = None
        for event in events:
            if (
                previous
                and event.timestamp_utc
                and previous.timestamp_utc
                and event.timestamp_utc < previous.timestamp_utc
            ):
                findings.append(
                    Finding("high", "Chat timestamps are non-monotonic.", f"event_id={event.id}")
                )
                break
            previous = event
        if len(events) < 2:
            findings.append(
                Finding(
                    "low", "Chat export contains very few parseable messages.", "low_event_count"
                )
            )
        return findings
