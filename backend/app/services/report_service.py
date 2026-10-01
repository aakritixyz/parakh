import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback
    A4 = None
    canvas = None
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Event, Evidence
from app.models.report import Report
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.services.authenticity_service import AuthenticityService


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_case_report(self, case_id: int) -> Report:
        out_dir = Path("reports")
        out_dir.mkdir(exist_ok=True)
        path = out_dir / f"case-{case_id}-court-report.pdf"
        lines = self._report_lines(case_id)
        if canvas is None or A4 is None:
            write_minimal_pdf(path, lines)
        else:
            self._write_reportlab_pdf(path, lines)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        report = Report(case_id=case_id, path=str(path), sha256=digest)
        self.db.add(report)
        self.db.flush()
        AuditService(self.db).log(action="report.exported", case_id=case_id, target_type="report", target_id=str(report.id), payload={"sha256": digest})
        return report

    def export_case_bundle(self, case_id: int) -> Report:
        out_dir = Path("reports")
        out_dir.mkdir(exist_ok=True)
        bundle_path = out_dir / f"case-{case_id}-portable-bundle.zip"
        evidence = list(self.db.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id)))
        events = list(self.db.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.timestamp_utc, Event.id)))
        audit = AuditService(self.db).verify_chain()
        manifest = {
            "format": "parakh-portable-case-bundle-v1",
            "case_id": case_id,
            "draft_notice": "DRAFT bundle for investigative review; verify with legal counsel before court use.",
            "audit_verification": audit,
            "evidence": [
                {
                    "id": item.id,
                    "filename": item.filename,
                    "sha256": item.sha256,
                    "md5": item.md5,
                    "size_bytes": item.size_bytes,
                    "source_type": item.source_type,
                }
                for item in evidence
            ],
        }
        with ZipFile(bundle_path, "w", ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
            bundle.writestr("evidence_index.csv", _evidence_csv(evidence))
            bundle.writestr("events.csv", _events_csv(events))
            bundle.writestr("viewer.html", _offline_viewer_html(manifest))
            bundle.writestr("verify.py", VERIFY_SCRIPT)
        digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        report = Report(
            case_id=case_id,
            kind="portable_case_bundle",
            path=str(bundle_path),
            sha256=digest,
            manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True, default=str).encode()).hexdigest(),
            metadata_json={"contains": ["manifest.json", "evidence_index.csv", "events.csv", "viewer.html", "verify.py"]},
        )
        self.db.add(report)
        self.db.flush()
        AuditService(self.db).log(
            action="case.bundle_exported",
            case_id=case_id,
            target_type="report",
            target_id=str(report.id),
            payload={"sha256": digest, "manifest_hash": report.manifest_hash},
        )
        return report

    def _report_lines(self, case_id: int) -> list[str]:
        lines = [
            "Parakh Court-Ready Investigation Report",
            f"Case ID: {case_id}",
            "Section 63 BSA 2023 certificate: DRAFT ONLY - verify with legal counsel.",
            "",
            "Evidence Manifest",
        ]
        auth = AuthenticityService(self.db)
        for ev in self.db.scalars(select(Evidence).where(Evidence.case_id == case_id)):
            lines.append(f"Evidence {ev.id}: {ev.filename} SHA256={ev.sha256}")
            report = auth.report(ev)
            lines.append(f"  Authenticity score: {report.score}")
        lines.append("")
        lines.append("Timeline")
        for item in AnalysisService(self.db).timeline(case_id)[:25]:
            lines.append(f"{item['timestamp_utc']} {item['phase']} {item['summary']}")
        chain = AuditService(self.db).verify_chain()
        lines.append(f"Chain of custody verification: {chain}")
        return lines

    def _write_reportlab_pdf(self, path: Path, lines: list[str]) -> None:
        c = canvas.Canvas(str(path), pagesize=A4)
        width, height = A4
        y = height - 50

        def line(text: str) -> None:
            nonlocal y
            if y < 70:
                c.showPage()
                y = height - 50
            c.drawString(40, y, text[:120])
            y -= 16

        for item in lines:
            line(item)
        c.save()


def write_minimal_pdf(path: Path, lines: list[str]) -> None:
    escaped = "\\n".join(lines).replace("(", "\\(").replace(")", "\\)")[:3000]
    stream = f"BT /F1 11 Tf 40 800 Td ({escaped}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj",
    ]
    content = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(content.encode()))
        content += obj + "\n"
    xref = len(content.encode())
    content += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        content += f"{offset:010d} 00000 n \n"
    content += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    path.write_bytes(content.encode())


def _evidence_csv(evidence: list[Evidence]) -> str:
    rows: list[list[object]] = [["id", "filename", "source_type", "sha256", "md5", "size_bytes"]]
    rows.extend([[item.id, item.filename, item.source_type, item.sha256, item.md5, item.size_bytes] for item in evidence])
    return _csv_string(rows)


def _events_csv(events: list[Event]) -> str:
    rows: list[list[object]] = [
        ["id", "evidence_id", "timestamp_utc", "event_type", "source_type", "action", "content", "dedupe_hash"]
    ]
    rows.extend(
        [
            [
                event.id,
                event.evidence_id,
                event.timestamp_utc,
                event.event_type,
                event.source_type,
                event.action,
                event.content,
                event.dedupe_hash or "",
            ]
            for event in events
        ]
    )
    return _csv_string(rows)


def _csv_string(rows: list[list[object]]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return buffer.getvalue()


def _offline_viewer_html(manifest: dict) -> str:
    evidence_rows = "\n".join(
        f"<tr><td>{item['id']}</td><td>{item['filename']}</td><td><code>{item['sha256']}</code></td></tr>"
        for item in manifest["evidence"]
    )
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Parakh Offline Case Bundle</title>
<style>
body{{font-family:Inter,Arial,sans-serif;margin:32px;background:#101722;color:#edf4fb}}
table{{border-collapse:collapse;width:100%;background:#172235}}td,th{{border:1px solid #32445e;padding:8px;text-align:left}}
code{{color:#8debd1}}.notice{{color:#ffc35a}}
</style>
<h1>Parakh Portable Case Bundle</h1>
<p class="notice">{manifest["draft_notice"]}</p>
<p>Case ID: {manifest["case_id"]}</p>
<p>Audit chain valid: {manifest["audit_verification"].get("valid")}</p>
<h2>Evidence Manifest</h2>
<table><thead><tr><th>ID</th><th>Filename</th><th>SHA-256</th></tr></thead><tbody>{evidence_rows}</tbody></table>
</html>"""


VERIFY_SCRIPT = '''#!/usr/bin/env python3
"""Verify a Parakh portable bundle manifest.

This verifier checks that manifest.json exists and prints evidence hashes.
Evidence bytes are not embedded in the prototype bundle, so source-file
rehashing must be performed against the original evidence store.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


def main() -> None:
    bundle = Path(__file__).resolve().parent
    zip_files = list(bundle.glob("*.zip"))
    if not zip_files:
        print("Place verify.py beside the Parakh bundle ZIP and run it again.")
        return
    with zipfile.ZipFile(zip_files[0]) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    print("format:", manifest["format"])
    print("case_id:", manifest["case_id"])
    print("audit_valid:", manifest["audit_verification"].get("valid"))
    for item in manifest["evidence"]:
        print(item["id"], item["filename"], item["sha256"])


if __name__ == "__main__":
    main()
'''
