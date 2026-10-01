# Parakh Phase 0 Audit

Date: 2026-10-01

## Current Architecture

Parakh is a backend-first prototype with:

- `backend/`: FastAPI API, SQLAlchemy models, SQLite dev database, content-addressed local storage, parser registry, analysis/authenticity/audit/report services, and pytest coverage for parsers, audit chain, authenticity, fraud/entity extraction, and citation enforcement.
- `frontend/`: Vite + React + TypeScript investigator workspace with case-style navigation, faceted panels, graph/timeline/map/gallery/communications/reporting views, and demo fallback data.
- `backend/data/raw/demo_case/`: synthetic UPI-scam demo evidence.
- `work/`: scratch area for generated presentation artifacts.

## What Works Today

- Versioned `/api/v1` REST API with OpenAPI docs.
- JWT-style login and RBAC role field.
- Evidence upload with SHA-256/MD5 recording and content-addressed storage.
- Parser registry with working prototype parsers for common demo formats.
- Unified event output for parsed artifacts.
- Hash-chained audit log and verification endpoint.
- Rule/heuristic authenticity, anomaly, fraud, graph, timeline, reconstruction, and cited-assistant endpoints.
- Demo frontend with original Parakh branding and dense investigator-style views.
- Generated presentation document for explaining the project.

## Major Gaps

- Schema is still prototype-scale. It lacks the full Device, Extraction, Owner, Party, Identifier, Thread, Artifact, WatchList, Job, and richer Report model hierarchy requested in the full spec.
- Alembic has `env.py` but no real migration versions; startup still uses `Base.metadata.create_all`.
- Background jobs are not implemented yet; heavy analysis currently runs synchronously.
- `intelligence_service.py` is a large facade and should be split into focused services in a later phase.
- Search is not yet production-grade: no cursor pagination, no Postgres FTS/trigram, no vector store, and no 1M-event benchmark.
- Advanced media/document/audio/video detectors are labelled prototype heuristics or stubs, not court-grade ML.
- Frontend does not yet use TanStack Query/Table, Cytoscape, MapLibre, command palette, or generated OpenAPI client.
- Per-case membership RBAC is not fully enforced because the richer membership schema is not implemented.
- No Docker Compose stack with worker/db/redis/minio/web has been fully wired for one-command production-like demo.

## Immediate Tech Debt

- Replace `create_all` with Alembic migrations.
- Replace hardcoded demo credentials in docs/scripts with env-driven bootstrap.
- Remove local generated artifacts from version control and keep them ignored.
- Split service modules and add pagination-ready APIs before scaling data.
- Move demo seeding to `python -m app.cli seed-demo`.
- Add CI for backend/frontend checks.

## Safety Notes

- Ingestion must remain limited to exported/logical files only.
- No device exploitation, lock bypass, spyware, or invasive acquisition features are present or planned.
- AI outputs must remain citation-gated.
- Section 63 BSA output must remain marked as draft for legal review.
