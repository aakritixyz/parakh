# Step 1: sign-in, case creation and roles

## Implemented

One investigator interface with authenticated Active Cases or a bannered read-only synthetic demo. New case records include title, case/FIR number, jurisdiction, offence type, description, lead investigator and team memberships. The list shows status, evidence count and audit-derived last activity. Account and case roles are shown explicitly. The case panel exposes evidence upload, team management and the real audit log.

Passwords use Argon2id; existing bcrypt hashes upgrade after a successful sign-in. V2 access JWTs expire after 15 minutes. Refresh cookies last seven days, are HttpOnly and SameSite=Strict, and are Secure in production. Refresh rotates atomically, and replay revokes the session. Logout immediately invalidates access and refresh credentials. Refresh and logout check Origin when supplied. Access tokens exist only in memory. No passwords are embedded in source or browser builds.

The first-run `create-admin` command refuses to run when an admin already exists. Operators can provision other roles using `create-user`; admins can also use the account form. Credentials are always operator inputs.

## Run

From the repository root:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
# Configure private .env with a unique SECRET_KEY, DATABASE_URL and STORAGE_ROOT.
# Preserve/back up any existing database before migrating.
python -m app.cli migrate
alembic check
python -m app.cli create-admin
python -m app.cli create-user --role investigator --username investigator
python -m app.cli create-user --role prosecutor --username prosecutor
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173/signin.html. Enter your account credentials. Choose **New case**, create **Riya: investment scam complaint**, select an investigator lead and add a prosecutor account with the prosecutor case role. The title is user input, never shown on the public landing page. Inspect its case audit log, then sign out and sign in as the prosecutor. New case and Upload evidence are disabled; server writes return 403 too. Read-only demo is available directly from sign-in without backend authentication.

For preview builds on port 4173 or 5183, include that exact origin in CORS_ORIGINS if you override the default list. Serve frontend and API behind a common origin with HTTPS in production. API startup requires current migrations. Older JWTs without a revocable session require signing in again.

## Role rules

| Role | Cases visible | Evidence writes | Create case | Manage team |
| --- | --- | --- | --- | --- |
| Admin | All | Yes | Yes | Yes |
| Investigator | Membership only | When case role permits | Yes | As case investigator |
| Analyst | Membership only | When case role permits | No | No |
| Prosecutor | Membership only | No | No | No |

A membership cannot exceed the account role. Read-only membership narrows an investigator or analyst account. Removing membership takes effect on the next request even with an existing JWT. Lead investigators must retain investigator access. Admins have an explicit global oversight override. The legacy V1 surface uses the same case authorization guard, including evidence, job and nested record ownership. Cross-case administration endpoints require admin access.

## API and audit

New contracts are under `/api/v2/auth` and `/api/v2/cases`, plus admin account provisioning at `/api/v2/users`. V1 response shapes and legacy token lifetime remain compatible; legacy-issued sessions are now revocable. Anonymous account bootstrap is closed.

Sign-in records `auth.signed_in`; creation records `case.created`; each member records `case.member_added`. Role changes, removals, session rotation/replay and logout are also audited. A serialized audit head prevents concurrent writers from forking the global hash chain. The UI displays case entries and the viewer's own session entries, with an explicit filtered scope. Global chain verification runs server-side. A matching hash establishes integrity, not truth.

## Verification and limits

Run `make lint test` from the root with the backend virtual environment active. Coverage includes account bootstrap, Argon2/bcrypt migration, token expiry, rotation/replay, revocation, malformed client responses, concurrent refresh, membership revocation, nested cross-case access, analyst restrictions, prosecutor denials on V1/V2, required case fields, audit actions, migrations and tamper checks.

Browser checks cover real case creation, sign-in restoration after reload, logout, the audit log, prosecutor-disabled controls, and the bannered no-login demo. Screenshots and complete test output are delivered separately with this step.

This step adds no ML. MFA, password-reset flows, signed audit entries, persisted finding review and later forensic/ML features remain planned. Metadata editing has a protected API; a metadata edit form is planned. Existing workspace demo heuristics remain labelled and are not new Step 1 findings. The demo custody chain remains explicitly simulated. No synthetic findings are inserted into a newly created empty backend case. No uploaded originals are edited.
