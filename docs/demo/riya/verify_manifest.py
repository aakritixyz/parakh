"""Generated fixture SHA-256 check only; not a signed audit-chain verifier."""
from pathlib import Path
import hashlib,json,sys
guide=Path(__file__).resolve().parent
manifest=json.loads((guide/'manifest.json').read_text())
evidence=guide.parents[2]/'evidence'
for item in manifest['evidence']:
    path=evidence/item['file']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
        print('FAIL:',item['file'])
        sys.exit(1)
print('PASS:',len(manifest['evidence']),'synthetic files match the generated SHA-256 baseline.')
