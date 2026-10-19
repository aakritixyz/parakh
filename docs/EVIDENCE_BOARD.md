# Evidence board

The Board view is a source-linked, freeform investigation canvas. Its permanent warning is: **“A line on this board shows a relationship in the records, or a hypothesis. It does not prove involvement.”** The bundled board uses only the synthetic Riya pack. `docs/demo/riya/ANSWER_KEY.md` remains teaching ground truth and is never imported as evidence.

## Run

Apply migrations and start the API from `backend/`, then start Vite from `frontend/`:

```text
python -m app.cli migrate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
npm run dev
```

Open `http://127.0.0.1:5173/signin.html`, sign in, open a case containing the Riya pack, and choose **Board**. The offline demo also exposes the complete Riya board, but server audit, PDF attachment and role checks require a signed-in case.

## Data and integrity

- The stored JSON is schema version 1. Cards, strings, zones, exact positions, locked positions, viewport, caption and exhibit selection are persisted. Writes use optimistic revisions.
- Every mutating request records its actor, action, target, revision and canonical board SHA-256 in the existing signed, hash-chained audit log.
- Named snapshots retain the complete JSON and its hash. Loading a snapshot restores identical coordinates and seed.
- Every non-note card requires a receipt with file, source reference and hash. Notes are forced to display “Investigator note, not evidence”.
- Investigator and analyst case members may edit. Prosecutors are read-only in both the UI and API.
- PNG/PDF export records the board hash, caption and receipt list. The most recent board PDF is appended as a page to the Step 17 case report.

## Algorithms and fallbacks

- Auto-arrange: NetworkX seeded force-directed layout (`seed=51026`, 1.2-second budget), preserving locked positions; radial fallback, or grid for more than 500 cards. The UI also has a deterministic grid fallback when offline.
- Connect these: deterministic metric-closure Steiner approximation with a one-second budget. A timed-out result is labelled `incomplete`.
- Shortest path: weighted Dijkstra; established strings cost less than possible or hypothesis strings.
- Communities/card size: seeded Louvain communities and normalized betweenness centrality.
- Time-respecting path: breadth-first traversal that does not move backward across timestamped cards.
- Find gaps: reuses the Step 4 alias-matcher identity and labels its output with model/version, confidence and reasons. Output is always a lead, never a finding.
- Optional CP-SAT crossing/overlap minimization is not implemented; it remains **planned [T2]**. Realtime multi-user editing remains **planned [T3]**.

## Performance measurement

Run `npm run test:board-performance`. The deterministic measurement uses 500 cards, 1,500 strings, seed 51026 and 240 pan/zoom frames. On the October 19, 2026 validation machine:

| Measure | Result |
| --- | ---: |
| Median JS frame work | 0.007 ms |
| 95th percentile | 0.088 ms |
| Maximum | 0.840 ms |
| Budget | 16.7 ms |

Pan and zoom update one SVG `viewBox`; card/string geometry is not recomputed. This benchmark measures the deterministic JavaScript pan/zoom path and minimap projection, not GPU paint time across every browser/device.

## Riya acceptance route

The seeded board pins Riya, Agent Arjun, the payment handle and phone, victim/collection/onward accounts, both payment rows, the false refund receipt, key pitch message, victim location and a caution note. Established strings cite direct bank/chat records; possible strings preserve identity uncertainty; the refund conflict is crossed; the unsupported account-control string is dashed and labelled `not established`.

Select **Riya** and **cashout.one@demo**, then choose **Connect these**. The highlighted source-backed path runs through the victim account/payment and collection account to the onward account. Save a named snapshot, move an unlocked card, then reload the snapshot to restore the same seed and coordinates. Delete/undo, snapshot, analysis and export actions can be inspected under the case audit log.
