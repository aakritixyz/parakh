# Decisions

## Phase 0

- Kept SQLite as the default local database so the hackathon demo remains easy to run.
- Added production guardrails without removing dev convenience: demo seed can still use `admin/admin123` in `ENV=dev`, but production requires `DEMO_ADMIN_PASSWORD`.
- Used a dependency-free `argparse` CLI instead of adding a new Typer dependency immediately. The command surface matches the requested operator workflow and can be migrated to Typer later.
- Kept all advanced, not-yet-real operations explicitly labelled as STUB instead of showing fake results.

## 2026-10-15 · Phase 0 bootstrap completion

- Supersedes the earlier implicit dev password: demo seeding now requires an explicit configured password in every environment, and the frontend uses runtime sign-in.
- Retained the existing migration revision ID while replacing live-model DDL with a frozen baseline. Schema changes now belong to Alembic rather than API startup.
- Existing unversioned schemas require explicit, validated adoption; mismatches are refused without rewriting forensic data.
- Replaced the incompatible Passlib adapter with direct bcrypt usage while preserving standard bcrypt hash verification.
- Parser versions and documented source-time assumptions change future imports and explicit reparse only.
- Included narrow unreadable-PDF handling because the planted demo receipt prevented clean seeding; originals and warnings are retained.

See PHASE0.md for setup and validation.
