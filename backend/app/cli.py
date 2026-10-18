from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.migrations import migrate_database, require_current_schema
from app.core.security import Role, hash_password
from app.models.user import User
from app.services.audit_service import AuditService


def _create_user(args: argparse.Namespace, role: Role) -> None:
    settings = get_settings()
    username = args.username or input(f"{role.value.title()} username: ").strip()
    password = args.password or getpass(f"{role.value.title()} password: ")
    if not username.strip() or not 1 <= len(password.encode("utf-8")) <= 72:
        raise SystemExit("Username is required; password must contain 1 to 72 UTF-8 bytes.")
    if settings.is_production and password in {"admin", "admin123", "password", "changeme"}:
        raise SystemExit("Refusing weak/default admin password in production.")

    require_current_schema(engine)
    db = SessionLocal()
    try:
        if role == Role.admin and db.scalar(select(User).where(User.role == "admin")):
            raise SystemExit("An admin already exists; create-admin is for first-run setup only.")
        if db.scalar(select(User).where(User.username == username)):
            raise SystemExit(f"User already exists: {username}")
        db.add(
            User(username=username, hashed_password=hash_password(password), role=role.value)
        )
        AuditService(db).log(action="user.created", actor="operator-cli", target_type="user", target_id=username, payload={"role": role.value})
        db.commit()
        print(f"Created {role.value} user: {username}")
    finally:
        db.close()


def create_admin(args: argparse.Namespace) -> None:
    _create_user(args, Role.admin)


def create_user(args: argparse.Namespace) -> None:
    _create_user(args, Role(args.role))


def create_investigator(args: argparse.Namespace) -> None:
    _create_user(args, Role.investigator)


def migrate(args: argparse.Namespace) -> None:
    try:
        migrate_database(engine, adopt_existing=args.adopt_existing)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("Database migrations complete.")


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


def ml_foundation(args: argparse.Namespace) -> None:
    from app.services.ml_foundation_service import register_model, run_baseline

    require_current_schema(engine)
    output = Path(__file__).resolve().parents[1] / "data" / "ml"
    card = run_baseline(output, seed=args.seed)
    db = SessionLocal()
    try:
        register_model(db, card)
    finally:
        db.close()
    print(f"Registered {card['name']} {card['version']} ({card['evaluation_label']}).")


def not_ready(name: str):
    def _handler(_: argparse.Namespace) -> None:
        print(f"{name} command is registered but currently STUB for Phase 0.")

    return _handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Parakh operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    migrate_parser = sub.add_parser("migrate", help="Apply Alembic schema migrations")
    migrate_parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Validate and stamp an unversioned prototype schema; back up the database first",
    )
    migrate_parser.set_defaults(func=migrate)

    create_admin_parser = sub.add_parser("create-admin", help="Create the first admin user")
    create_admin_parser.add_argument("--username")
    create_admin_parser.add_argument("--password")
    create_admin_parser.set_defaults(func=create_admin)

    investigator_parser = sub.add_parser("create-investigator", help="Create an investigator account")
    investigator_parser.add_argument("--username")
    investigator_parser.add_argument("--password")
    investigator_parser.set_defaults(func=create_investigator)

    account_parser = sub.add_parser("create-user", help="Provision a non-admin team account")
    account_parser.add_argument("--username")
    account_parser.add_argument("--password")
    account_parser.add_argument("--role", choices=["investigator", "analyst", "prosecutor"], required=True)
    account_parser.set_defaults(func=create_user)

    sub.add_parser("seed-demo", help="Seed the synthetic demo case").set_defaults(func=seed_demo)
    sub.add_parser("generate-demo-data", help="Generate synthetic demo files").set_defaults(
        func=generate_demo_data
    )
    sub.add_parser("verify-audit", help="Verify the hash-chained audit log").set_defaults(
        func=verify_audit
    )
    ml_parser = sub.add_parser("ml-foundation", help="Generate, evaluate and register the synthetic baseline")
    ml_parser.add_argument("--seed", type=int, default=51026)
    ml_parser.set_defaults(func=ml_foundation)
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
