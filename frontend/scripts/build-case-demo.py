"""Build the demo from original synthetic files, preserving source references."""
from pathlib import Path
import sys,json,csv,sqlite3,shutil,hashlib
from pypdf import PdfReader
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'backend'))
from app.parsers.registry import ParserRegistry
folder=root/'evidence'; dest=root/'frontend/public/demo-evidence';dest.mkdir(exist_ok=True)
manifest=json.loads((root/'docs/demo/riya/manifest.json').read_text())
files=[];events=[];audit=[];previous='0'*64
for index,item in enumerate(manifest['evidence'],1):
 path=folder/item['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
 parser=ParserRegistry.detect(path.name,'application/pdf' if path.suffix=='.pdf' else '',path)
 parsed=list(parser.parse(path,case_id=1,evidence_id=index))
 rows=[]
 if path.suffix=='.pdf':
  for page,n in zip(PdfReader(path).pages,range(1,100)):
   rows.append({'ref':f'page:{n}','text':page.extract_text()})
 elif path.suffix=='.sqlite':
  db=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
  table=db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()[0]
  cur=db.execute('SELECT * FROM '+table);headers=[c[0] for c in cur.description]
  rows=[{'ref':f'row:{n}','text':json.dumps(dict(zip(headers,row)),ensure_ascii=False)} for n,row in enumerate(cur,1)];db.close()
 else:rows=[{'ref':f'line:{n}','text':line} for n,line in enumerate(path.read_text().splitlines(),1)]
 raw=[]
 for i,event in enumerate(parsed,1):
  record=event.model_dump(mode='json');record['id']=f'E{index:02}-{i:03}';record['file']=path.name
  record['label']=record['content']
  if not record['raw_ref'] and path.suffix=='.pdf':record['raw_ref']='page:1' # All supplied PDFs are verified single-page sources.
  if not record['content'] and record.get('location'):record['content']=json.dumps(record['location'])
  if record['raw_ref'] and not any(row['ref']==record['raw_ref'] for row in rows):
   ref=record['raw_ref']; text=record['content']
   if path.suffix=='.json' and ref.startswith('location:'):
    text=json.dumps(json.loads(path.read_text())['locations'][int(ref.split(':')[1])-1],ensure_ascii=False,indent=2)
   elif path.suffix=='.sqlite':
    match=next((row for row in rows if row['ref']==f"row:{ref.split(':')[-1]}"),None)
    if match:text=match['text']
   rows.append({'ref':ref,'text':text})
  events.append(record);raw.append(record)
 f={**item,'id':index,'parser':parser.name,'records':len(parsed),'rows':rows}
 if path.suffix=='.csv':f['table']=list(csv.DictReader(path.open()))
 files.append(f);shutil.copyfile(path,dest/path.name)
 payload={'sequence':index,'action':'Synthetic baseline registered','filename':path.name,'sha256':item['sha256'],'previous_hash':previous,'actor':'Demo fixture generator','timestamp':'2026-10-18T00:00:00Z'}
 previous=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 audit.append({**payload,'entry_hash':previous})
result={'files':files,'events':events,'audit':audit,'notice':'Synthetic demo chain generated from the fixture inventory. Not a signed acquisition or real investigation log.'}
(root/'frontend/src/components/casework/demo.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(f'Built {len(files)} sources, {len(events)} parsed records, {len(audit)} simulated custody entries.')
