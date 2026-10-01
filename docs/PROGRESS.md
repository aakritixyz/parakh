# Parakh Progress Log

## 2026-10-01 · Phase 0 Start

Done:

- Audited the current prototype and recorded gaps in `docs/AUDIT.md`.
- Added repo-level `.gitignore` covering local databases, `.env`, evidence storage, build output, node modules, caches, and OS files while keeping synthetic raw demo files allowed.
- Added env-driven demo admin settings and production guardrails for seed credentials.
- Added `python -m app.cli` with `create-admin`, `seed-demo`, `generate-demo-data`, `verify-audit`, plus labelled STUB commands for `reindex` and `export-case`.
- Added configurable CORS origins and request ID response headers.
- Expanded `.env.example`.
- Added CI workflow for backend tests/lint/type checks and frontend build.

Still stubbed or future work:

- `reindex` and `export-case` CLI commands are registered but labelled STUB.
- Background job queue, full schema migrations, scale search, advanced detectors, and generated frontend API client are not yet implemented.

Demo:

- Backend: `cd backend && python -m app.cli seed-demo && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm run dev`

## 2026-10-01 · Phase 1 Schema Slice

Done:

- Expanded `Case`, `CaseMembership`, `Evidence`, `Event`, `Lead`, and `Report` with Phase 1 fields.
- Added new investigation schema models: role records, devices, owners, extractions, parties, identifiers, aliases, party identifiers, threads, event recipients, artifacts/media, tags, event tags, bookmarks, watch lists, saved searches, tasks, jobs, and audit checkpoints.
- Added stored authenticity report/finding models.
- Added Alembic migration `20261001_0001_phase1_investigation_schema.py`.
- Updated ingestion so every uploaded evidence item creates an `Extraction` and parsed events point back to that extraction.
- Added tests proving Phase 1 tables are registered and ingestion creates extraction-linked events.

Still stubbed or future work:

- Alembic is listed as a dependency, but the active shell environment used for this run did not have the Alembic command installed; schema creation was verified through SQLAlchemy metadata, and the migration file is present for an environment with requirements installed.
- Startup still uses `Base.metadata.create_all`; removing that requires a careful migration-first boot flow.
- Identifier merge/unmerge operations and full per-case RBAC enforcement are still future work.

Verification:

- Backend: `8 passed`, `ruff check .` clean, `mypy app` clean.
- Frontend: `npm run build` passed.

## 2026-10-01 · Phase 2 Pipeline Slice

Done:

- Added `app.normalize` with India-specific normalization for +91 phones, UPI IDs, IFSC, PAN, masked Aadhaar, email, URL/domain, and IP values.
- Updated entity extraction to use the normalization package and detect common Indian phone variants such as `0`-prefixed and `91-` hyphenated numbers.
- Added parser capability declarations (`name`, `version`, `supported_types`, `status`) and made `/parsers/capabilities` report stable/beta/stub status honestly.
- Added persisted ingestion `Job` rows during evidence upload and exposed `/jobs/{id}`.
- Added tests for normalization, parser capabilities, and ingestion job status.

Still stubbed or future work:

- Parsing is still synchronous; RQ/Celery workers, cancel/retry, SSE/WebSocket progress, and batch inserts remain future phases.
- Deduplication/indexing/search backfills are not yet implemented.

Verification:

- Backend: `11 passed`, `ruff check .` clean, `mypy app` clean.
- Frontend: `npm run build` passed.

## 2026-10-01 · Phase 2 Continuation

Done:

- Added deterministic event `dedupe_hash` generation during ingestion.
- Added `POST /api/v1/evidence/{evidence_id}/reparse`, which deletes prior events for the extraction and inserts a fresh parse result instead of duplicating events.
- Improved CSV source classification using schema markers for financial and CDR/IPDR files instead of checking whether any value contains `upi`.
- Added tests for dedupe hash stability, reparse replacement behavior, and CSV financial schema detection.

Still stubbed or future work:

- Reparse is synchronous and should move into the background job runner later.
- The dedupe hash is stored, but cross-evidence duplicate grouping and UI controls are still future work.

Verification:

- Backend: `13 passed`, `ruff check .` clean, `mypy app` clean.
- Frontend: `npm run build` passed.

## 2026-10-01 · Phase 3 Parser Slice

Done:

- Upgraded WhatsApp text export parsing from a single-line parser to a small state machine.
- Added support for bracketed and dash-separated exports, 12h/24h timestamps, seconds in timestamps, multiline messages, system messages, Hindi/Hinglish content, and media-omitted markers.
- Added parser tests for bracketed iOS-style exports, multiline messages, system notices, and omitted media.

Still stubbed or future work:

- Ambiguous date format handling (`DD/MM` vs `MM/DD`) still needs a parser warning and investigator override.
- WhatsApp app database parsing is not implemented yet.

Verification:

- Backend: `14 passed`, `ruff check .` clean, `mypy app` clean.
- Frontend: `npm run build` passed.

## 2026-10-01 · Phase 5/7 Vertical Slice

Done:

- Added `POST /api/v1/cases/{case_id}/export-bundle`.
- Implemented portable ZIP case bundle export containing `manifest.json`, `evidence_index.csv`, `events.csv`, `viewer.html`, and `verify.py`.
- Stored bundle SHA-256 and manifest hash in the `Report` row and audit log payload.
- Tightened Section 63 BSA draft label to `DRAFT — verify with legal counsel`.
- Added an adversarial prompt-injection regression test for the cited assistant.
- Added tests for portable bundle contents and manifest generation.

Still stubbed or future work:

- Prototype bundle does not embed original evidence bytes; it exports hashes/indexes/events and notes that rehashing must be done against the original evidence store.
- Ed25519 signatures, timestamping, and full backup/restore are not implemented yet.
- The assistant is still deterministic/offline and not a full Ollama-backed JSON RAG provider.

Verification:

- Backend: `16 passed`, `ruff check .` clean, `mypy app` clean.
- Frontend: `npm run build` passed.

## 2026-10-01 · Phase 7/8 RBAC And Readiness Slice

Done:

- Added case RBAC helper functions.
- Case creators now receive a `CaseMembership` automatically.
- Non-admin `/cases` listing is filtered to only cases where the user is a member.
- Added case/evidence/job access middleware for case-scoped API paths.
- Prosecutor membership is treated as read-only for write checks.
- Added `/healthz` and `/readyz` endpoints.
- Added RBAC tests for creator membership, read-only prosecutor behavior, and membership denial.

Still stubbed or future work:

- Prosecutor exhibit-only access is not implemented yet.
- Middleware handles current route shapes; a future route registry/dependency pattern should replace it for finer endpoint-by-endpoint permissions.
- Rate limiting and CSRF-safe cookie mode remain future hardening work.

Verification:

- Backend: `19 passed`, `ruff check .` clean, `mypy app` clean.
- Frontend: `npm run build` passed.
