# Parakh Frontend

Investigator-facing dashboard for the Parakh digital forensics backend.

The UI is inspired by modern investigation suites: dark command center, evidence cards, graph analytics, AI leads, authenticity scoring, and incident timeline. It does not copy Cellebrite branding or protected UI assets.

## Run

```bash
cd ~/Desktop/parakh/frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Backend default:

```text
http://127.0.0.1:8000/api/v1
```

If the backend is not running, the frontend falls back to built-in synthetic demo data so the screen still works for presentation.

## No-Install Preview

If npm install is unavailable, open this file directly in a browser:

```text
~/Desktop/parakh/frontend/preview.html
```
