# Parakh

Project layout:

- `backend/` - FastAPI forensic investigation API
- `frontend/` - Investigator dashboard UI

## First setup

Copy `.env.example` to a private `.env` and set `DEMO_ADMIN_USERNAME`, `DEMO_ADMIN_PASSWORD`, and `SECRET_KEY`. There is no default demo password. From an activated backend environment, run `make backend-migrate` before starting or seeding the API. Full clean-checkout and existing-database instructions are in [Phase 0](docs/PHASE0.md).

## Run Backend

From the project root:

```bash
cd ~/Desktop/parakh
make backend
```

Or directly:

```bash
cd ~/Desktop/parakh/backend
uvicorn app.main:app --reload
```

The command must run from `backend/`, because the Python package is `backend/app`.

Open:

```text
http://127.0.0.1:8000/api/docs
```

## Run Frontend

```bash
cd ~/Desktop/parakh/frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The root URL opens the Parakh landing page. Choose a capability card to open
the matching investigator view, or use **Open investigator workspace** to open
the dashboard. In the investigator console, select the Parakh brand to return
to the landing page.

Landing-page destinations:

- Evidence collection → Gallery
- Pattern and anomaly analysis → AI Leads
- Integrity and origin → Authenticity
- Fraud and manipulation detection → Fraud
- Cross-source correlation → Graph
- Incident reconstruction → Reconstruction

No-install preview:

```text
~/Desktop/parakh/frontend/preview.html
```

## Demo Data

```bash
cd ~/Desktop/parakh
make backend-demo
make backend-seed
```

Demo login comes from the private `.env`. Choose **Connect backend** in the frontend and enter these values:

- username: `DEMO_ADMIN_USERNAME` (default `admin`)
- password: `DEMO_ADMIN_PASSWORD` (required explicitly in every environment)

Create a real admin manually:

```bash
cd ~/Desktop/parakh
make create-admin
```
