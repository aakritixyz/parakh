import React from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  Files,
  Network,
  Search,
  ShieldCheck,
  MessageSquare,
  MapPin,
  ChevronRight,
  Fingerprint,
  FolderOpen,
} from "lucide-react";
import "./styles.css";
import "./landing-refined.css";
import styles from "./components/entry/Entry.module.css";

const showcaseViews = [
  { title: "Evidence", image: "evidence-preview.jpg", heading: "Keep the source within reach.", body: "Review evidence details alongside the records you are examining." },
  { title: "Timeline", image: "timeline-preview.jpg", heading: "See how the story unfolds.", body: "Explore records in time and compare events across your sources." },
  { title: "Graph", image: "graph-preview.jpg", heading: "Follow the connections.", body: "Explore relationships and return to the evidence behind each lead." },
];
const storyEvents = [
  { time: "10:12", kind: "Message", title: "A conversation begins", text: "“Please share the payment reference once the transfer is complete.”", source: "Sample chat export · Message 04", context: "A payment request appears in a conversation. It is a starting point for review, not proof of a completed transfer.", Icon: MessageSquare },
  { time: "10:18", kind: "Transaction", title: "A payment is recorded", text: "Transfer recorded · ₹12,500 · Reference DEMO-018", source: "Sample bank statement · Row 12", context: "The statement records a transfer six minutes later. Matching time alone does not establish who requested or received it.", Icon: Files },
  { time: "10:24", kind: "Location", title: "Location adds context", text: "Location record · Sample point A · 10:24 IST", source: "Sample location export · Record 08", context: "A nearby location record provides another point of context. It does not independently confirm a person’s presence.", Icon: MapPin },
];
function Landing() {
  const [activeView, setActiveView] = React.useState(2);
  const [activeEvent, setActiveEvent] = React.useState(0);
  const [selectedNode, setSelectedNode] = React.useState(0);
  const view = showcaseViews[activeView];
  return (
    <div className={`${styles.entry} landing-refined`}>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <a className={styles.brand} href="./index.html">
          <span className={styles.mark}>P</span>Parakh
          <span className={styles.brandMeta}>Digital investigations</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#workspace">The workspace</a>
          <a href="#workflow">How it works</a>
          <a href="#start">Get started</a>
        </nav>
        <a className={styles.headerAction} href="./signin.html">
          Investigator workspace <ArrowRight />
        </a>
      </header>
      <main id="main">
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <span className={styles.eyebrow}>
              <span className={styles.statusDot} /> One workspace. A clearer
              picture.
            </span>
            <h1>
              Every piece of evidence.
              <br />
              One connected story.
            </h1>
            <p className={styles.lead}>
              Bring scattered digital records into focus. Explore the timeline,
              follow the connections, and keep the original evidence within
              reach.
            </p>
            <div className={styles.actions}>
              <a className={styles.primary} href="./signin.html">
                Investigator workspace <ArrowRight />
              </a>
              <a className={styles.textLink} href="./dashboard.html?mode=demo">
                Try the demo <ArrowRight />
              </a>
            </div>
            <p className={styles.heroNote}>
              <ShieldCheck /> Self-hosted prototype <span>·</span> Offline demo
              available
            </p>
          </div>
          <figure className={styles.heroVisual}>
            <img
              src="./images/evidence-review.jpg"
              width="1600"
              height="1068"
              alt="Professionals reviewing documents together at a desk with laptops"
              fetchPriority="high"
            />
            <figcaption className={styles.photoLabel}>
              A focused space for careful investigation.
            </figcaption>
            <div className={styles.caseOverlay}>
              <span className={styles.caseIcon}>
                <FolderOpen />
              </span>
              <div>
                <span className={styles.smallLabel}>
                  Start an investigation
                </span>
                <strong>Upload your evidence</strong>
                <span>Bring your source files into one case</span>
              </div>
              <span className={styles.demoBadge}>Evidence first</span>
            </div>
          </figure>
        </section>
        <div className={styles.sourceStrip}>
          <span className={styles.stripLabel}>
            Different sources. Shared context.
          </span>
          <span>
            <MessageSquare /> Chats & emails
          </span>
          <span>
            <Files /> Statements & documents
          </span>
          <span>
            <MapPin /> Location & call records
          </span>
          <span>
            <Fingerprint /> File integrity
          </span>
        </div>
        <section id="workspace" className="interactive-showcase" aria-labelledby="showcase-heading">
          <div className="showcase-intro"><div><span className={styles.eyebrow}>A closer look</span><h2 id="showcase-heading">One case. Different perspectives.</h2></div><p>Explore the tools that bring your investigation into focus.</p></div>
          <div className="showcase-tabs" role="tablist" aria-label="Workspace previews">{showcaseViews.map((item, index) => <button key={item.title} id={`preview-tab-${index}`} role="tab" aria-selected={activeView === index} aria-controls="workspace-preview-panel" tabIndex={activeView === index ? 0 : -1} onClick={() => setActiveView(index)} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + showcaseViews.length) % showcaseViews.length; setActiveView(next); document.getElementById(`preview-tab-${next}`)?.focus(); } }}>{index === 0 ? <Files /> : index === 1 ? <ChevronRight /> : <Network />}{item.title}</button>)}</div>
          <div className="showcase-panel" role="tabpanel" id="workspace-preview-panel" aria-labelledby={`preview-tab-${activeView}`}><div className="showcase-copy"><span className="showcase-number">0{activeView + 1} / WORKSPACE</span><h3>{view.heading}</h3><p>{view.body}</p><a href="./dashboard.html?mode=demo">Try the interactive demo <ArrowRight /></a><small>Illustrative graph and project interface previews.<br />Demo opens the current sample case list.</small></div><div className="showcase-image">{activeView === 2 ? <div className="live-graph"><span className="graph-label">ILLUSTRATIVE CONNECTION MAP · SYNTHETIC</span><div className="graph-canvas"><svg viewBox="0 0 500 340" aria-hidden="true">{[[250,60],[85,175],[415,175],[250,290]].map(([x,y],i)=><line key={i} x1="250" y1="175" x2={x} y2={y} className={selectedNode === 0 || selectedNode === i+1 ? 'edge-active' : ''}/>)}</svg>{[{name:'Sample case',x:50,y:51,detail:'Select a source to explore its connection to this illustrative case.'},{name:'Person A',x:50,y:18,detail:'Person A appears in the sample chat export. Identity requires independent review.'},{name:'Messages',x:17,y:51,detail:'A sample conversation contains a payment request. Review the original wording and timestamp.'},{name:'Transfer',x:83,y:51,detail:'A sample statement records a ₹12,500 transfer. Timing alone does not prove a relationship.'},{name:'Location',x:50,y:85,detail:'A sample location record provides context, not independent proof of presence.'}].map((node,i)=><button key={node.name} style={{left:`${node.x}%`,top:`${node.y}%`}} className={`graph-node ${selectedNode===i?'node-selected':''}`} aria-pressed={selectedNode===i} onClick={()=>setSelectedNode(i)}>{i===0?<FolderOpen/>:i===1?<Search/>:i===2?<MessageSquare/>:i===3?<Files/>:<MapPin/>}<span>{node.name}</span></button>)}</div><p className="graph-receipt" aria-live="polite">{['Select a source to explore its connection to this illustrative case.','Person A appears in the sample chat export. Identity requires independent review.','A sample conversation contains a payment request. Review the original wording and timestamp.','A sample statement records a ₹12,500 transfer. Timing alone does not prove a relationship.','A sample location record provides context, not independent proof of presence.'][selectedNode]}</p></div> : <img src={`./images/${view.image}`} alt={`${view.title} interface preview from Parakh`} loading="lazy" />}</div></div>
        </section>
        <section className="story-timeline" aria-labelledby="story-heading">
          <div className="story-heading"><div><span className={styles.eyebrow}>Follow the sequence</span><h2 id="story-heading">A moment. More context.</h2><p>Select an event to see how different sources add to the picture.</p></div><span className="synthetic-label">Illustrative example · Synthetic records</span></div>
          <div className="story-track" role="tablist" aria-label="Sample investigation events">{storyEvents.map(({time, kind, Icon}, index) => <button key={time} role="tab" id={`story-tab-${index}`} aria-selected={activeEvent === index} aria-controls="story-panel" tabIndex={activeEvent === index ? 0 : -1} onClick={() => setActiveEvent(index)} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + storyEvents.length) % storyEvents.length; setActiveEvent(next); document.getElementById(`story-tab-${next}`)?.focus(); } }}><span className="event-time">{time} <small>IST</small></span><span className="event-dot"><Icon /></span><span>{kind}</span></button>)}</div>
          <div className="story-detail" id="story-panel" role="tabpanel" aria-labelledby={`story-tab-${activeEvent}`}><div><span className="story-label">SOURCE EXCERPT</span><h3>{storyEvents[activeEvent].title}</h3><blockquote>{storyEvents[activeEvent].text}</blockquote><small>{storyEvents[activeEvent].source}</small></div><div><span className="story-label">INVESTIGATOR CONTEXT</span><p>{storyEvents[activeEvent].context}</p><span className="context-note"><ShieldCheck /> Keep the source. Check the connection.</span></div></div>
        </section>
        <section className={styles.workflow} id="workflow">
          <div className={styles.workflowPhoto}>
            <img
              src="./images/research-library.jpg"
              width="1000"
              height="665"
              loading="lazy"
              alt="A stack of reference books, illustrating careful research and review"
            />
            <span>Context matters. Sources matter.</span>
          </div>
          <div className={styles.workflowBody}>
            <span className={styles.eyebrow}>From records to review</span>
            <h2>A clear path through the evidence.</h2>
            <ol>
              {[
                [
                  "Upload evidence",
                  "Create a case and upload all the evidence files before starting your review.",
                ],
                [
                  "Examine",
                  "Review records by time, source and relationship. Compare what each source says.",
                ],
                [
                  "Explain",
                  "Build a source-linked account, keeping assumptions and gaps visible.",
                ],
              ].map(([title, body], i) => (
                <li key={title}>
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>
        <section className={styles.section} id="start">
          <div className={styles.demoPanel}>
            <div>
              <span className={styles.demoBadge}>Start your investigation</span>
              <h2>Your investigation starts with the evidence.</h2>
              <p>
                Upload the source files for your case, review the evidence list,
                then explore timelines, connections and source-linked findings.
              </p>
              <a className={styles.secondary} href="./signin.html">
                Open investigator workspace <ArrowRight />
              </a>
              <small>
                Or explore the synthetic demo without signing in.
              </small>
            </div>
            <a className="final-demo" href="./dashboard.html?mode=demo">Explore the demo <ArrowRight /></a>
          </div>
        </section>
      </main>
      <footer className={styles.footer}>
        <a className={styles.brand} href="./index.html">
          <span className={styles.mark}>P</span>Parakh
        </a>
        <span>Digital evidence. Thoughtful investigation.</span>
        <div>
          <a href="./signin.html">Investigator sign-in</a>
          <a href="./image-credits.html">Photo credits</a>
          <span>Prototype</span>
        </div>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Landing />
  </React.StrictMode>,
);
