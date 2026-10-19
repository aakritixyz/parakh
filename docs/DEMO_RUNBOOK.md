# Five-minute Riya demo

Only the fifteen synthetic files in `evidence/` are source evidence. The answer key in
`docs/demo/riya/ANSWER_KEY.md` is teaching ground truth, never uploaded evidence.

From a fresh database: `make backend-migrate`, `make create-admin` (choose credentials),
`make backend`, and in another terminal `make frontend`. Sign in at
http://127.0.0.1:5173/signin.html. Create “Riya: investment scam complaint”, set the
jurisdiction to “Synthetic demo”, and upload `evidence/` with owner Riya and logical
export acquisition notes. Review import warnings before confirming. Register the
synthetic baseline with `cd backend && python -m app.cli ml-foundation` if model-card
metrics are to be included. These are metrics on synthetic data only.

- 00:00–00:35: Sign in, open the case, show immutable sources and the integrity chip.
- 00:35–01:10: Comms: show guaranteed-return pressure and OTP request with receipts.
- 01:10–01:55: Money: two INR 25,000 debits, INR 30,000 and INR 19,500 onward,
  INR 500 remaining. Separate observed transfers from assumed allocation.
- 01:55–02:40: Authenticity: claimed INR 50,000 refund reuses an outgoing INR 25,000
  reference. No matching incoming credit occurs in the supplied coverage. Show alternatives.
- 02:40–03:15: Timeline: explain the tablet's 30-minute clock offset and excerpt limits.
  Play/pause the replay; timing does not establish causation. Suspect location is unknown.
- 03:15–03:50: Assistant: ask “Where did Riya's money go?”, open a source, then ask
  “What was said in the calls?” and require refusal if no supporting transcript exists.
- 03:50–04:30: Findings: add/review the two-payment finding with source rows; add it and
  source records to the exhibit tray, save, then show the page-budget selection result.
- 04:30–05:00: Reports: download the PDF and portable ZIP. Extract verify.py and run
  `python3 verify.py path/to/bundle.zip`. Show the PASS result and counsel-review draft.

## Validation commands

`make lint test` runs repository checks. `make smoke` starts isolated temporary services,
creates an ephemeral admin with a generated password and uploads the synthetic pack.
No real account or case is used. `make benchmark` writes measured results to
`docs/validation/search-benchmark.json`. `make dependency-audit` scans dependencies;
findings or unavailable advisory services are reported, never called a pass.

## Limits and planned work

Rate limiting is process-local and bounded; a shared production limiter is planned.
The exhibit page budget uses declared page estimates, not the final PDF page count.
The PDF prints non-ASCII characters as escaped Unicode when no supporting font is
available; originals remain in events.csv/review.json. Model registry cards are labelled
as a registry snapshot; registration does not establish actual case inference.
Full forensic legal certification is planned. The Section 63 text is an unsigned draft
for verification with legal counsel. Neural tamper localisation, deepfakes, graph neural
networks, stylometry, Hawkes processes, Z3, private set intersection, roaring bitmaps,
HyperLogLog, DuckDB and HNSW are planned. Large-data aggregation and production
multi-user load remain planned wherever the stored benchmark reaches its time guard.

## Recorded local validation (19 October 2026)

The stored 20,000-row measurement used seed 18026 on local SQLite. Indexed payment
filtering completed in about 110 ms and cold FTS search in about 235 ms on this host.
The unfiltered query reached its guard; this is not a production throughput claim.
`EXPLAIN` confirms the composite case/type/time index.

The local Playwright process was blocked before any UI step by macOS sandbox
MachPort permission enforcement. The smoke test is also configured in GitHub CI;
a local browser failure is not reported as a smoke pass.

The frontend advisory scan reports zero vulnerabilities after the Vite toolchain
update. The Python scan covers the installed direct requirements on this host,
not a clean full transitive lock. It reports advisories in pydantic-settings, Pillow,
pytest and python-jose; the reported python-jose advisory has no published fix.
Consult `docs/validation/python-audit.json` for IDs and available patched versions.
A clean dependency audit and production rollout remain pending those findings.
