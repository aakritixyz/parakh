.PHONY: backend backend-install backend-migrate backend-test backend-lint backend-demo backend-seed create-admin frontend frontend-install lint test

backend:
	cd backend && uvicorn app.main:app --reload

backend-install:
	cd backend && pip install -r requirements.txt

backend-migrate:
	cd backend && python -m app.cli migrate

backend-test:
	cd backend && pytest

backend-lint:
	cd backend && ruff check . && mypy app

backend-demo:
	cd backend && python -m app.cli generate-demo-data

backend-seed:
	cd backend && python -m app.cli seed-demo

create-admin:
	cd backend && python -m app.cli create-admin

lint:
	cd backend && ruff check . && mypy app
	cd frontend && npm run lint && npm run typecheck && npm run build

test:
	cd backend && pytest -q
	cd frontend && npm test && npm run typecheck && npm run build

frontend:
	cd frontend && npm run dev

frontend-install:
	cd frontend && npm install

smoke:
	cd frontend && node scripts/smoke.mjs

benchmark:
	cd backend && python -m scripts.benchmark_search

dependency-audit:
	cd frontend && npm audit
	cd backend && python -m pip_audit -r requirements.txt
