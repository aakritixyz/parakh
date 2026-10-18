from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import DocumentExtraction, Evidence


class DocumentExtractionService:
    """Offline text extraction. Evidence bytes are only read, never changed."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def extract(self, evidence: Evidence) -> tuple[DocumentExtraction | None, list[dict]]:
        path = Path(evidence.storage_path)
        suffix = Path(evidence.filename).suffix.casefold()
        warnings: list[dict] = []
        if suffix == ".pdf":
            text, boxes = self._embedded_pdf_text(path)
            engine, version, languages = "embedded_pdf_text", "pypdf", ["document-declared"]
            if not text.strip():
                warnings.append(
                    {
                        "type": "ocr_required",
                        "message": "This scanned PDF has no embedded text and needs an offline OCR rasterizer.",
                    }
                )
        elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            result = self._tesseract(path)
            if result is None:
                return None, [
                    {
                        "type": "ocr_engine_unavailable",
                        "message": "Tesseract is not installed; image OCR was not run.",
                    }
                ]
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
    def _embedded_pdf_text(path: Path) -> tuple[str, list[dict]]:
        reader = PdfReader(str(path))
        all_text: list[str] = []
        boxes: list[dict] = []
        for page_number, page in enumerate(reader.pages, start=1):
            lines = (page.extract_text() or "").splitlines()
            all_text.extend(lines)
            for line_number, line in enumerate(lines, start=1):
                boxes.append(
                    {
                        "text": line,
                        "page": page_number,
                        "bbox": [
                            0.05,
                            min(0.95, 0.04 * line_number),
                            0.95,
                            min(0.99, 0.04 * line_number + 0.03),
                        ],
                        "confidence": 1.0,
                        "coordinate_system": "normalised_estimate",
                    }
                )
        return "\n".join(all_text), boxes

    @staticmethod
    def _tesseract(path: Path) -> tuple[str, list[dict], str] | None:
        binary = shutil.which("tesseract")
        if binary is None:
            return None
        version_result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
        version = (version_result.stdout.splitlines() or ["unknown"])[0][:40]
        result = subprocess.run(
            [binary, str(path), "stdout", "-l", "eng+hin", "tsv"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            return "", [], version
        boxes: list[dict] = []
        words: list[str] = []
        rows = result.stdout.splitlines()
        for row in rows[1:]:
            columns = row.split("\t")
            if len(columns) != 12 or not columns[11].strip():
                continue
            try:
                left, top, width, height = (int(columns[index]) for index in range(6, 10))
                confidence = max(0.0, float(columns[10]) / 100)
            except ValueError:
                continue
            word = columns[11].strip()
            words.append(word)
            boxes.append(
                {
                    "text": word,
                    "page": 1,
                    "bbox": [left, top, left + width, top + height],
                    "confidence": confidence,
                    "coordinate_system": "pixels",
                }
            )
        return " ".join(words), boxes, version


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
            "confidence": 0.98 if receipt else 0.86,
            "method": "layout_rule",
            "reason": f"Matched the labelled {name} field in extracted document text.",
            "receipt": receipt or {"page": 1, "bbox": None},
        }
    return fields


def _receipt_for_text(fragment: str, boxes: list[dict]) -> dict | None:
    words = {word.casefold() for word in re.findall(r"[A-Za-z0-9₹.-]+", fragment)}
    for box in boxes:
        if words & {word.casefold() for word in re.findall(r"[A-Za-z0-9₹.-]+", box["text"])}:
            return {"page": box["page"], "bbox": box["bbox"], "text": box["text"]}
    return None
