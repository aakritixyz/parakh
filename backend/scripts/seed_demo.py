import sys
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.migrations import require_current_schema
from app.core.security import hash_password, verify_password
from app.models.case import Case
from app.models.user import User
from app.services.evidence_service import EvidenceService

DATA = ROOT / "data" / "raw" / "demo_case"


async def seed() -> int:
    settings = get_settings()
    admin_password = settings.demo_admin_password
    if not admin_password:
        raise RuntimeError("Set DEMO_ADMIN_PASSWORD before seeding the synthetic demo.")
    if settings.is_production and admin_password in {"admin", "admin123", "password", "changeme"}:
        raise RuntimeError("Refusing weak/default demo admin password in production.")
    require_current_schema(engine)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == settings.demo_admin_username))
        if user and user.role != "admin":
            raise RuntimeError("Configured demo username belongs to a non-admin account.")
        if user and not verify_password(admin_password, user.hashed_password):
            raise RuntimeError(
                "Configured demo password does not match the existing account; seeding never resets passwords."
            )
        if not user:
            user = User(
                username=settings.demo_admin_username,
                hashed_password=hash_password(admin_password),
                role="admin",
            )
            db.add(user)
        case = Case(
            title="Synthetic UPI Investment Scam", description="Generated demo case with fake data."
        )
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
