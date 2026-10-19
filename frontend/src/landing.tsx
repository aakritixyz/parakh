import React from "react";
import { createRoot } from "react-dom/client";
import { ArrowRight, ArrowUpRight, Check, ChevronRight, Clock3, FileCheck2, Files, Fingerprint, FolderInput, GitBranch, Globe2, MapPin, MessageSquare, Network, ScanLine, Search, ShieldCheck, Sparkles } from "lucide-react";
import { BrandMark } from "./components/ui/BrandMark";
import "./styles.css";
import "./landing-refined.css";

const capabilities = [
  { Icon: FolderInput, title: "Bring every source together", hindi: "संग्रह", text: "Start with logical exports: chats, bank statements, call records, documents and location history.", detail: "Evidence intake", target: "#workflow" },
  { Icon: Search, title: "Find the meaningful detail", hindi: "खोज", text: "Search across records, narrow the context and return to the original file behind a result.", detail: "Search & exploration", target: "#workspace" },
  { Icon: Fingerprint, title: "Check what has changed", hindi: "सत्यापन", text: "Review file hashes and custody history. Unchanged since sealing does not mean a record is true.", detail: "Integrity & provenance", target: "#principles" },
  { Icon: ScanLine, title: "Examine the inconsistencies", hindi: "परख", text: "Compare a document with other records, review suspicious signals and keep alternative explanations visible.", detail: "Authenticity review", target: "#workspace" },
  { Icon: Network, title: "Connect the evidence", hindi: "संबंध", text: "Explore people, identifiers and transfers. Bring cited records onto a visual investigation board.", detail: "Graph & investigation board", target: "#workspace" },
  { Icon: Clock3, title: "Reconstruct the sequence", hindi: "क्रम", text: "Build a source-linked timeline, inspect clock uncertainty and replay the sequence for review.", detail: "Timeline & replay", target: "#workflow" },
];
const previews = [
  { label: "Evidence", Icon: Files, title: "The detail is always within reach.", body: "Review the source, its recorded time and the context around it. Follow a finding back to the records that support it.", image: "evidence-preview.jpg", alt: "Parakh evidence interface preview", note: "Interface preview · Synthetic demonstration data" },
  { label: "Timeline", Icon: Clock3, title: "A sequence you can interrogate.", body: "Put different records on one timeline. Examine the source timestamps and the uncertainty behind their order.", image: "timeline-preview.jpg", alt: "Parakh timeline interface preview", note: "Interface preview · Synthetic demonstration data" },
  { label: "Connections", Icon: Network, title: "Follow the links. Keep the proof.", body: "Link conversations, accounts and records into a working picture. A connection is a lead to examine, never automatic proof.", image: null, alt: "", note: "Illustrative connection map · Not a case finding" },
];
const connectionDetails = ["A working picture built from separate records. Select a source to inspect the connection.", "A conversation can contain a payment request. Check its wording and original timestamp.", "A bank row records a transfer. Attribution needs supporting records.", "A call log records contact, not what was said.", "A location record adds context. Proximity alone does not prove people were together."];
function EvidenceLens() {
  const surface = React.useRef<HTMLDivElement>(null);
  const position = React.useRef({ x: 62, y: 44 });
  const move = (x: number, y: number) => {
    const next = { x: Math.min(94, Math.max(6, x)), y: Math.min(90, Math.max(10, y)) };
    position.current = next;
    surface.current?.style.setProperty("--lens-x", `${next.x}%`);
    surface.current?.style.setProperty("--lens-y", `${next.y}%`);
  };
  const documentContents = (inspected: boolean) => <>
    <div className="pl-document-heading"><Fingerprint/><span>PARAKH / DOCUMENT REVIEW<small>ILLUSTRATIVE RECORD · NOT CASE EVIDENCE</small></span><span className="pl-document-folio">018</span></div>
    <div className="pl-document-title"><span lang="hi">भुगतान विवरण</span><h3>Payment acknowledgement</h3><p>{inspected ? "SOURCE CONTEXT / ADDITIONAL DETAIL" : "A closer look starts with the original."}</p></div>
    <dl className="pl-document-fields">{[
      { label: "Record reference", value: "DEMO-TRX-018", context: "Sample source: bank-export.csv · row 18", kind: "reference" },
      { label: "Recorded time", value: "12 Oct 2026 · 10:18 IST", context: "UTC 04:48 · original offset +05:30", kind: "time" },
      { label: "Transfer amount", value: "₹25,000.00", context: "Amount in document · bank match not established", kind: "amount" },
      { label: "Review status", value: "Awaiting corroboration", context: "A claim in a document is not a verified payment", kind: "status" },
    ].map(({ label, value, context, kind }) => <div key={kind} className={`pl-document-field pl-document-field-${kind}`}><dt>{label}</dt><dd>{value}</dd><span className={inspected ? "pl-field-context is-revealed" : "pl-field-context"}>{inspected && <ScanLine/>}{inspected ? context : "Additional context beneath the lens"}</span></div>)}</dl>
    <div className="pl-document-signature"><span>Sample signature</span><svg viewBox="0 0 160 50" aria-hidden="true"><path d="M7 36 C25 2 23 48 39 26 S51 6 51 27 S68 36 78 18 S75 38 96 26 S118 30 147 13"/></svg></div>
    <div className="pl-document-stamp">SAMPLE<br/><span>{inspected ? "SOURCE CONTEXT" : "REVIEW COPY"}</span></div>
    <div className="pl-document-foot"><ScanLine/>{inspected ? "Illustrative annotations · No live analysis performed" : "Original wording visible. More context under the lens."}</div>
  </>;
  return <div className="pl-hero-art pl-lens-art"><div className="pl-inspection-backdrop" aria-hidden="true"/><div ref={surface} className="pl-inspection" role="group" tabIndex={0} aria-label="Interactive document magnifier" aria-describedby="pl-lens-instructions" onPointerMove={event => {
    if (event.pointerType !== "mouse" && event.buttons === 0) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    move((event.clientX - bounds.left) / bounds.width * 100, (event.clientY - bounds.top) / bounds.height * 100);
  }} onPointerDown={event => {
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.focus({ preventScroll: true });
    const bounds = event.currentTarget.getBoundingClientRect();
    move((event.clientX - bounds.left) / bounds.width * 100, (event.clientY - bounds.top) / bounds.height * 100);
  }} onKeyDown={event => {
    const directions: Record<string, [number, number]> = { ArrowLeft: [-4, 0], ArrowRight: [4, 0], ArrowUp: [0, -4], ArrowDown: [0, 4] };
    if (event.key === "Home") { event.preventDefault(); move(62, 44); }
    else if (directions[event.key]) { event.preventDefault(); const [dx, dy] = directions[event.key]; move(position.current.x + dx, position.current.y + dy); }
  }}>
    <div className="pl-document pl-document-original">{documentContents(false)}</div>
    <div className="pl-document-reveal" aria-hidden="true"><div className="pl-document pl-document-inspected">{documentContents(true)}</div></div>
    <div className="pl-magnifier" aria-hidden="true"><span className="pl-lens-crosshair"/><span className="pl-lens-rim">MORE CONTEXT</span></div>
    <span className="pl-inspection-label">SYNTHETIC DOCUMENT / INTERACTIVE PREVIEW</span>
  </div><p className="pl-lens-instructions" id="pl-lens-instructions"><Search/><span>The record stays visible. The lens reveals more.<small>Hover over a field · Drag on touch · Arrow keys to explore</small></span></p></div>;
}
const editorialImages = [
  { image: "photo-1516321318423-f06f85e504b3", title: "A place for careful collaboration.", caption: "REVIEW TOGETHER", alt: "People working together with laptops and notes at a table", fallback: "evidence-review.jpg" },
  { image: "photo-1499750310107-5fef28a66643", title: "Keep the working picture connected.", caption: "FIND THE CONTEXT", alt: "A working desk with a notebook and laptop", fallback: "research-library.jpg" },
  { image: "photo-1450101499163-c8848c66ca85", title: "Explain the account behind the records.", caption: "DOCUMENT THE REASONING", alt: "Professionals reviewing paperwork and written records", fallback: "evidence-review.jpg" },
];
function EditorialPhoto({ image, alt, fallback, className }: { image: string; alt: string; fallback: string; className?: string }) {
  const [failed, setFailed] = React.useState(false);
  return <img className={className} src={failed ? `./images/${fallback}` : `https://images.unsplash.com/${image}?auto=format&fit=crop&w=1100&q=85`} alt={failed ? "Editorial photograph of research and document review" : alt} loading="lazy" width="1100" height="740" referrerPolicy="no-referrer" onError={() => { if (!failed) setFailed(true); }}/>
}
function Landing() {
  const [active, setActive] = React.useState(0);
  const [node, setNode] = React.useState(0);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const preview = previews[active];
  return <div className="pl-page">
    <a className="pl-skip" href="#main">Skip to content</a>
    <header className="pl-header">
      <a className="pl-brand" href="./index.html" aria-label="Parakh home"><BrandMark size={38}/><span>PARAKH<small>DIGITAL EVIDENCE INTELLIGENCE</small></span></a>
      <button className="pl-menu" aria-expanded={menuOpen} aria-controls="landing-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? "Close" : "Menu"}</button>
      <nav id="landing-navigation" className={menuOpen ? "pl-nav is-open" : "pl-nav"} aria-label="Main navigation" onClick={() => setMenuOpen(false)}><a href="#capabilities">Capabilities</a><a href="#workflow">How it works</a><a href="#workspace">The workspace</a><a href="#principles">Our approach</a></nav>
      <a className="pl-header-cta" href="./signin.html">Investigator sign-in <ArrowUpRight/></a>
    </header>
    <main id="main">
      <section className="pl-hero pl-container" aria-labelledby="hero-title">
        <div className="pl-hero-copy"><span className="pl-eyebrow"><span/> CLARITY THROUGH EVIDENCE</span><div className="pl-hindi" lang="hi">परख<span>हर डिजिटल सुराग, सही संदर्भ में।</span></div><h1 id="hero-title">Every trace.<br/>A clearer <em>picture.</em></h1><p>Scattered records. Connected context. A focused workspace to examine digital evidence and explain the story it supports.</p><div className="pl-actions"><a className="pl-button" href="./signin.html">Open investigator workspace <ArrowRight/></a><a className="pl-link" href="./dashboard.html?mode=demo">Explore the demo <ArrowUpRight/></a></div><div className="pl-hero-note"><ShieldCheck/><span>Evidence first. Uncertainty visible. Sources within reach.</span></div></div>
        <EvidenceLens/>
      </section>
      <section className="pl-source-band" aria-label="Evidence sources"><div className="pl-container"><span className="pl-band-intro">MANY SOURCES.<br/><strong>ONE WORKSPACE.</strong></span>{[{Icon:MessageSquare,label:"Chats & emails"},{Icon:FileCheck2,label:"Bank records"},{Icon:Files,label:"PDFs & images"},{Icon:Globe2,label:"Browser history"},{Icon:MapPin,label:"Location & calls"}].map(({Icon,label})=><span key={label}><Icon/>{label}</span>)}</div></section>
      <section className="pl-capabilities pl-container pl-section" id="capabilities"><div className="pl-section-heading"><div><span className="pl-eyebrow">PURPOSE-BUILT FOR INVESTIGATION</span><h2>Less scattered evidence.<br/>More informed decisions.</h2></div><p>Move from individual records to a connected account, with the supporting evidence close at hand.</p></div><div className="pl-capability-grid">{capabilities.map(({Icon,title,hindi,text,detail,target},i)=><a className="pl-capability" href={target} key={title}><div className="pl-card-top"><span className="pl-icon"><Icon/></span><span className="pl-card-number">0{i+1}</span></div><span className="pl-card-hindi" lang="hi">{hindi}</span><h3>{title}</h3><p>{text}</p><span className="pl-card-link">{detail}<ArrowUpRight/></span></a>)}</div></section>
      <section className="pl-editorial-feature pl-container" aria-labelledby="editorial-heading"><div className="pl-editorial-feature-photo"><EditorialPhoto image="photo-1516321318423-f06f85e504b3" alt="People reviewing work together around laptops and notes" fallback="evidence-review.jpg"/><span>THE HUMAN SIDE OF DIGITAL INVESTIGATION</span></div><div className="pl-editorial-feature-copy"><span className="pl-eyebrow">BETTER CONTEXT. BETTER QUESTIONS.</span><h2 id="editorial-heading">Behind every record,<br/>a question worth asking.</h2><p>Give the investigator room to compare, challenge and connect. Parakh brings the records into one working space, while keeping judgement with the person reviewing them.</p><a className="pl-link" href="#workspace">See the workspace <ArrowRight/></a></div></section>
      <section className="pl-workflow" id="workflow"><div className="pl-container"><div className="pl-section-heading"><div><span className="pl-eyebrow">A CLEAR PATH THROUGH THE CASE</span><h2>Start with the source.<br/>Finish with a supported account.</h2></div><a className="pl-link" href="./signin.html">Start an investigation <ArrowRight/></a></div><ol className="pl-steps">{[["Upload & seal","Create a case. Add the owner and acquisition context, upload your evidence, then review the import report."],["Explore & connect","Search the records, follow the money and connect sources on the graph or investigation board."],["Test & reconstruct","Compare conflicting records, examine document signals and review the sequence with clock uncertainty."],["Review & explain","Record findings with their status and citations. Assemble exhibits and export a reviewable account."]].map(([title,text],i)=><li key={title}><span className="pl-step-number">0{i+1}<ChevronRight/></span><h3>{title}</h3><p>{text}</p></li>)}</ol></div></section>
      <section className="pl-container pl-section pl-workspace" id="workspace"><div className="pl-section-heading"><div><span className="pl-eyebrow">ONE CASE. MULTIPLE PERSPECTIVES.</span><h2>See the context.<br/>Inspect the detail.</h2></div><p>A workspace that keeps exploration and the original source in the same conversation.</p></div><div className="pl-preview-tabs" role="tablist" aria-label="Workspace previews">{previews.map(({label,Icon},i)=><button key={label} id={`pl-tab-${i}`} aria-selected={active===i} role="tab" aria-controls="pl-preview" tabIndex={active===i?0:-1} onClick={()=>setActive(i)} onKeyDown={e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'||e.key==='Home'||e.key==='End'){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?previews.length-1:(i+(e.key==='ArrowRight'?1:-1)+previews.length)%previews.length;setActive(next);document.getElementById(`pl-tab-${next}`)?.focus();}}}><Icon/>{label}<ArrowUpRight/></button>)}</div><div className="pl-preview" role="tabpanel" id="pl-preview" aria-labelledby={`pl-tab-${active}`}><div className="pl-preview-copy"><span className="pl-eyebrow">0{active+1} / WORKSPACE VIEW</span><h3>{preview.title}</h3><p>{preview.body}</p><a className="pl-link" href="./dashboard.html?mode=demo">Open the interactive demo <ArrowRight/></a><small>{preview.note}</small></div><div className="pl-preview-visual">{preview.image ? <img src={`./images/${preview.image}`} alt={preview.alt} loading="lazy" width="1200" height="800"/> : <div className="pl-graph"><div className="pl-graph-canvas"><svg viewBox="0 0 500 320" aria-hidden="true">{[[95,80],[405,80],[95,240],[405,240]].map(([x,y],i)=><path key={i} d={`M250 160 Q${x} 160 ${x} ${y}`} className={node===i+1||node===0?'pl-edge-selected':''}/>)}</svg>{[{label:'Case',Icon:FolderInput,x:50,y:50},{label:'Messages',Icon:MessageSquare,x:19,y:25},{label:'Transactions',Icon:FileCheck2,x:81,y:25},{label:'Call records',Icon:Network,x:19,y:75},{label:'Locations',Icon:MapPin,x:81,y:75}].map(({label,Icon,x,y},i)=><button key={label} aria-pressed={node===i} className={node===i?'is-selected':''} style={{left:`${x}%`,top:`${y}%`}} onClick={()=>setNode(i)}><Icon/><span>{label}</span></button>)}</div><p aria-live="polite">{connectionDetails[node]}</p></div>}</div></div><div className="pl-workspace-footnote"><ShieldCheck/><span>Demo mode uses clearly labelled synthetic data. No sign-in required.</span><a href="./dashboard.html?mode=demo">View demo <ArrowRight/></a></div></section>
      <section className="pl-photo-stories pl-container" aria-labelledby="photo-stories-heading"><div className="pl-section-heading"><div><span className="pl-eyebrow">BUILT AROUND THE WAY YOU WORK</span><h2 id="photo-stories-heading">Space to think.<br/>Tools to follow through.</h2></div><p>From a first review to a supported account, keep the detail and the wider picture together.</p></div><div className="pl-photo-story-grid">{editorialImages.map(({ image, title, caption, alt, fallback }, i) => <article key={image} className="pl-photo-story"><div><EditorialPhoto image={image} alt={alt} fallback={fallback}/><span>0{i+1}</span></div><p>{caption}</p><h3>{title}</h3></article>)}</div><small className="pl-editorial-note">Editorial stock photographs · Illustrations of review and research, not case evidence or endorsements. <a href="./image-credits.html">Photo sources</a></small></section>
      <section className="pl-principles pl-container" id="principles"><div className="pl-principles-photo"><img src="./images/research-library.jpg" width="1000" height="665" loading="lazy" alt="Reference books arranged for study and careful research"/><span><Fingerprint/> CAREFUL EXAMINATION. CLEAR LIMITS.</span></div><div className="pl-principles-copy"><span className="pl-eyebrow">DESIGNED TO BE QUESTIONED</span><h2>Confidence comes<br/>from showing your work.</h2><p>Useful evidence tools should make it easier to ask difficult questions, including questions about their own conclusions.</p><ul><li><Check/><div><strong>Every claim needs a receipt.</strong><span>Follow a supported finding to its source. Missing support means “not established”.</span></div></li><li><Check/><div><strong>Leads stay separate from findings.</strong><span>Review reasons, caveats and uncertainty before drawing a conclusion.</span></div></li><li><Check/><div><strong>Integrity has a precise meaning.</strong><span>A matching hash shows a file is unchanged since sealing. It does not prove it was truthful.</span></div></li></ul></div></section>
      <section className="pl-container pl-section" id="start"><div className="pl-final"><div className="pl-final-emblem" aria-hidden="true"><Fingerprint/></div><span className="pl-eyebrow">THE NEXT STEP STARTS WITH YOUR EVIDENCE</span><h2>Bring clarity to<br/>your next investigation.</h2><p>Open the investigator workspace, or explore a synthetic case<br className="pl-desktop-break"/> before bringing in your own source files.</p><div className="pl-actions"><a className="pl-button pl-button-light" href="./signin.html">Open investigator workspace <ArrowRight/></a><a className="pl-link" href="./dashboard.html?mode=demo">View demo without signing in <ArrowUpRight/></a></div><span className="pl-final-note"><ShieldCheck/> Self-hosted prototype · Synthetic demo available</span></div></section>
    </main><footer className="pl-footer pl-container"><div><a className="pl-brand" href="./index.html"><BrandMark size={32}/><span>PARAKH<small>EXAMINE. CONNECT. SUBSTANTIATE.</small></span></a><p>Digital evidence. A clearer perspective.</p></div><div className="pl-footer-links"><a href="#capabilities">Capabilities</a><a href="#workflow">How it works</a><a href="./signin.html">Investigator sign-in</a><a href="./image-credits.html">Photo credits</a></div><span className="pl-footer-note"><GitBranch/> Investigation prototype<br/><Sparkles/> Built for thoughtful review</span></footer>
  </div>;
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><Landing/></React.StrictMode>);
