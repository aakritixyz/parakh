# Step 2: evidence intake and sealing

## Implemented flow

Open a writable case and choose **Upload evidence**. Record the owner, optional device, who handed the material over, the received time, acquisition method and notes. Files, folders and ZIP archives can be added by picker or drag and drop. Before import, every row shows an editable suggested source type, owner, device and file note.

**Start import** streams each original through SHA-256 and MD5 hashing into the content-addressed vault. The server never reads the whole upload for hashing. New vault blobs are made read-only. Evidence metadata, the vault key and an `evidence.sealed` hash-chain entry are committed before a background parser sees the path. Progress is reported as Hashing, Stored, Parsing, Indexing and Done. Import jobs can be cancelled before indexing is committed and failed/cancelled jobs can be retried.

Exact SHA-256 duplicates within a case return the existing evidence record and do not create a second row. Idempotency keys protect request retries. MD5 is recorded only for legacy forensic compatibility; SHA-256 is the integrity identity.

ZIP intake rejects absolute/parent paths, Windows separator paths, encrypted members, excessive member counts, excessive declared expansion and excessive compression ratios. Each accepted file member streams into the same sealing path and is linked to the parent archive using its original member path. Limits come from private server configuration:

```text
MAX_UPLOAD_BYTES=536870912
MAX_ZIP_MEMBERS=1000
MAX_ZIP_UNCOMPRESSED_BYTES=1073741824
MAX_ZIP_RATIO=100
```

Magic-byte detection records the detected MIME type independently of the filename and declared browser MIME. A PDF, ZIP, SQLite database or supported image with contradictory bytes receives a visible warning. ZIP files whose contents fail safety validation are rejected before database commit.

## Run

Back up the database, then apply the migration and start both services:

```bash
cd ~/Desktop/parakh/backend
source .venv/bin/activate
python -m app.cli migrate
alembic check
uvicorn app.main:app --reload
```

```bash
cd ~/Desktop/parakh/frontend
npm install
npm run dev
```

Sign in as an investigator, open **Riya: investment scam complaint**, choose **Upload evidence**, and select `~/Desktop/parakh/evidence/`. Use Riya as owner and complete the handover fields. All 15 files should reach Done. The case then exposes the parsed workspace.

## Verification

`make lint test` covers all 15 synthetic sources, streaming hashes, read-only vault permissions, exact duplicate rejection, isolated tamper failure, magic-byte mismatches, path traversal, compression-ratio bombs, ZIP child hashes, job cancel/retry, access controls, migrations and frontend request metadata.

A matching verification hash proves only that the stored bytes still match the sealed original. It does not establish that the source content is true. Parsing and indexing can be retried without modifying the vault original. No ML is used in this step.

The current queue is an in-process background queue suitable for the local prototype. Durable multi-process workers and restart recovery remain planned. ZIP containers are preserved as parent evidence; their accepted file members are child evidence. Folder selection is provided by the browser and uploads each selected file separately because browsers do not transmit the local folder itself.
