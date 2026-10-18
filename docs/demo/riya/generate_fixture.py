from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import csv,json,hashlib,sqlite3
from email.message import EmailMessage
from email.policy import SMTP
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape
BASE=Path(__file__).resolve().parents[3]
E=BASE/'evidence';G=BASE/'docs'/'demo'/'riya';IST=ZoneInfo('Asia/Kolkata');CASE='PARAKH-SYN-RIYA-001'
E.mkdir(parents=True,exist_ok=True);G.mkdir(exist_ok=True)
inventory=[];timeline=[]
def ts(h,day='2026-09-12'):return datetime.fromisoformat(day+'T'+h).replace(tzinfo=IST)
def utc(t):return t.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
def write(name,text): (E/name).write_text(text,encoding='utf-8')
def register(name,owner,source,note):
 inventory.append(dict(file=name,owner=owner,source=source,note=note,synthetic=True))
def csvfile(name,rows):
 with (E/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def event(t,kind,description,file,ref):
 timeline.append(dict(timestamp_ist=t.isoformat(),timestamp_utc=utc(t),kind=kind,description=description,source_file=file,raw_reference=ref))
messages=[
('09:05','Riya','Hello, I saw the investment advertisement. Is this safe?'),
('09:06','Agent Arjun','Welcome to Saffron Growth Club. Guaranteed return: INR 50,000 becomes INR 75,000 today.'),
('09:07','Riya','This is my savings. I do not want a loan.'),
('09:08','Agent Arjun','No loan. Limited slots. Complete KYC: https://kyc-saffron.example/verify'),
('09:10','Riya','The page asks for an OTP. Why?'),
('09:11','Agent Arjun','KYC update only. OTP bhejo, jaldi.'),
('09:12','Riya','[SYNTHETIC OTP REDACTED - no usable code]'),
('09:14','Agent Arjun','Call DEMO-PHONE-ARJUN. I will explain.'),
('09:17','Riya','You said guaranteed. Can I withdraw today?'),
('09:18','Agent Arjun','Yes. First send INR 25,000 to arjun.collect@demo. It is our collection account.'),
('09:24','Riya','Sending INR 25,000 now.'),
('09:26','Riya','Paid INR 25,000. Reference DEMO-UPI-001.'),
('09:27','Agent Arjun','Received. One more INR 25,000 unlocks the portfolio.'),
('09:28','Riya','That was not mentioned before.'),
('09:29','Agent Arjun','Urgent payment needed before the slot closes. Return guaranteed.'),
('09:32','Riya','I will send the remaining INR 25,000, then please stop.'),
('09:34','Riya','Second payment done. Reference DEMO-UPI-002.'),
('09:35','Agent Arjun','Your portfolio is processing.'),
('09:39','Riya','The website is not opening. I want my money back.'),
('09:40','Agent Arjun','Refund approved. Do not contact the bank yet.'),
('09:44','Agent Arjun','<Media omitted>'),
('09:44','Agent Arjun','06_refund_receipt_claim.pdf - INR 50,000 returned at 09:42. Reference DEMO-UPI-001.'),
('09:46','Riya','My bank still shows INR 32,500. No refund credit.'),
('09:47','Agent Arjun','Bank delay. Send INR 5,000 release fee.'),
('09:48','Riya','No. I am not paying another fee.'),
('09:52','Riya','I tried calling you. Please answer.'),
('10:02','Riya','I contacted the bank through its support channel.'),
('10:05','Agent Arjun','Wait until evening. Do not file a complaint.'),
('10:08','Riya','I am preserving the chats and bank records.'),
('10:20','Riya','I will report this. Do not contact me again.')]
def line(m,shift=0,bracket=False):
 h,a,b=m;t=ts(h+':00')+timedelta(minutes=shift)
 return (t.strftime('[%d/%m/%Y, %H:%M:%S] ') if bracket else t.strftime('%d/%m/%Y, %H:%M - '))+a+': '+b
write('01_whatsapp_riya_android.txt','12/09/2026, 09:00 - SYNTHETIC DEMO ONLY. All people, messages and identifiers are fictional.\n'+'\n'.join(line(m) for m in messages)+'\n')
register('01_whatsapp_riya_android.txt','Riya','Android-style WhatsApp export','30 messages and synthetic system notice. Source clock assumed accurate.')
for i,m in enumerate(messages,2):event(ts(m[0]+':00'),'chat',m[1]+': '+m[2],'01_whatsapp_riya_android.txt',f'line:{i}')
subset=[messages[i] for i in [0,1,8,11,16,20,21,22,24,28]]
write('02_whatsapp_linked_tablet.txt','[12/09/2026, 08:30:00] SYNTHETIC DEMO ONLY. Linked-tablet excerpt; source clock not corrected.\n'+'\n'.join(line(m,-30,True) for m in subset)+'\n')
register('02_whatsapp_linked_tablet.txt','Riya linked tablet','Bracketed WhatsApp export','Ten repeated messages recorded 30 minutes slow. Excerpt gaps do not prove deletion.')
bank=[];balance=85000
for day,h,kind,amount,party,ref,note in [
('2026-09-11','18:30:00','debit',1800,'DEMO-GROCERY','DEMO-CARD-001','Ordinary groceries'),
('2026-09-11','20:10:00','debit',700,'DEMO-TRANSPORT','DEMO-UPI-LOCAL','Ordinary transport'),
('2026-09-12','09:25:00','debit',25000,'arjun.collect@demo','DEMO-UPI-001','Investment payment 1'),
('2026-09-12','09:33:00','debit',25000,'arjun.collect@demo','DEMO-UPI-002','Investment payment 2'),
('2026-09-13','11:30:00','debit',499,'DEMO-GROCERY','DEMO-CARD-002','Ordinary household purchase')]:
 balance-=amount
 bank.append(dict(timestamp=ts(h,day).isoformat(),account='DEMO-ACCT-RIYA-001',type=kind,amount=f'{amount:.2f}',currency='INR',counterparty=party,utr=ref,balance=f'{balance:.2f}',note=note,synthetic='true'))
csvfile('03_bank_statement_riya.csv',bank)
register('03_bank_statement_riya.csv','Riya','Fictional bank CSV','11-13 September; opening 85,000, closing 32,001; no refund within this window.')
collection=[];balance=0
for h,kind,amount,party,ref in [
('09:25:05','credit',25000,'DEMO-ACCT-RIYA-001','DEMO-UPI-001'),
('09:33:05','credit',25000,'DEMO-ACCT-RIYA-001','DEMO-UPI-002'),
('09:36:00','debit',30000,'cashout.one@demo','DEMO-OUT-001'),
('09:38:00','debit',19500,'cashout.two@demo','DEMO-OUT-002')]:
 balance+=amount if kind=='credit' else -amount
 collection.append(dict(timestamp=ts(h).isoformat(),account='DEMO-ACCT-COLLECT-009',type=kind,amount=f'{amount:.2f}',currency='INR',counterparty=party,utr=ref,balance=f'{balance:.2f}',synthetic='true'))
csvfile('05_bank_statement_collection.csv',collection)
register('05_bank_statement_collection.csv','Collection account; legal operator unknown','Fictional bank disclosure to investigator','Zero opening; 50,000 incoming, 49,500 onward, 500 retained. Not obtained from victim handset.')
for name,rows in [('03_bank_statement_riya.csv',bank),('05_bank_statement_collection.csv',collection)]:
 for i,r in enumerate(rows,2):event(datetime.fromisoformat(r['timestamp']),'bank',f"{r['account']} {r['type']} INR {r['amount']} / {r['utr']}",name,f'row:{i}')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='DemoBody',fontName='Helvetica',fontSize=10,leading=15,textColor=colors.HexColor('#000129'),spaceAfter=10))
styles.add(ParagraphStyle(name='DemoSmall',fontName='Helvetica',fontSize=9,leading=13,textColor=colors.HexColor('#4A4D68')))
styles.add(ParagraphStyle(name='DemoTitle',fontName='Helvetica-Bold',fontSize=22,leading=27,textColor=colors.HexColor('#000129'),spaceAfter=16))
def p(t,style='DemoBody'):return Paragraph(escape(str(t)).replace('\n','<br/>'),styles[style])
def table(rows,widths):
 t=Table([[p(c,'DemoSmall') for c in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#F0EFF2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#E2E1E8')),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]));return t
def pdf(name,title,body):
 def page(c,d):
  c.setFont('Helvetica-Bold',9);c.setFillColor(colors.HexColor('#8F1D26'));c.drawString(42,810,'SYNTHETIC DEMO ONLY - NOT A VALID FINANCIAL OR LEGAL DOCUMENT')
  c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#4A4D68'));c.drawString(42,25,CASE+' | All identities and institutions are fictional');c.drawRightString(552,25,f'Page {d.page}')
 SimpleDocTemplate(str(E/name),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=62,bottomMargin=46,title=title,author='PARAKH synthetic fixture generator',invariant=1).build([p(title,'DemoTitle')]+body,onFirstPage=page,onLaterPages=page)
pdf('04_bank_statement_riya.pdf','Nayi Disha Demo Bank\nAccount statement',[
p('FICTIONAL INSTITUTION | Holder: Riya (invented) | DEMO-ACCT-RIYA-001','DemoSmall'),Spacer(1,14),
p('Period: 11 September 2026 00:00 IST through 13 September 2026 23:59 IST. Currency: INR.'),
table([['Opening','Total debits','Total credits','Closing'],['85,000.00','52,999.00','0.00','32,001.00']],[128]*4),Spacer(1,18),
table([['Date / time IST','Reference','Debit INR','Credit INR','Balance INR']]+[[r['timestamp'][:10]+'\n'+r['timestamp'][11:19],r['utr'],r['amount'],'-',r['balance']] for r in bank],[98,126,92,92,104]),Spacer(1,16),
p('DEMO-UPI-001 and DEMO-UPI-002 are outgoing INR 25,000 transfers to arjun.collect@demo. No incoming credit appears during this statement period.'),
p('This PDF and 03_bank_statement_riya.csv are two representations of the SAME synthetic records. Use the CSV for structured analysis. Do not count them as independent corroboration.','DemoSmall')])
register('04_bank_statement_riya.pdf','Riya','Presentation copy of statement 03','Duplicate representation, not an independent source.')
pdf('06_refund_receipt_claim.pdf','Refund confirmation',[
p('SAFFRON GROWTH CLUB - FICTIONAL DEMO PORTAL','DemoSmall'),Spacer(1,16),
table([['Claimed field','Value printed on the supplied receipt'],['Status','COMPLETED'],['Amount','INR 50,000.00'],['Paid to','Riya / DEMO-ACCT-RIYA-001'],['Payment reference','DEMO-UPI-001'],['Issued at','12 September 2026, 09:42:00 IST'],['Claimed sender','Saffron Growth Club refund desk']],[152,360]),Spacer(1,18),
p('Your investment refund has been successfully processed. Allow time for your balance to update.'),
p("Synthetic prop supplied by the fictional chat contact at 09:44 IST. Status and amount are the sender's claims, not verified bank facts. This prop cannot be used to transfer or claim funds.",'DemoSmall')])
register('06_refund_receipt_claim.pdf','Supplied by Agent Arjun display name','Synthetic attachment in primary chat','False refund claim: reuses first-debit reference with changed amount/direction. Readable PDF; no fake metadata evidence.')
pdf('15_riya_incident_account.pdf','Riya - incident account',[
p('SYNTHETIC FIRST-PERSON ACCOUNT | Not an official complaint or police form','DemoSmall'),Spacer(1,14),
p('Recorded: 13 September 2026, 15:00 IST. Case: '+CASE),
p('I am Riya, a fictional person. On 12 September I contacted someone using the display name Agent Arjun after seeing an investment advertisement. They promised guaranteed returns, sent a KYC link and persuaded me to make two INR 25,000 payments to arjun.collect@demo.'),
p('When I asked for a refund, the contact sent a receipt claiming INR 50,000 had been returned. I did not see that credit in my supplied statement through 13 September. I refused a further INR 5,000 release-fee request.'),
p('I used an Android phone and an older linked tablet. The tablet clock was 30 minutes slow before a manual sync at 09:50 IST. The tablet chat file is an excerpt; missing messages in that excerpt do not establish deletion.'),
p('I provide chats, my account statement, the received receipt, location history, call export, browser history and emails. I do not know the legal identity of the contact. The investigator separately obtained the collection account and tower records in this synthetic scenario.'),
p('This fictional account is a source assertion to compare against the records, not independent proof of every statement. No real address, signature, Aadhaar, PAN, OTP or phone number is included.','DemoSmall')])
register('15_riya_incident_account.pdf','Riya','Fictional complainant narrative','Not an official legal form or certificate.')
points=[('08:45:00',28.6200,77.3600,25,'Residential area'),('09:10:00',28.6201,77.3601,22,'Residential area'),('09:25:00',28.6200,77.3602,30,'Residential area'),('09:33:00',28.6201,77.3601,24,'Residential area'),('09:47:00',28.6200,77.3600,28,'Residential area'),('10:15:00',28.6212,77.3610,40,'Nearby street'),('10:30:00',28.6250,77.3640,35,'Demo support-desk vicinity'),('10:55:00',28.6252,77.3641,28,'Demo support-desk vicinity'),('11:15:00',28.6201,77.3600,30,'Residential area')]
locations=[dict(timestamp=utc(ts(h)),lat=lat,lon=lon,accuracy_m=acc,owner='Riya',device_id='DEMO-DEVICE-RIYA-A',place_label=place,synthetic=True) for h,lat,lon,acc,place in points]
write('07_gps_location_riya.json',json.dumps(dict(synthetic=True,case_id=CASE,notice='Invented approximate points in a broad Noida area; not a real home or business address.',locations=locations),indent=2)+'\n')
register('07_gps_location_riya.json','Riya Android','Synthetic GPS export','UTC timestamps. Victim location only; accuracy is simulated, not a suspect route.')
for i,r in enumerate(locations,1):event(datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')).astimezone(IST),'location',r['place_label']+' (invented point)','07_gps_location_riya.json',f'location:{i}')
calls=[]
for i,(h,caller,called,duration,direction,status) in enumerate([
('09:14:00','DEMO-PHONE-RIYA','DEMO-PHONE-ARJUN',152,'outgoing','answered'),
('09:22:00','DEMO-PHONE-ARJUN','DEMO-PHONE-RIYA',95,'incoming','answered'),
('09:31:00','DEMO-PHONE-ARJUN','DEMO-PHONE-RIYA',48,'incoming','answered'),
('09:50:00','DEMO-PHONE-RIYA','DEMO-PHONE-ARJUN',0,'outgoing','unanswered'),
('09:52:00','DEMO-PHONE-RIYA','DEMO-PHONE-ARJUN',0,'outgoing','unanswered'),
('10:00:00','DEMO-PHONE-RIYA','DEMO-PHONE-BANK',210,'outgoing','answered'),
('10:12:00','DEMO-PHONE-RIYA','DEMO-PHONE-FRIEND',88,'outgoing','answered')],1):
 calls.append(dict(timestamp=ts(h).isoformat(),caller=caller,called=called,duration_sec=duration,direction=direction,status=status,owner='Riya',record_id=f'DEMO-CALL-{i:03}',synthetic='true'))
csvfile('08_call_records_riya.csv',calls)
register('08_call_records_riya.csv','Riya handset','Synthetic call export','Non-dialable DEMO tokens. No audio or transcript. Seven calls.')
for i,r in enumerate(calls,2):event(datetime.fromisoformat(r['timestamp']),'call',f"{r['direction']} {r['status']} {r['duration_sec']} sec",'08_call_records_riya.csv',f'row:{i}')
towers=[dict(timestamp=r['timestamp'],caller=r['caller'],called=r['called'],cell_id='DEMO-TOWER-N01' if i<5 else 'DEMO-TOWER-N02',lac='DEMO-LAC-001',duration_sec=r['duration_sec'],tower_lat=28.621 if i<5 else 28.624,tower_lon=77.361 if i<5 else 77.364,coverage_radius_m=1500,subject='Riya SIM only',synthetic='true') for i,r in enumerate(calls)]
csvfile('09_cdr_tower_context.csv',towers)
register('09_cdr_tower_context.csv','Riya SIM','Separate fictional telecom disclosure','Coarse 1.5 km tower circles. No suspect cells; no basis for asserting co-location.')
def eml(name,sender,subject,t,body,msgid):
 m=EmailMessage(policy=SMTP);m['From']=sender;m['To']='Riya <riya@parakh-demo.example>';m['Subject']=subject;m['Date']=t.strftime('%a, %d %b %Y %H:%M:%S %z');m['Message-ID']=f'<{msgid}@parakh-demo.example>';m['X-Parakh-Synthetic']='true';m.set_content('SYNTHETIC DEMO ONLY - all identities and messages are invented.\n\n'+body);(E/name).write_bytes(m.as_bytes());event(t,'email',subject,name,'message:1')
eml('10_email_investment_pitch.eml','Saffron Growth <desk@saffron-growth.example>','Synthetic portfolio activation',ts('09:09:00'),'Your DEMO portfolio is reserved. Contact Agent Arjun in the existing chat. Demo link: https://kyc-saffron.example/verify\nDo not enter real credentials.','pitch-001')
register('10_email_investment_pitch.eml','Riya mailbox','Fictional received email','Reserved domain; no validated SPF/DKIM claims.')
eml('11_email_bank_support.eml','Demo Bank Support <support@nayi-disha-bank.example>','Demo transaction-reference review',ts('12:00:00','2026-09-13'),'Synthetic support reference DEMO-SUPPORT-014. In the account records reviewed through 13 September 2026 11:59 IST, DEMO-UPI-001 and DEMO-UPI-002 are outgoing debits of INR 25,000 each. No incoming credit of INR 50,000 is present in this reviewed window. This is a fictional bank response, not a recovery guarantee.','bank-001')
register('11_email_bank_support.eml','Riya mailbox','Fictional support response','Explicit review cutoff; no conclusion about all future credits.')
(E/'12_browser_history_riya.sqlite').unlink(missing_ok=True)
con=sqlite3.connect(E/'12_browser_history_riya.sqlite');con.execute('DROP TABLE IF EXISTS urls');con.execute('CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_time_utc TEXT, synthetic INTEGER)')
visits=[('09:02:00','https://saffron-growth.example','Synthetic investment ad'),('09:09:00','https://kyc-saffron.example/verify','Synthetic KYC page'),('09:38:00','https://saffron-growth.example/portfolio','Synthetic portfolio page'),('09:59:00','https://nayi-disha-bank.example/support','Synthetic bank support')]
con.executemany('INSERT INTO urls(url,title,visit_time_utc,synthetic) VALUES (?,?,?,1)',[(u,t,utc(ts(h))) for h,u,t in visits]);con.commit();con.close()
register('12_browser_history_riya.sqlite','Riya browser','Minimal synthetic SQLite urls export','Four visits. Current prototype extracts titles/URLs but ignores visit_time_utc. Visits do not prove submission of credentials.')
write('13_device_clock_observation.txt',f'''SYNTHETIC DEMO ONLY
Case: {CASE}
Observer: DEMO-ANALYST
Source: controlled synthetic observation, not a real signed NTP capture.
Reference: 2026-09-12T09:50:00+05:30
Android display: 2026-09-12T09:50:00+05:30
Tablet display BEFORE sync: 2026-09-12T09:20:00+05:30
Tablet display AFTER sync: 2026-09-12T09:50:00+05:30
Observed tablet offset: -1800 seconds
Simulation assumption: this fixed offset applied earlier that morning.
A single observation alone does not establish historical clock stability.
Raw chat files retain their recorded timestamps.
''')
register('13_device_clock_observation.txt','Riya devices','Synthetic operator observation','Clock assumption explicit; not an independent timing attestation.')
write('14_acquisition_context.txt',f'''SYNTHETIC DEMO ONLY - INVENTED ACQUISITION CONTEXT
Case: {CASE}
Received: 2026-09-14T10:00:00+05:30
One investigator interface. No real person, subscriber, device, institution or case exists.
Android exports: primary chats, GPS, call records and browser history.
Tablet export: selected ten messages only, uncorrected clock.
Victim statement CSV and PDF: same fictional disclosure, not independent sources.
Collection statement and tower records: separate fictional responses provided to investigator, not recovered from victim phone.
Refund receipt: supplied by chat contact.
Scenario mapping: arjun.collect@demo -> DEMO-ACCT-COLLECT-009.
Agent Arjun is a display name; legal identity and downstream account control are unresolved.
No source was edited after generation. No pre-import digital signature or chain of custody is claimed.
Never upload demo-guide/ or its ground truth as original evidence.
''')
register('14_acquisition_context.txt','Investigator','Synthetic provenance note','Separates phone exports, alleged attachment and additional disclosures.')
# Inventory is hashed after all source documents are complete.
manifest=[]
for item in sorted(inventory,key=lambda r:r['file']):
 data=(E/item['file']).read_bytes();manifest.append({**item,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'md5':hashlib.md5(data).hexdigest()})
(G/'manifest.json').write_text(json.dumps(dict(case_id=CASE,synthetic=True,timezone='Asia/Kolkata',warning='Generated baseline only, not a signed audit chain or legal attestation.',evidence=manifest),indent=2)+'\n')
timeline.sort(key=lambda r:(r['timestamp_utc'],r['source_file'],r['raw_reference']))
with (G/'ground_truth_timeline.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(timeline[0]));w.writeheader();w.writerows(timeline)
(G/'generate_fixture.py').write_text(Path(__file__).read_text())
print(json.dumps(dict(files=len(manifest),primary_messages=len(messages),tablet_messages=len(subset),victim_bank_rows=len(bank),collection_bank_rows=len(collection),calls=len(calls),gps_points=len(locations),derived_timeline=len(timeline)),indent=2))
