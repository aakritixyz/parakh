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

from app.models.audit import AuditLog
from app.models.evidence import Event, Evidence
from app.models.investigation import AuditCheckpoint
from app.models.report import Report
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.services.authenticity_service import AuthenticityService
from app.services.integrity_service import manifest_leaf, merkle_proof, merkle_root


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
        AuditService(self.db).log(
            action="report.exported",
            case_id=case_id,
            target_type="report",
            target_id=str(report.id),
            payload={"sha256": digest},
        )
        return report

    def export_case_bundle(self, case_id: int) -> Report:
        out_dir = Path("reports")
        out_dir.mkdir(exist_ok=True)
        bundle_path = out_dir / f"case-{case_id}-portable-bundle.zip"
        evidence = list(
            self.db.scalars(
                select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.id)
            )
        )
        events = list(
            self.db.scalars(
                select(Event)
                .where(Event.case_id == case_id)
                .order_by(Event.timestamp_utc, Event.id)
            )
        )
        audit = AuditService(self.db).verify_chain()
        audit_logs = list(self.db.scalars(select(AuditLog).order_by(AuditLog.id)))
        checkpoints = list(self.db.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id)))
        signatures: dict[int, list[dict]] = {}
        for checkpoint in checkpoints:
            if checkpoint.signature:
                try:
                    signatures.setdefault(checkpoint.audit_log_id, []).append(
                        json.loads(checkpoint.signature)
                    )
                except json.JSONDecodeError:
                    signatures.setdefault(checkpoint.audit_log_id, []).append({"invalid": True})
        leaves = [manifest_leaf(item) for item in evidence]
        root = merkle_root(leaves)
        evidence_rows = []
        for index, item in enumerate(evidence):
            evidence_rows.append(
                {
                    "id": item.id,
                    "filename": item.filename,
                    "sha256": item.sha256,
                    "md5": item.md5,
                    "size_bytes": item.size_bytes,
                    "source_type": item.source_type,
                    "bundle_path": f"evidence/{item.id}-{Path(item.filename).name}",
                    "merkle_leaf": leaves[index],
                    "merkle_proof": merkle_proof(leaves, index),
                }
            )
        manifest = {
            "format": "parakh-portable-case-bundle-v1",
            "case_id": case_id,
            "draft_notice": "DRAFT bundle for investigative review; verify with legal counsel before court use.",
            "integrity_version": 2,
            "integrity_notice": "A matching hash shows the file is unchanged since it was sealed. It does not prove the file was truthful.",
            "audit_verification": audit,
            "audit_entries": [
                {
                    "id": entry.id,
                    "case_id": entry.case_id,
                    "actor": entry.actor,
                    "action": entry.action,
                    "target_type": entry.target_type,
                    "target_id": entry.target_id,
                    "payload": entry.payload,
                    "previous_hash": entry.previous_hash,
                    "entry_hash": entry.entry_hash,
                    "signatures": signatures.get(entry.id, []),
                }
                for entry in audit_logs
            ],
            "merkle": {"algorithm": "SHA-256", "root": root, "leaf_count": len(leaves)},
            "evidence": evidence_rows,
        }
        with ZipFile(bundle_path, "w", ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
            bundle.writestr("evidence_index.csv", _evidence_csv(evidence))
            bundle.writestr("events.csv", _events_csv(events))
            bundle.writestr("viewer.html", _offline_viewer_html(manifest))
            bundle.writestr("verify.py", VERIFY_SCRIPT)
            for item in evidence:
                source = Path(item.storage_path)
                if source.is_file():
                    bundle.write(source, f"evidence/{item.id}-{Path(item.filename).name}")
        digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        report = Report(
            case_id=case_id,
            kind="portable_case_bundle",
            path=str(bundle_path),
            sha256=digest,
            manifest_hash=hashlib.sha256(
                json.dumps(manifest, sort_keys=True, default=str).encode()
            ).hexdigest(),
            metadata_json={
                "contains": [
                    "manifest.json",
                    "evidence_index.csv",
                    "events.csv",
                    "viewer.html",
                    "verify.py",
                    "evidence/",
                ]
            },
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
    rows.extend(
        [
            [item.id, item.filename, item.source_type, item.sha256, item.md5, item.size_bytes]
            for item in evidence
        ]
    )
    return _csv_string(rows)


def _events_csv(events: list[Event]) -> str:
    rows: list[list[object]] = [
        [
            "id",
            "evidence_id",
            "timestamp_utc",
            "event_type",
            "source_type",
            "action",
            "content",
            "dedupe_hash",
        ]
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
"""Standalone deterministic verifier for a Parakh portable bundle."""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def digest(value):
    return hashlib.sha256(value).hexdigest()


def leaf(item):
    value = {key: item[key] for key in ("id", "filename", "sha256", "size_bytes")}
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def proof_valid(value, proof, root):
    current = value
    for step in proof:
        pair = (step["hash"], current) if step["side"] == "left" else (current, step["hash"])
        current = digest(bytes.fromhex(pair[0]) + bytes.fromhex(pair[1]))
    return current == root


def canonical_entry(entry):
    keys = ("case_id", "actor", "action", "target_type", "target_id", "payload", "previous_hash")
    return json.dumps({key: entry[key] for key in keys}, sort_keys=True, separators=(",", ":"), default=str).encode()


def verify_signature(entry_hash, signed):
    if signed.get("algorithm") != "Ed25519" or signed.get("kind") != "entry_signature":
        return True
    raw = base64.b64decode(signed["public_key"])
    der = bytes.fromhex("302a300506032b6570032100") + raw
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder); key = root / "key.der"; sig = root / "sig"; data = root / "data"
        key.write_bytes(der); sig.write_bytes(base64.b64decode(signed["signature"])); data.write_bytes(entry_hash.encode())
        try:
            result = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(key), "-keyform", "DER", "-rawin", "-in", str(data), "-sigfile", str(sig)], capture_output=True)
        except FileNotFoundError:
            print("FAIL: OpenSSL is required to verify Ed25519 signatures."); return False
        return result.returncode == 0


def main() -> None:
    candidate = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if candidate is None:
        files = list(Path(__file__).resolve().parent.glob("*.zip")); candidate = files[0] if files else None
    if candidate is None:
        print("FAIL: pass the bundle ZIP path to verify.py"); raise SystemExit(2)
    failures = []
    with zipfile.ZipFile(candidate) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for item in manifest["evidence"]:
            try: actual = digest(zf.read(item["bundle_path"]))
            except KeyError: actual = None
            if actual != item["sha256"]: failures.append("evidence %s: %s" % (item["id"], item["filename"]))
            if leaf(item) != item["merkle_leaf"] or not proof_valid(item["merkle_leaf"], item["merkle_proof"], manifest["merkle"]["root"]):
                failures.append("Merkle proof for evidence %s" % item["id"])
    previous = "GENESIS"
    for entry in manifest.get("audit_entries", []):
        expected = digest(canonical_entry(entry))
        if entry["previous_hash"] != previous or entry["entry_hash"] != expected:
            failures.append("audit entry %s" % entry["id"]); break
        for signed in entry.get("signatures", []):
            if not verify_signature(entry["entry_hash"], signed): failures.append("signature at audit entry %s" % entry["id"])
        previous = entry["entry_hash"]
    if failures:
        print("FAIL at " + ", ".join(failures)); raise SystemExit(1)
    print("PASS: evidence hashes, Merkle proofs, audit chain and Ed25519 signatures verified.")
    print(manifest["integrity_notice"])


if __name__ == "__main__":
    main()
'''
