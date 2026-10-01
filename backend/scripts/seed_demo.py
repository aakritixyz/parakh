import sys
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.case import Case
from app.models.user import User
from app.services.evidence_service import EvidenceService

DATA = ROOT / "data" / "raw" / "demo_case"


async def seed() -> int:
    settings = get_settings()
    admin_password = settings.demo_admin_password
    if not admin_password:
        if settings.is_production:
            raise RuntimeError("DEMO_ADMIN_PASSWORD is required when ENV=production")
        admin_password = "admin123"

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == settings.demo_admin_username))
        if not user:
            user = User(
                username=settings.demo_admin_username,
                hashed_password=hash_password(admin_password),
                role="admin",
            )
            db.add(user)
        case = Case(title="Synthetic UPI Investment Scam", description="Generated demo case with fake data.")
        db.add(case)
        db.flush()
        svc = EvidenceService(db)
        for path in DATA.iterdir():
            if path.is_file():
                with path.open("rb") as fh:
                    upload = UploadFile(filename=path.name, file=fh)
                    await svc.ingest(case.id, upload, "seed", f"seed-{path.name}")
        db.commit()
        return case.id
    finally:
        db.close()


if __name__ == "__main__":
    import asyncio

    print(f"Seeded case_id={asyncio.run(seed())}")
