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
import styles from "./components/entry/Entry.module.css";

const features = [
  {
    Icon: Files,
    number: "01",
    title: "Upload all your evidence",
    body: "Start a case by uploading chats, statements, documents and location exports.",
    tab: "Gallery",
  },
  {
    Icon: Network,
    number: "02",
    title: "Follow the connections",
    body: "Explore events, people and payment references without losing sight of the source.",
    tab: "Graph",
  },
  {
    Icon: Search,
    number: "03",
    title: "Make the story reviewable",
    body: "Compare records and examine the evidence behind an investigation lead.",
    tab: "Timeline",
  },
];
function Landing() {
  return (
    <div className={styles.entry}>
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
              <a className={styles.textLink} href="#workflow">
                See the workflow <ChevronRight />
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
        <section className={styles.section} id="workspace">
          <div className={styles.sectionHeading}>
            <div>
              <span className={styles.eyebrow}>
                Built around the investigator
              </span>
              <h2>Less switching. More understanding.</h2>
            </div>
            <p>
              A familiar workspace for moving from individual records to the
              bigger picture.
            </p>
          </div>
          <div className={styles.featureGrid}>
            {features.map(({ Icon, number, title, body, tab }) => (
              <a
                className={styles.featureCard}
                key={number}
                href={"./signin.html?tab=" + encodeURIComponent(tab)}
              >
                <div className={styles.cardTop}>
                  <Icon />
                  <span>{number}</span>
                </div>
                <h3>{title}</h3>
                <p>{body}</p>
                <span className={styles.featureLink}>
                  Explore workspace <ArrowRight />
                </span>
              </a>
            ))}
          </div>
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
                You’ll be able to choose demo mode on the next page.
              </small>
            </div>
            <div
              className={styles.casePreview}
              aria-label="Illustrative case preview"
            >
              <div className={styles.previewHeader}>
                <FolderOpen />
                <strong>New investigation / Evidence intake</strong>
                <span>Preview</span>
              </div>
              <div className={styles.previewTabs}>
                <span>Timeline</span>
                <span>Graph</span>
                <span>Evidence</span>
              </div>
              <div className={styles.previewRow}>
                <span className={styles.rowIcon}>
                  <MessageSquare />
                </span>
                <div>
                  <strong>1. Upload source files</strong>
                  <small>WhatsApp export</small>
                </div>
                <ChevronRight />
              </div>
              <div className={styles.previewRow}>
                <span className={styles.rowIcon}>
                  <Files />
                </span>
                <div>
                  <strong>2. Review your evidence list</strong>
                  <small>Bank statement</small>
                </div>
                <ChevronRight />
              </div>
              <div className={styles.previewRow}>
                <span className={styles.rowIcon}>
                  <Search />
                </span>
                <div>
                  <strong>3. Explore the analysis</strong>
                  <small>Timeline, graph and source records</small>
                </div>
                <ChevronRight />
              </div>
              <p className={styles.previewFoot}>
                Upload → Review evidence → Investigate
              </p>
            </div>
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
