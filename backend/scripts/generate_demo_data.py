from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "demo_case"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "whatsapp_investment_scam.txt").write_text(
        "\n".join(
            [
                "12/09/2026, 09:10 - Riya: Bhai ek guaranteed return investment plan mila hai",
                "12/09/2026, 09:12 - Agent Arjun: Madam 2 din me double money, bas KYC update link open karo",
                "12/09/2026, 09:15 - Riya: ye link safe hai? https://kyc-fast.example/login",
                "12/09/2026, 09:17 - Agent Arjun: OTP share mat bolna kisi ko, yaha enter karo urgent payment unlock hoga",
                "12/09/2026, 09:25 - Riya: Maine 25000 bhej diya arjun@upi",
                "12/09/2026, 09:32 - Agent Arjun: aur 25000 karo warna account block hoga",
                "12/09/2026, 09:40 - Riya: PAN ABCDE1234F aur Aadhaar 1234 5678 9012 bhi maanga?",
            ]
        ),
        encoding="utf-8",
    )
    with (OUT / "upi_bank_statement.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["timestamp", "account", "type", "amount", "counterparty", "note"])
        writer.writeheader()
        writer.writerows(
            [
                {"timestamp": "2026-09-12 09:25 IST", "account": "victim", "type": "debit", "amount": 25000, "counterparty": "arjun@upi", "note": "investment plan"},
                {"timestamp": "2026-09-12 09:33 IST", "account": "victim", "type": "debit", "amount": 25000, "counterparty": "arjun@upi", "note": "urgent payment"},
                {"timestamp": "2026-09-12 09:45 IST", "account": "mule", "type": "credit", "amount": 50000, "counterparty": "victim@upi", "note": "rapid pass-through"},
                {"timestamp": "2026-09-12 09:47 IST", "account": "mule", "type": "debit", "amount": 49500, "counterparty": "cashout@upi", "note": "pass-through"},
            ]
        )
    with (OUT / "call_logs.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["timestamp", "phone", "direction", "duration_sec"])
        writer.writeheader()
        writer.writerow({"timestamp": "2026-09-12 09:05 IST", "phone": "+91 9876543210", "direction": "incoming", "duration_sec": 182})
    (OUT / "gps_location_takeout.json").write_text(
        json.dumps(
            {
                "locations": [
                    {"timestamp": "2026-09-12T09:00:00+05:30", "lat": 28.6139, "lon": 77.2090},
                    {"timestamp": "2026-09-12T09:30:00+05:30", "lat": 28.6200, "lon": 77.2300},
                ]
            }
        )
    )
    make_browser_db(OUT / "browser_history.sqlite")
    make_images()
    make_pdf(OUT / "suspicious_receipt.pdf")
    print(f"Demo data written to {OUT}")


def make_browser_db(path: Path) -> None:
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.execute("create table urls(url text, title text)")
        conn.execute("insert into urls values(?, ?)", ("https://kyc-fast.example/login", "KYC Fast Login"))


def make_images() -> None:
    img = Image.new("RGB", (400, 240), color=(220, 240, 255))
    img.save(OUT / "receipt_clean.jpg", "JPEG")
    stripped = Image.new("RGB", (400, 240), color=(255, 220, 220))
    stripped.save(OUT / "receipt_stripped.jpg", "JPEG")


def make_pdf(path: Path) -> None:
    write_minimal_pdf(path, ["Investment Receipt", "Amount: INR 50,000", "Beneficiary: arjun@upi"])
    with path.open("ab") as fh:
        fh.write(b"\n%%EOF\n% suspicious incremental marker\n%%EOF\n")


def write_minimal_pdf(path: Path, lines: list[str]) -> None:
    text = "\\n".join(lines).replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 740 Td ({text}) Tj ET"
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


if __name__ == "__main__":
    main()
