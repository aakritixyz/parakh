from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import Role, hash_password
from app.models.user import User
from app.services.audit_service import AuditService


def create_admin(args: argparse.Namespace) -> None:
    settings = get_settings()
    username = args.username or input("Admin username: ").strip()
    password = args.password or getpass("Admin password: ")
    if settings.is_production and password in {"admin", "admin123", "password", "changeme"}:
        raise SystemExit("Refusing weak/default admin password in production.")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.username == username)):
            raise SystemExit(f"User already exists: {username}")
        db.add(User(username=username, hashed_password=hash_password(password), role=Role.admin.value))
        db.commit()
        print(f"Created admin user: {username}")
    finally:
        db.close()


def seed_demo(_: argparse.Namespace) -> None:
    from scripts.seed_demo import seed

    case_id = asyncio.run(seed())
    print(f"Seeded demo case_id={case_id}")


def generate_demo_data(_: argparse.Namespace) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_demo_data.py"
    subprocess.run([sys.executable, str(script)], check=True)


def verify_audit(_: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        result = AuditService(db).verify_chain()
        print(result)
        if not result.get("valid"):
            raise SystemExit(1)
    finally:
        db.close()


def not_ready(name: str):
    def _handler(_: argparse.Namespace) -> None:
        print(f"{name} command is registered but currently STUB for Phase 0.")

    return _handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Parakh operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = sub.add_parser("create-admin", help="Create the first admin user")
    create_admin_parser.add_argument("--username")
    create_admin_parser.add_argument("--password")
    create_admin_parser.set_defaults(func=create_admin)

    sub.add_parser("seed-demo", help="Seed the synthetic demo case").set_defaults(func=seed_demo)
    sub.add_parser("generate-demo-data", help="Generate synthetic demo files").set_defaults(
        func=generate_demo_data
    )
    sub.add_parser("verify-audit", help="Verify the hash-chained audit log").set_defaults(
        func=verify_audit
    )
    sub.add_parser("reindex", help="Rebuild search indexes").set_defaults(func=not_ready("reindex"))
    sub.add_parser("export-case", help="Export a portable case bundle").set_defaults(
        func=not_ready("export-case")
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
