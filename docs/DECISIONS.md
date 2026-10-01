# Decisions

## Phase 0

- Kept SQLite as the default local database so the hackathon demo remains easy to run.
- Added production guardrails without removing dev convenience: demo seed can still use `admin/admin123` in `ENV=dev`, but production requires `DEMO_ADMIN_PASSWORD`.
- Used a dependency-free `argparse` CLI instead of adding a new Typer dependency immediately. The command surface matches the requested operator workflow and can be migrated to Typer later.
- Kept all advanced, not-yet-real operations explicitly labelled as STUB instead of showing fake results.
