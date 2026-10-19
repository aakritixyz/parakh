from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from importlib.metadata import version as package_version
from pathlib import Path

from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import DocumentExtraction, Event, Evidence


class DocumentExtractionService:
    """Offline text extraction. Evidence bytes are only read, never changed."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def extract(self, evidence: Evidence) -> tuple[DocumentExtraction | None, list[dict]]:
        path = Path(evidence.storage_path)
        suffix = Path(evidence.filename).suffix.casefold()
        warnings: list[dict] = []
        if suffix == ".pdf":
            try:
                text, boxes, used_ocr = self._pdf_text(path)
            except (PdfReadError, ValueError, RuntimeError, OSError) as exc:
                return None, [{"type": "pdf_unreadable", "message": f"PDF extraction failed; original retained: {str(exc)[:160]}"}]
            engine = "pymupdf+tesseract" if used_ocr else "embedded_pdf_text"
            version = package_version("pymupdf")
            languages = ["eng", "hin"] if used_ocr else ["document-declared"]
            if not text.strip():
                warnings.append({"type": "ocr_required", "message": "No text was recovered. Review the original; no content was invented."})
        elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            result = self._tesseract(path)
            if result is None:
                return None, [{"type": "ocr_engine_unavailable", "message": "Install the local Tesseract runtime and English/Hindi language files."}]
            text, boxes, version = result
            engine, languages = "tesseract", ["eng", "hin"]
        else:
            return None, []

        fields = extract_receipt_fields(text, boxes)
        extraction = self.db.scalar(
            select(DocumentExtraction).where(DocumentExtraction.evidence_id == evidence.id)
        )
        if extraction is None:
            extraction = DocumentExtraction(case_id=evidence.case_id, evidence_id=evidence.id)
            self.db.add(extraction)
        extraction.engine = engine
        extraction.engine_version = version
        extraction.languages = languages
        extraction.ocr_text = text
        extraction.boxes = boxes
        extraction.fields = fields
        self.db.flush()
        return extraction, warnings

    @staticmethod
    def _pdf_text(path: Path) -> tuple[str, list[dict], bool]:
        import pymupdf as fitz

        all_text, boxes, used_ocr = [], [], False
        with fitz.open(path) as document:
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text")
                if text.strip():
                    all_text.append(text)
                    for word in page.get_text("words"):
                        boxes.append({"text": word[4], "page": page_number,
                                      "bbox": [word[0]/page.rect.width, word[1]/page.rect.height, word[2]/page.rect.width, word[3]/page.rect.height],
                                      "confidence": 1.0, "coordinate_system": "normalised"})
                else:
                    used_ocr = True
                    with tempfile.TemporaryDirectory(prefix="parakh-ocr-") as folder:
                        image = Path(folder) / "page.png"
                        page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False).save(image)
                        result = DocumentExtractionService._tesseract(image, page_number)
                        if result is None:
                            raise RuntimeError("Local Tesseract English/Hindi runtime unavailable")
                        text, page_boxes, _ = result
                        all_text.append(text)
                        boxes.extend(page_boxes)
        return "\n".join(all_text), boxes, used_ocr

    @staticmethod
    def _embedded_pdf_text(path: Path) -> tuple[str, list[dict]]:
        text, boxes, _ = DocumentExtractionService._pdf_text(path)
        return text, boxes

    @staticmethod
    def _tesseract(path: Path, page_number: int = 1) -> tuple[str, list[dict], str] | None:
        from PIL import Image

        local = Path(__file__).resolve().parents[2] / ".runtime" / "ocr" / "bin" / "tesseract"
        binary = str(local) if local.is_file() else shutil.which("tesseract")
        if binary is None:
            return None
        environment = dict(os.environ)
        environment["OMP_THREAD_LIMIT"] = "1"
        version_result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, check=False, env=environment)
        version = (version_result.stdout.splitlines() or ["unknown"])[0][:80]
        result = subprocess.run([binary, str(path), "stdout", "-l", "eng+hin", "--psm", "6", "tsv"], capture_output=True, text=True, timeout=60, check=False, env=environment)
        if result.returncode != 0:
            raise RuntimeError(f"Local OCR failed: {result.stderr[-160:]}")
        with Image.open(path) as image:
            image_width, image_height = image.size
        boxes = []
        lines: dict[tuple[str, ...], list[str]] = {}
        for row in result.stdout.splitlines()[1:]:
            columns = row.split("\t")
            if len(columns) != 12 or not columns[11].strip():
                continue
            try:
                left, top, width, height = (int(columns[index]) for index in range(6, 10))
                confidence = min(1.0, max(0.0, float(columns[10]) / 100))
            except ValueError:
                continue
            word = columns[11].strip()
            lines.setdefault(tuple(columns[1:5]), []).append(word)
            boxes.append({"text": word, "page": page_number,
                          "bbox": [left/image_width, top/image_height, (left+width)/image_width, (top+height)/image_height],
                          "confidence": confidence, "coordinate_system": "normalised"})
        return "\n".join(" ".join(words) for words in lines.values()), boxes, version


def index_ocr_event(db: Session, evidence: Evidence, extraction_id: int, document: DocumentExtraction | None) -> int:
    if document is None or "tesseract" not in document.engine or not document.ocr_text.strip():
        return 0
    db.add(Event(case_id=evidence.case_id, evidence_id=evidence.id, extraction_id=extraction_id,
                 owner_id=evidence.owner_id, source_app="OCR", source_type=evidence.source_type,
                 event_type="document", action="ocr_extracted", content=document.ocr_text,
                 raw_ref="ocr:document", parser_name=document.engine, parser_version=document.engine_version,
                 confidence=sum(box["confidence"] for box in document.boxes) / max(1, len(document.boxes))))
    db.flush()
    return 1


def extract_receipt_fields(text: str, boxes: list[dict]) -> dict:
    patterns = {
        "amount": r"(?i)(?:INR|₹|Rs\.?)[ ]*([\d,]+(?:\.\d{1,2})?)",
        "date": r"(?i)(?:issued\s+at|date)\s*(\d{1,2}(?:[/.-]\d{1,2}[/.-]\d{2,4}|\s+[A-Za-z]+\s+\d{4}))",
        "time": r"(?is)(?:issued\s+at).{0,50}?(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M|\s*IST)?)",
        "utr": r"(?i)(?:UTR|reference|ref(?:erence)?\s*no)\s*[:#-]?\s*([A-Z0-9-]{6,})",
        "payee": r"(?i)(?:paid\s+to|payee)\s*[:#-]?\s*([^\n]{2,80})",
    }
    fields: dict[str, dict] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group(1).strip()
        receipt = _receipt_for_text(match.group(0), boxes)
        fields[name] = {
            "value": value,
            "confidence": round(receipt.get("confidence", 0.0), 4) if receipt else 0.0,
            "method": "layout_rule",
            "reason": f"Matched the labelled {name} field in extracted document text.",
            "receipt": receipt or {"page": 1, "bbox": None},
        }
    return fields


def _receipt_for_text(fragment: str, boxes: list[dict]) -> dict | None:
    words = {word.casefold() for word in re.findall(r"[\w₹.-]+", fragment)}
    matched = [box for box in boxes if words & {word.casefold() for word in re.findall(r"[\w₹.-]+", box["text"])}]
    if not matched:
        return None
    page = matched[0]["page"]
    matched = [box for box in matched if box["page"] == page]
    return {
        "page": page,
        "bbox": [min(box["bbox"][0] for box in matched), min(box["bbox"][1] for box in matched), max(box["bbox"][2] for box in matched), max(box["bbox"][3] for box in matched)],
        "text": " ".join(box["text"] for box in matched),
        "confidence": sum(box["confidence"] for box in matched) / len(matched),
        "coordinate_system": matched[0].get("coordinate_system", "unknown"),
    }
