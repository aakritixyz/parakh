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

The landing page opens at `/`. **Investigator workspace** leads to `/signin.html`. Sign in with a provisioned backend account or choose **View demo without signing in**. Both routes open Active Cases in the same investigator interface. Demo mode is a clearly bannered, read-only synthetic case and needs no account.

Authenticated sessions use `/api/v2/auth`: a short-lived access token held in memory and a rotating HttpOnly refresh cookie. Reload restores a valid session; logout revokes it on the server. Passwords and tokens are never put in Vite configuration or browser storage. Photography is local; credits are in `public/images/CREDITS.md`. See [Step 1 setup and access rules](../docs/STEP1.md).

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

The checked-in `screenshots/parakh-*.jpg` captures were taken through the app browser against the production build. The browser exports JPEGs at its own image scale; filename widths refer to the verified CSS viewport. Standalone Playwright Chromium could not launch in the Codex macOS sandbox, so the browser validation was performed through the app browser. `npm run build`, `npm run typecheck`, `npm run lint`, and the current backend test suite pass; see the latest Step 1 validation output for counts.

`preview.html` is a separate legacy static demo and is not the redesigned React app. Use Vite or the production build to review this redesign.

## Evidence intake and sealing

Signed-in investigators create a case from Active Cases, then record the evidence owner, optional device and acquisition context before selecting files, folders or ZIP archives. Each file exposes its suggested source type, owner, device and note before **Start import**. Progress moves through Hashing, Stored, Parsing, Indexing and Done. Failed or cancelled background jobs can be retried. Exact duplicates reuse the existing evidence record. Safe ZIP members become individually hashed child evidence. Prosecutors and read-only memberships cannot import. Demo mode remains clearly synthetic and makes no case, owner, device or evidence changes.

## Source-linked investigator workspace

After evidence intake, the case opens at Overview with four curated, source-cited questions. The navigation is Overview, Evidence, Explore, Comms, Money, Authenticity, Graph, Map, Timeline, Findings, Reports. Counts come from the bundled 15 synthetic sources; the current source parser emits 108 records, including notices, context lines, and duplicate representations. This differs from earlier backend ingestion counts and is labelled **Parsed source records**, not unique investigative events. Rebuild the snapshot with `../backend/.venv/bin/python scripts/build-case-demo.py` from this frontend folder.

Each citation opens a source receipt with original text, line/row/page reference, raw and IST timestamp when available, and SHA-256. The demo checks all original bytes via Web Crypto. Its custody log is an explicitly simulated hash chain, never a signed acquisition record. Export a JSON review bundle and the standalone Python verifier from Reports; source-only exhibits and locally reviewed finding statuses are included. The verifier checks the original files and simulated chain, without asserting source truth or legal validity.

Replay synchronizes the source-time cursor with the latest chat, recorded bank rows and GPS plot. Translations, aliases and assistant answers are curated demo interactions. The assistant refuses unsupported questions. Findings and grouping are session-local. Persisted finding review, signed entries, ZIP exports and the Section 63 certificate workflow remain labelled planned. Per-case team access and authenticated audit-log retrieval are implemented in Step 1. Arbitrary uploaded cases receive no synthetic scenario findings; their supplied records remain inspectable in Evidence and Explore.

`npm test` checks API behavior, all 15 source hashes, source reference resolution, uncertainty statuses, and tamper rejection for the simulated chain. `npm run test:screenshots` checks all 11 views at mobile, tablet and desktop sizes, exact receipts, adjacent events, hash verification and assistant refusal. When standalone Chromium is unavailable under the desktop sandbox, those UI flows can be verified through the app browser instead.

## Landing page and home-screen installation

The landing page includes a real photo, a clearly synthetic clickable relationship map, Evidence/Timeline interface previews, and a synthetic event timeline. These public examples do not read case data.

The production build includes a web app manifest, app icons, and a service worker for supported browsers' home-screen installation. Serve `dist/` over HTTPS (localhost works for desktop review). On iPhone, use Safari → Share → Add to Home Screen; on supported Android browsers, use Install app / Add to Home screen. Browser support and install prompts vary. Installation on a physical phone still needs verification against the deployed HTTPS site.

The service worker deliberately does not cache investigation pages, evidence, authenticated API responses, or offline case data. Home-screen installation does not provide offline investigations. The preview server is local to the development computer.
