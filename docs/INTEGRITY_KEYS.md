# Audit signing keys

Parakh creates one Ed25519 private key on first use at
`data/storage/keys/audit-ed25519-private.pem` (or `AUDIT_SIGNING_KEY_PATH`). The
file is written with mode `0600`. Never commit or include this private key in a
case export. Back it up through the deployment's secret-management system and
limit access to the Parakh service account.

Each audit entry is signed immediately. Exports include only the public key,
key identifier and signature, so the standalone verifier can check them. A
checkpoint is also written every 25 entries. If the private key is lost, old
signatures remain verifiable but new entries require a new key and documented
key identifier. If it is exposed, preserve the old public key for verification,
rotate the private key, and record the incident and rotation in custody notes.

RFC 3161 external timestamping is disabled by default. Enabling it later must
not replace local hashes, signatures or checkpoints.
