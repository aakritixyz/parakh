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

The landing page opens at `/`. **Investigator workspace** leads to `/signin.html`, where an investigator can enter an existing backend account or choose **View demo without signing in**. Demo mode opens the labelled synthetic offline workspace without API requests. Sign-in uses the backend token endpoint and server account configured with `DEMO_ADMIN_USERNAME` and `DEMO_ADMIN_PASSWORD`. Credentials are runtime inputs, never Vite build variables or browser storage. The authenticated view lasts for the current page session; reloading requires sign-in again. Optional public configuration is documented in `.env.example`. Photography is served locally, with sources and licenses in `public/images/CREDITS.md`.

## No-Install Preview

If npm install is unavailable, open this file directly in a browser:

```text
~/Desktop/parakh/frontend/preview.html
```

## UI system and validation

The React app uses a navy shell, white content panels, 13px body text, and centralized design tokens in `src/styles/tokens.css`. Layout components live in `src/components/layout/`; reusable controls and variable-height event virtualization live in `src/components/ui/`. Filters collapse to a narrow rail, and details use a grid column at 1440px and above, with a modal overlay below that breakpoint.

```bash
npm test
npm run build
npm run typecheck
npm run lint
npx playwright install chromium
# Run the app in another terminal, then:
npm run test:screenshots
# For a server on another port:
PARAKH_URL=http://127.0.0.1:5183 npm run test:screenshots
```

The screenshot script checks landing, sign-in errors, and demo entry at 375, 768, 1280, and 1920 pixels, then all 21 workspace destinations at 1280, 1440, 1600, and 1920 CSS pixels, validates drawer behavior, exercises 1,000-event virtualization, and writes Dashboard, Timeline, Graph, Communications, and Details captures at 1280 and 1920 to `screenshots/`. It uses synthetic fixtures without modifying backend data.

The checked-in `screenshots/parakh-*.jpg` captures were taken through the app browser against the production build. The browser exports JPEGs at its own image scale; filename widths refer to the verified CSS viewport. Standalone Playwright Chromium could not launch in the Codex macOS sandbox, so the browser validation was performed through the app browser. `npm run build`, `npm run typecheck`, `npm run lint`, and the existing 19 backend tests passed.

`preview.html` is a separate legacy static demo and is not the redesigned React app. Use Vite or the production build to review this redesign.

## Evidence intake

Both sign-in and demo entry open **Upload evidence** first. The investigator names a case, selects files or a folder, checks the evidence list, uploads, then opens case analysis. Signed-in uploads create a new backend case and use authenticated multipart requests with per-file status and retry keys. Failed files block analysis until retried or removed. Tokens are held only in memory; a refresh requires another sign-in. Demo mode stages file names locally and explicitly uses preloaded fictional analysis; it does not process selected files. All 15 synthetic source files are in `../evidence/`. Demo users can choose that folder or use the bundled inventory.

## Source-linked investigator workspace

After evidence intake, the case opens at Overview with four curated, source-cited questions. The navigation is Overview, Evidence, Explore, Comms, Money, Authenticity, Graph, Map, Timeline, Findings, Reports. Counts come from the bundled 15 synthetic sources; the current source parser emits 108 records, including notices, context lines, and duplicate representations. This differs from earlier backend ingestion counts and is labelled **Parsed source records**, not unique investigative events. Rebuild the snapshot with `../backend/.venv/bin/python scripts/build-case-demo.py` from this frontend folder.

Each citation opens a source receipt with original text, line/row/page reference, raw and IST timestamp when available, and SHA-256. The demo checks all original bytes via Web Crypto. Its custody log is an explicitly simulated hash chain, never a signed acquisition record. Export a JSON review bundle and the standalone Python verifier from Reports; source-only exhibits and locally reviewed finding statuses are included. The verifier checks the original files and simulated chain, without asserting source truth or legal validity.

Replay synchronizes the source-time cursor with the latest chat, recorded bank rows and GPS plot. Translations, aliases and assistant answers are curated demo interactions. The assistant refuses unsupported questions. Findings and grouping are session-local. Persisted review, team collaboration, full authenticated custody-log retrieval, signed entries, ZIP exports and the Section 63 certificate workflow remain labelled planned. Arbitrary uploaded cases receive no synthetic scenario findings; their supplied records remain inspectable in Evidence and Explore.

`npm test` checks API behavior, all 15 source hashes, source reference resolution, uncertainty statuses, and tamper rejection for the simulated chain. `npm run test:screenshots` checks all 11 views at mobile, tablet and desktop sizes, exact receipts, adjacent events, hash verification and assistant refusal. When standalone Chromium is unavailable under the desktop sandbox, those UI flows can be verified through the app browser instead.
