# Parakh

Project layout:

- `backend/` - FastAPI forensic investigation API
- `frontend/` - Investigator dashboard UI

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

Dev demo login comes from `.env`:

- username: `DEMO_ADMIN_USERNAME` (default `admin`)
- password: `DEMO_ADMIN_PASSWORD` (dev fallback `admin123`; production requires an explicit value)

Create a real admin manually:

```bash
cd ~/Desktop/parakh
make create-admin
```
