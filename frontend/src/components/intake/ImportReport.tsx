import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, FileText, ScanText } from "lucide-react";
import {
  confirmImportReport,
  getImportReport,
  reparseEvidence,
  type CaseInfo,
  type ImportReportData,
} from "../../caseApi";
import styles from "./Intake.module.css";

type Props = {
  caseInfo: CaseInfo;
  onBack: () => void;
  onContinue: () => Promise<void>;
};

export function ImportReport({ caseInfo, onBack, onContinue }: Props) {
  const [report, setReport] = useState<ImportReportData | null>(null);
  const [dateOrders, setDateOrders] = useState<Record<number, "day_first" | "month_first">>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setReport(await getImportReport(caseInfo.id));
  }
  useEffect(() => {
    void load().catch((cause) =>
      setError(cause instanceof Error ? cause.message : "Could not load the import report."),
    );
  }, [caseInfo.id]);

  async function fixAndReparse(evidenceId: number) {
    setBusy(true);
    setError("");
    try {
      await reparseEvidence(caseInfo.id, evidenceId, dateOrders[evidenceId] ?? "day_first");
      for (let attempt = 0; attempt < 80; attempt++) {
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        const next = await getImportReport(caseInfo.id);
        setReport(next);
        const file = next.files.find((item) => item.evidence_id === evidenceId);
        if (file && !["running", "queued"].includes(file.parse_status)) break;
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not re-parse the file.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      await confirmImportReport(caseInfo.id);
      await onContinue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not confirm the report.");
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="./index.html" className={styles.brand}><span>P</span>Parakh</a>
        <span>Investigator workspace</span><span className={styles.mode}>Signed in</span>
      </header>
      <main className={styles.main}>
        <button className={styles.back} onClick={onBack} disabled={busy}><ArrowLeft /> Back to evidence intake</button>
        <ol className={styles.steps} aria-label="Evidence intake workflow">
          <li><span>1</span>Acquisition context</li><li><span>2</span>Seal & process</li>
          <li aria-current="step"><span>3</span>Import report</li>
        </ol>
        <div className={styles.heading}>
          <div><p className={styles.eyebrow}>Import report · {caseInfo.title}</p><h1>Review what Parakh understood.</h1><p>Counts show normalized events. Decisions stay visible until an investigator confirms how the source should be interpreted.</p></div>
          <ScanText />
        </div>
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {!report ? <section className={styles.panel} role="status">Loading import report…</section> : <>
          <div className={styles.reportStats}>
            <div><strong>{report.files_imported}</strong><span>files imported</span></div>
            <div><strong>{report.total_events}</strong><span>normalized events</span></div>
            <div><strong>{report.decisions.length}</strong><span>decisions or warnings</span></div>
          </div>
          {report.decisions.length > 0 && <section className={styles.panel}>
            <h2 className={styles.sectionTitle}><AlertTriangle /> Decisions needed</h2>
            <div className={styles.decisionList}>
              {report.decisions.map((decision, index) => <article key={`${decision.evidence_id}-${decision.type}-${index}`}>
                <div><strong>{decision.filename}</strong><span>{decision.type.replaceAll("_", " ")}</span><p>{decision.message}</p>{decision.value && <code>{decision.value}</code>}</div>
                {decision.type === "ambiguous_date" && <div className={styles.decisionAction}>
                  <label>Date order<select value={dateOrders[decision.evidence_id] ?? "day_first"} onChange={(event) => setDateOrders((current) => ({ ...current, [decision.evidence_id]: event.target.value as "day_first" | "month_first" }))}><option value="day_first">DD/MM/YYYY</option><option value="month_first">MM/DD/YYYY</option></select></label>
                  <button disabled={busy} onClick={() => void fixAndReparse(decision.evidence_id)}>Fix and re-parse</button>
                </div>}
              </article>)}
            </div>
          </section>}
          <section className={styles.panel}>
            <h2 className={styles.sectionTitle}><FileText /> Files and event counts</h2>
            <div className={styles.reportTable} role="table">
              <div role="row" className={styles.reportHead}><span>File</span><span>Parser</span><span>Detection</span><span>Events</span><span>Status</span></div>
              {report.files.map((file) => <div role="row" key={file.evidence_id}>
                <span><strong>{file.filename}</strong>{file.document_extraction && Object.keys(file.document_extraction.fields).length > 0 && <small>Extracted: {Object.entries(file.document_extraction.fields).map(([name, field]) => `${name} ${field.value} (${Math.round(field.confidence * 100)}%)`).join(" · ")}</small>}</span>
                <span>{file.parser_name ?? "Pending"} {file.parser_version && `v${file.parser_version}`}</span>
                <span>{file.format_confidence === null ? "—" : `${Math.round(file.format_confidence * 100)}%`}</span>
                <span><strong>{file.event_count}</strong></span><span>{file.parse_status}</span>
              </div>)}
            </div>
          </section>
          <div className={styles.reportActions}><p><CheckCircle2 /> Confirming records the review in the hash-chained audit log.</p><button className={styles.primary} disabled={busy} onClick={() => void confirm()}>{busy ? "Working…" : "Confirm and continue"}<ArrowRight /></button></div>
        </>}
      </main>
    </div>
  );
}
