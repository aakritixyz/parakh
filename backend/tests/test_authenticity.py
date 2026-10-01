from pathlib import Path

from PIL import Image

from app.models.evidence import Evidence
from app.services.authenticity_service import AuthenticityService


def test_image_missing_exif_finding(db, tmp_path: Path):
    path = tmp_path / "x.jpg"
    Image.new("RGB", (20, 20)).save(path)
    evidence = Evidence(case_id=1, filename="x.jpg", source_type="image", content_type="image/jpeg", sha256="", md5="", size_bytes=1, storage_path=str(path), metadata_json={})
    db.add(evidence)
    db.commit()
    report = AuthenticityService(db).report(evidence)
    assert any(f.signal == "sha256_mismatch" for f in report.findings)
    assert any(f.signal == "missing_exif" for f in report.findings)
