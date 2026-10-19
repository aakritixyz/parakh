import { useEffect, useState } from "react";
import { sessionRequest } from "../../caseApi";
import type { Citation, RecordEvent, Source } from "./model";
import styles from "./Casework.module.css";

type Receipt = { evidence_id: number; event_id?: number; reference: string; file?: string; sha256?: string; timestamp?: string | null };
type Finding = { id: string; statement: string; status: string; citations: Receipt[]; notes: string; tags: string[]; comments: string[]; review_state: string };
type Exhibit = { id: string; kind: "event" | "document" | "finding"; evidence_id?: number; event_id?: number; finding_id?: string; reference: string; pages: number };
type Review = { revision: number; findings: Finding[]; exhibits: Exhibit[] };
const empty: Review = { revision: 0, findings: [], exhibits: [] };
const requestBody = (value: unknown) => ({ headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) });

export async function downloadCasePdf(caseId: number) {
  // Obtain the PDF through the same rotating-session transport as other case requests.
  const result = await sessionRequest<{ pdf_base64: string }>(`/api/v2/cases/${caseId}/report-data`, { method: "POST" });
  const bytes = Uint8Array.from(atob(result.pdf_base64), (char) => char.charCodeAt(0));
  const href = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const anchor = document.createElement("a"); anchor.href = href; anchor.download = `parakh-case-${caseId}.pdf`; anchor.click();
  URL.revokeObjectURL(href);
}

export function ReviewPanel({ caseId, readOnly, mode, sources, records, onOpen }: {
  caseId: number; readOnly: boolean; mode: "Findings" | "Reports" | "tray"; sources: Source[]; records: RecordEvent[]; onOpen: (citation: Citation) => void;
}) {
  const [review, setReview] = useState<Review>(empty);
  const [message, setMessage] = useState("");
  const [statement, setStatement] = useState("");
  const [selected, setSelected] = useState("");
  const [pages, setPages] = useState(10);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    sessionRequest<Review>(`/api/v2/cases/${caseId}/review`).then((value) => { if (active) setReview(value); }).catch((error: Error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, [caseId]);
  useEffect(() => {
    const receive = (event: Event) => {
      if (readOnly) return;
      const value = (event as CustomEvent<{ file: number; ref?: string; event_id?: number }>).detail;
      const exhibit: Exhibit = { id: `source-${value.file}-${value.event_id ?? value.ref ?? "document"}`, kind: value.event_id ? "event" : "document", evidence_id: value.file, event_id: value.event_id, reference: value.ref ?? "", pages: 1 };
      setReview((current) => ({ ...current, exhibits: current.exhibits.some((item) => item.id === exhibit.id) ? current.exhibits : [...current.exhibits, exhibit] }));
      setMessage("Source added. Save the tray before navigating away.");
    };
    window.addEventListener("parakh-exhibit", receive);
    return () => window.removeEventListener("parakh-exhibit", receive);
  }, [readOnly]);
  const save = async () => {
    setBusy(true);
    try {
      const value = await sessionRequest<Review>(`/api/v2/cases/${caseId}/review`, { method: "PUT", ...requestBody(review) });
      setReview(value); setMessage("Review saved with source receipts in the audit log.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Save failed"); }
    finally { setBusy(false); }
  };
  const addExhibit = (value: Exhibit) => setReview((current) => ({ ...current, exhibits: current.exhibits.some((e) => e.id === value.id) ? current.exhibits : [...current.exhibits, value] }));
  const updateFinding = (id: string, value: Partial<Finding>) => setReview((current) => ({ ...current, findings: current.findings.map((finding) => finding.id === id ? { ...finding, ...value } : finding) }));
  return <section className={styles.panel} aria-label="Saved case review">
    <h2>{mode === "Findings" ? "Findings and review" : "Case exhibit tray"}</h2>
    <p className={styles.note}>Drag a source chip, record or finding into the tray. Save before exporting. Status is an investigator assessment; citations establish traceability.</p>
    <div className={styles.exhibitDrop} role="region" aria-label="Drop exhibits here" onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
      event.preventDefault(); if (readOnly) return;
      try {
        const value = JSON.parse(event.dataTransfer.getData("application/parakh-source"));
        if (value.finding_id) addExhibit({ id: `finding-${value.finding_id}`, kind: "finding", finding_id: value.finding_id, reference: "", pages: 1 });
        else addExhibit({ id: `source-${value.file}-${value.event_id ?? value.ref ?? "document"}`, kind: value.event_id ? "event" : "document", evidence_id: value.file, event_id: value.event_id, reference: value.ref ?? "", pages: 1 });
      } catch { setMessage("Drop a PARAKH source or finding."); }
    }}>
      <strong>Drop exhibits here</strong>
      {review.exhibits.map((exhibit) => <div className={styles.sourceExhibit} key={exhibit.id}>
        <button onClick={() => exhibit.evidence_id && onOpen({ file: exhibit.evidence_id, ref: exhibit.reference })}>{exhibit.kind} · {exhibit.finding_id ?? sources.find((s) => s.id === exhibit.evidence_id)?.file ?? exhibit.evidence_id} · {exhibit.reference}</button>
        <label>Pages <input aria-label={`Pages for ${exhibit.id}`} type="number" min={1} max={100} value={exhibit.pages} disabled={readOnly} onChange={(event) => setReview({ ...review, exhibits: review.exhibits.map((e) => e.id === exhibit.id ? { ...e, pages: Math.max(1, Number(event.target.value)) } : e) })} /></label>
        <button disabled={readOnly} onClick={() => setReview({ ...review, exhibits: review.exhibits.filter((e) => e.id !== exhibit.id) })}>Remove</button>
      </div>)}
    </div>
    {mode === "Findings" && <>
      <form onSubmit={(event) => {
        event.preventDefault();
        const record = records.find((r) => r.id === selected);
        const citation = record ? { evidence_id: record.evidence_id, event_id: Number(record.id), reference: record.raw_ref } : null;
        setReview({ ...review, findings: [...review.findings, { id: crypto.randomUUID(), statement, status: citation ? "possible" : "not established", citations: citation ? [citation] : [], notes: "", tags: [], comments: [], review_state: "draft" }] }); setStatement("");
      }}>
        <label>Finding statement<textarea required maxLength={4000} disabled={readOnly} value={statement} onChange={(event) => setStatement(event.target.value)} /></label>
        <label>Supporting record<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">No support: not established</option>{records.map((record) => <option value={record.id} key={record.id}>{record.file} · {record.raw_ref} · {record.content.slice(0, 75)}</option>)}</select></label>
        <button disabled={readOnly}>Add finding</button>
      </form>
      {review.findings.map((finding) => <article className={styles.signal} key={finding.id} draggable onDragStart={(event) => event.dataTransfer.setData("application/parakh-source", JSON.stringify({ finding_id: finding.id }))}>
        <strong>{finding.statement}</strong>
        <div className={styles.findingActions}>
          <label>Status<select disabled={readOnly} value={finding.status} onChange={(event) => updateFinding(finding.id, { status: event.target.value })}>{["established", "possible", "not established", "contradicted"].map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Review state<select disabled={readOnly} value={finding.review_state} onChange={(event) => updateFinding(finding.id, { review_state: event.target.value })}>{["draft", "reviewing", "reviewed"].map((value) => <option key={value}>{value}</option>)}</select></label>
          <button disabled={readOnly || !selected} onClick={() => {
            const record = records.find((item) => item.id === selected);
            if (record && !finding.citations.some((citation) => citation.event_id === Number(record.id))) updateFinding(finding.id, { citations: [...finding.citations, { evidence_id: record.evidence_id, event_id: Number(record.id), reference: record.raw_ref }] });
          }}>Link selected record</button>
          <button disabled={readOnly} onClick={() => addExhibit({ id: `finding-${finding.id}`, kind: "finding", finding_id: finding.id, reference: "", pages: 1 })}>Add to tray</button>
        </div>
        <label>Notes<textarea disabled={readOnly} value={finding.notes} onChange={(event) => updateFinding(finding.id, { notes: event.target.value })} /></label>
        <label>Tags (comma separated)<input disabled={readOnly} value={finding.tags.join(",")} onChange={(event) => updateFinding(finding.id, { tags: event.target.value.split(",") })} /></label>
        {finding.citations.map((citation) => <button className={styles.citation} key={`${citation.evidence_id}-${citation.reference}`} onClick={() => onOpen({ file: citation.evidence_id, ref: citation.reference })}>{citation.file ?? citation.evidence_id} · {citation.reference}</button>)}
        {finding.comments.map((comment, index) => <p key={index}>{comment}</p>)}
        <button disabled={readOnly} onClick={() => { const comment = window.prompt("Review comment"); if (comment) updateFinding(finding.id, { comments: [...finding.comments, comment] }); }}>Add comment</button>
      </article>)}
    </>}
    <div className={styles.toolbar}>
      <button disabled={readOnly || busy} onClick={() => void save()}>Save findings and tray</button>
      {mode === "Reports" && <>
        <label>Page budget<input aria-label="Exhibit page budget" type="number" min={1} max={500} value={pages} onChange={(event) => setPages(Number(event.target.value))} /></label>
        <button onClick={async () => { try { const result = await sessionRequest<{ selected_ids: string[]; status: string; complete: boolean; fallback: string }>(`/api/v2/cases/${caseId}/review/select-exhibits?page_limit=${pages}`, { method: "POST" }); setMessage(`${result.status}: ${result.selected_ids.join(", ") || "No feasible selection"}. ${result.complete ? "Optimal selection." : result.fallback}`); } catch (error) { setMessage(String(error)); } }}>Suggest minimum exhibits</button>
        <button onClick={() => void downloadCasePdf(caseId).catch((error) => setMessage(String(error)))}>Download cited report PDF</button>
      </>}
    </div>
    {message && <p role="status" className={styles.notice}>{message}</p>}
  </section>;
}
