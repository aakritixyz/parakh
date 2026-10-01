# Parakh Delivery Plan

This checklist tracks the pasted build spec. Completed items are checked only when implemented and verified.

## Phase 0: Repo Foundation

- [x] Audit existing repo and document gaps in `docs/AUDIT.md`.
- [x] Add `.gitignore` for env files, local DBs, caches, evidence storage, build output, and OS noise.
- [x] Make demo credentials configurable through environment settings.
- [x] Add `python -m app.cli` commands: `create-admin`, `seed-demo`, `generate-demo-data`, `verify-audit`.
- [x] Label not-yet-real CLI operations as STUB: `reindex`, `export-case`.
- [x] Add CORS settings and request ID middleware.
- [x] Expand `.env.example`.
- [x] Add CI workflow for backend and frontend checks.
- [ ] Replace `create_all` startup schema creation with migrations.
- [ ] Split `intelligence_service.py` into focused modules.
- [ ] Add structured logging with richer request metadata and PII-safe redaction.

## Phase 1: Data Model And Migrations

- [x] Add case membership grants and database role table foundation.
- [x] Add Device, Extraction/DataSource, Owner, Party, Identifier, alias/merge foundation models.
- [x] Expand Event schema with source app/type, extraction, owner, thread, parties, geo, deletion recovery, parser version, dedupe hash.
- [x] Add Artifact/MediaItem, Thread, Tag, Bookmark, WatchList, SavedSearch, Task, Job, richer Report, AuthenticityReport/Finding, and AuditCheckpoint models.
- [x] Add Alembic Phase 1 migration file that creates missing tables and patches legacy prototype columns.
- [x] Link new evidence uploads to Extraction records and extraction-linked parsed events.
- [ ] Add full reversible merge/unmerge operations for party/identifier resolution.
- [ ] Add production-grade Postgres indexes, FTS/trigram/vector indexes, and EXPLAIN docs.
- [ ] Fully remove startup `create_all` after migrations are the only supported schema path.

## Phase 2: Ingestion Pipeline

- [x] Upload -> hash -> immutable store -> extraction -> synchronous parse job record.
- [x] India normalization package for phones, UPI, IFSC, PAN, masked Aadhaar, email, URL, IP.
- [x] Parser capability metadata: name, version, formats, status.
- [x] Persist basic ingestion job status rows and expose `/jobs` plus `/jobs/{id}`.
- [x] Generate deterministic event `dedupe_hash` values.
- [x] Add synchronous reparse endpoint that replaces prior extraction events instead of duplicating them.
- [x] Replace fragile CSV "contains UPI anywhere" classification with schema-marker detection.
- [ ] Full upload -> queued ParseJob -> normalize -> resolve -> dedupe -> index pipeline.
- [ ] Streaming parser interface with batched inserts.
- [x] Idempotent synchronous re-parsing without duplicate events for current parser pipeline.
- [ ] Timezone helper with UTC/original/offset enforcement across all parsers.
- [ ] RQ/Celery worker with progress/cancel/retry/logs.

## Phase 3: Parsers And Scale

- [x] Upgrade WhatsApp parser for bracket/dash export styles, 12h/24h timestamps, multiline messages, system messages, and media-omitted markers.
- [ ] Add WhatsApp date ambiguity reporting and user-confirmable DD/MM vs MM/DD override.
- [ ] Add app DB, Telegram, Signal, SMS, calls, contacts, browser, email, financial PDF/CSV, CDR/IPDR, location, logs, media/document parsers.
- [ ] Add archive/folder ingestion with zip-slip and zip-bomb protection.
- [ ] Optional LEAPP-style adapter documented in `docs/THIRD_PARTY.md`.
- [ ] Deleted SQLite record recovery marked with lower confidence.
- [ ] 1M-event synthetic benchmark and documented numbers.

## Phase 4: Search, Graph, Geo, Fraud

- [ ] Full faceted search with boolean filters, safe regex, cursor pagination, facet counts, histograms.
- [ ] Thread/communications APIs.
- [ ] Case and cross-case identifier search with permissions.
- [ ] Semantic/hybrid search with local embeddings.
- [ ] Saved searches, tags, bookmarks, watch lists.
- [ ] Geo clustering/trails/dwell/co-location.
- [ ] NetworkX graph metrics, shortest path, exports.
- [ ] Transaction/mule and CDR analytics with row-level citations.

## Phase 5: Authenticity And AI

- [ ] Real image/document/audio/video/OCR authenticity pipelines where feasible offline.
- [ ] Explainable authenticity score with versioned signal weights.
- [ ] LLM provider interface with Ollama/default offline extractive fallback.
- [x] Citation-gated offline assistant response with validation.
- [x] Prompt-injection tests using adversarial evidence text.
- [ ] Full JSON RAG contract with provider repair attempt and retrieved-set citation validation.

## Phase 6: Investigator Frontend

- [x] Original Parakh investigator-style workspace shell.
- [ ] Generated typed API client from OpenAPI.
- [ ] TanStack Query/Table/Virtual, Zustand, Cytoscape, MapLibre, charting, command palette.
- [ ] Evidence intake wizard.
- [ ] Explore, Timeline, Graph, Map, Media, Comms, Financial, Telecom, Leads, Assistant, Identifier Search, Reports, Jobs, Audit, Admin wired to real APIs.
- [ ] URL-shareable filter state, i18n scaffolding, Playwright smoke tests.

## Phase 7: Reporting, Security, Packaging

- [x] Per-case RBAC foundation with automatic creator membership, case-list filtering, and case/evidence/job middleware checks.
- [ ] Full prosecutor exhibit-only mode and endpoint-by-endpoint role matrix enforcement.
- [ ] Court-ready report generation with report hash in audit log.
- [x] Portable case export bundle with offline viewer and `verify.py`.
- [x] Bundle SHA-256 and manifest hash recorded in report/audit metadata.
- [ ] Ed25519 audit signatures and checkpointing.
- [ ] Backup/restore commands and disaster recovery docs.
- [ ] Upload hardening, rate limits, security headers, dependency audit, secrets scanning.
- [x] `/healthz` and `/readyz` system endpoints.
- [ ] Docker Compose one-command demo stack.
- [ ] Final coverage report in `docs/FINAL_REPORT.md`.
