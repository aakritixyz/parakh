from pathlib import Path
import csv,json,hashlib,sys
from decimal import Decimal
from pypdf import PdfReader
guide=Path(__file__).resolve().parent
base=guide.parents[2]
e=base/'evidence'
manifest=json.loads((guide/'manifest.json').read_text())
assert len(manifest['evidence'])==15
for item in manifest['evidence']:
 assert hashlib.sha256((e/item['file']).read_bytes()).hexdigest()==item['sha256']
for name,opening,closing in [('03_bank_statement_riya.csv',85000,32001),('05_bank_statement_collection.csv',0,500)]:
 rows=list(csv.DictReader((e/name).open()));balance=Decimal(opening)
 for r in rows:
  balance+=Decimal(r['amount'])*(1 if r['type']=='credit' else -1)
  assert balance==Decimal(r['balance']),(name,r)
 assert balance==Decimal(closing)
for name in ['04_bank_statement_riya.pdf','06_refund_receipt_claim.pdf','15_riya_incident_account.pdf']:
 r=PdfReader(e/name);print(name,'pages',len(r.pages))
 assert len(r.pages)==1
 assert 'SYNTHETIC DEMO ONLY' in r.pages[0].extract_text()
# Read-only smoke check against the existing prototype's parsers, without ingesting anything.
sys.path.insert(0,str(base/'backend'))
from app.parsers.registry import ParserRegistry
from app.core.config import get_settings
get_settings.cache_clear()
parsed={}
for item in manifest['evidence']:
 path=e/item['file']
 parser=ParserRegistry.detect(path.name,'application/pdf' if path.suffix=='.pdf' else '',path)
 events=list(parser.parse(path,case_id=999,evidence_id=999))
 parsed[path.name]={'parser':parser.name,'records':len(events)}
 print(path.name,parser.name,len(events))
a=list(ParserRegistry.detect('01_whatsapp_riya_android.txt','',e/'01_whatsapp_riya_android.txt').parse(e/'01_whatsapp_riya_android.txt',case_id=1,evidence_id=1))
b=list(ParserRegistry.detect('02_whatsapp_linked_tablet.txt','',e/'02_whatsapp_linked_tablet.txt').parse(e/'02_whatsapp_linked_tablet.txt',case_id=1,evidence_id=2))
primary={r.content:r for r in a if r.actor_entities}
for r in b:
 if r.actor_entities:assert (primary[r.content].timestamp_utc-r.timestamp_utc).total_seconds()==1800
assert parsed['01_whatsapp_riya_android.txt']['records']==31
assert parsed['02_whatsapp_linked_tablet.txt']['records']==11
assert parsed['07_gps_location_riya.json']['records']==9
assert parsed['08_call_records_riya.csv']['records']==7
assert parsed['12_browser_history_riya.sqlite']['records']==4
report={'hashes':'15/15 passed','balance_reconciliation':'passed','tablet_clock_offset_seconds':-1800,'pdfs':'3 readable single-page documents, visually reviewed','parser_smoke_check':parsed,'note':'Parse only, no existing database/vault touched. Generic parser counts include synthetic notices and provenance text; they are not independent investigative events.'}
(guide/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('All fixture checks passed.')
