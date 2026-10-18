# Phase 0: reproducible bootstrap

This phase makes the existing prototype installable and testable. It does not implement the later blueprint's signed audit chain, solver-based analysis, live facets, or Incident Replay.

## Start from a clean checkout

```bash
cp .env.example .env
# Edit the private .env: set DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD and SECRET_KEY.
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.cli migrate
alembic check
python -m app.cli generate-demo-data
python -m app.cli seed-demo
uvicorn app.main:app --reload
```

In another terminal, run `npm ci` and `npm run dev` from `frontend/`. The UI opens with labelled synthetic offline data and makes no automatic login request. Choose **Connect backend**, then enter the configured server account. Credentials are supplied at runtime, not Vite build variables; the UI does not persist the password or bearer token. Reloading returns to the offline demo. The frontend's existing case-1 default is unchanged.

Backend settings load repository-root `.env`, then `backend/.env` if present; process environment variables take precedence over both. `DEMO_ADMIN_PASSWORD` has no implicit fallback in any environment. Production seeding rejects known default passwords. Re-seeding never resets an existing account's password or promotes an existing non-admin account.

## Migration ownership

The baseline keeps revision `20261001_0001` but now contains fixed table/index/constraint definitions for all 32 application tables. It does not import application models or call `metadata.create_all`. Future schema changes require a new Alembic revision; the standard revision template is included. API imports do not create database files or tables. API startup, seeding, and admin creation require the current migration revision. Readiness returns HTTP 503 when the database or revision is unavailable.

For a new database use `python -m app.cli migrate` (or `alembic upgrade head`). Repeating the upgrade preserves rows. Offline SQL is available through `alembic upgrade head --sql`.

For an existing unversioned prototype, stop writes and back up the database and vault first. Then use:

```bash
python -m app.cli migrate --adopt-existing
```

Adoption compares tables, columns, indexes, constraints and server defaults before stamping the baseline. It accepts a matching current prototype schema and preserves its rows. It refuses incompatible older schemas without stamping or rewriting them; those require a reviewed migration or a separate fresh database. It also refuses adoption after future revisions are introduced until that path is reviewed. Existing databases already stamped with the retained baseline revision are not re-created. This implementation and validation do not modify the user's existing local database.

Docker applies migrations before starting Uvicorn and reads the private root `.env`. The build context excludes local credentials, databases, virtual environments, evidence storage, and caches.

## Parser corrections

- WhatsApp v2 recognizes bracketed iOS and Android exports, seconds, 12/24-hour clocks, slash/dot/hyphen dates, Unicode direction markers and narrow spaces, multiline bodies, system messages and omitted media. Detection also recognizes valid exports such as `_chat.txt` without relying on a WhatsApp filename.
- Offset-less WhatsApp times use `WHATSAPP_TIMEZONE` (default `Asia/Kolkata`); ambiguous date order uses `WHATSAPP_DAY_FIRST` (default `true`). These are source-device assumptions, not inferred clock corrections. Original timestamps and raw line references are retained. Set the options to match the source export before importing.
- Year-first ISO dates are not reinterpreted as day-first; explicit IST timestamps are converted correctly. Other offset-less generic parser inputs retain their existing UTC default. SQLite event values are restored as aware UTC values on read, so API timestamps carry an offset and display correctly in the browser.
- CSV v2 uses multiple compatible header markers rather than values or one generic `account`/`amount` column. Headers tolerate case, spaces, underscores and UTF-8 BOMs. Telecom schemas take precedence over incidental charge columns. Duplicate headers and extra row fields produce explicit errors.
- The planted demo receipt has an unreadable PDF trailer. It remains sealed with its original hash; extraction is marked `needs_review`, warnings are recorded, and no extracted text is invented. Authenticity reports expose an unreadable-structure signal without treating it alone as proof of manipulation. Reparse preserves that review status.

Original evidence files are never rewritten. Existing event rows are not re-extracted or rewritten. Display now respects their declared UTC meaning. Events imported under the older WhatsApp parser's UTC assumption need an explicit, audited reparse with the intended source timezone to correct those stored times.

## Credentials and repository hygiene

The Passlib adapter was incompatible with the installed bcrypt release and prevented a fresh seed from hashing any password. Password hashing now uses the declared bcrypt dependency directly, while accepting existing standard bcrypt hashes. Empty passwords and values over bcrypt's 72-byte UTF-8 limit are rejected rather than truncated. The old deterministic development hash fallback is no longer used for new passwords.

No `.env`, live database, `node_modules`, or Python cache files were tracked at the start of this work. Ignore rules now also cover environment variants, SQLite journal/WAL files, and Playwright runtime output. Synthetic raw evidence fixtures remain intentionally tracked. Local ignored files were not deleted.

## Validation

```bash
cd backend
ruff check .
mypy app
pytest -q

cd ../frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Backend tests cover fresh/duplicate upgrades, offline SQL, independence from future runtime metadata, matching legacy adoption with row preservation, incompatible-schema refusal, migration-first API lifecycle, configured seed/login, parser formats, and unreadable-PDF handling. Frontend tests cover offline behavior, runtime credentials, failed sign-in, invalid tokens, and compatibility with older API endpoints. CI performs a fresh migration and `alembic check` before the backend checks, and runs the frontend tests, lint, typecheck, and build.

### Completion results (15 October 2026)

- Backend: 60 tests passed; Ruff and mypy passed.
- Frontend: six API tests passed; lint, typecheck, and production build passed.
- A source-only copy with no private `.env`, local database, Python environment, or frontend `node_modules` successfully migrated a new temporary SQLite database, passed `alembic check`, regenerated/sealed the bundled demo, and passed all 60 tests. It used the existing backend dependency environment; frontend dependencies were installed afresh with `npm ci`.
- Isolated browser/API test: incorrect credentials showed a visible error; the configured synthetic account connected to eight evidence items and 15 parsed events. An original 09:10 IST WhatsApp message round-tripped through SQLite and displayed as 09:10 IST.
- Sign-in dialog bounds, header spacing, initial focus, Escape, and focus restoration passed at 1280, 1440, 1600 and 1920 CSS pixels through the app browser.
- Screenshots: `frontend/screenshots/phase0-sign-in-1280.jpg`, `phase0-sign-in-1920.jpg`, and `phase0-connected-events.jpg`.
- Docker configuration was updated but not run; validation used the local API and production frontend. Standalone Playwright was not rerun because its Chromium launch is blocked in this sandbox; the scripted screenshot workflow was updated for explicit sign-in.
- Existing local database and evidence vault were not migrated, seeded, reset, or deleted.
