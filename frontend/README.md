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

## UI system and validation

The React app uses a navy shell, white content panels, 13px body text, and centralized design tokens in `src/styles/tokens.css`. Layout components live in `src/components/layout/`; reusable controls and variable-height event virtualization live in `src/components/ui/`. Filters collapse to a narrow rail, and details use a grid column at 1440px and above, with a modal overlay below that breakpoint.

```bash
npm run build
npm run typecheck
npm run lint
npx playwright install chromium
# Run the app in another terminal, then:
npm run test:screenshots
# For a server on another port:
PARAKH_URL=http://127.0.0.1:5183 npm run test:screenshots
```

The screenshot script checks all 21 destinations at 1280, 1440, 1600, and 1920 CSS pixels, validates drawer behavior, exercises 1,000-event virtualization, and writes Dashboard, Timeline, Graph, Communications, and Details captures at 1280 and 1920 to `screenshots/`. It uses synthetic fixtures without modifying backend data.

The checked-in `screenshots/parakh-*.jpg` captures were taken through the app browser against the production build. The browser exports JPEGs at its own image scale; filename widths refer to the verified CSS viewport. Standalone Playwright Chromium could not launch in the Codex macOS sandbox, so the browser validation was performed through the app browser. `npm run build`, `npm run typecheck`, `npm run lint`, and the existing 19 backend tests passed.

`preview.html` is a separate legacy static demo and is not the redesigned React app. Use Vite or the production build to review this redesign.
