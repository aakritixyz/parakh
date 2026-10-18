import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileText,
  FolderOpen,
  LoaderCircle,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { createInvestigation, uploadCaseEvidence } from "../../api";
import { demoEvidence } from "./demoEvidence";
import styles from "./Intake.module.css";

type Entry = {
  id: string;
  name: string;
  size: number;
  file?: File;
  status: "selected" | "uploading" | "uploaded" | "failed";
  error?: string;
};
type Props = {
  token: string | null;
  onReview: (caseId: number | null, title: string) => Promise<void>;
  onBack: () => void;
};
const sizeLabel = (bytes: number) =>
  bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;

export function EvidenceIntake({ token, onReview, onBack }: Props) {
  const demo = !token;
  const [title, setTitle] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [sample, setSample] = useState(false);
  const caseId = useRef<number | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement | null>(null);
  const locked = busy || reviewing;
  const ready =
    entries.length > 0 && entries.every((e) => e.status === "uploaded");
  function addFiles(files: File[]) {
    if (locked || sample) return;
    setError("");
    setEntries((current) => {
      const keys = new Set(
        current.map((e) => `${e.name}:${e.size}:${e.file?.lastModified}`),
      );
      return [
        ...current,
        ...files
          .sort((a, b) => a.name.localeCompare(b.name))
          .filter((file) => {
            const key = `${file.name}:${file.size}:${file.lastModified}`;
            if (keys.has(key)) return false;
            keys.add(key);
            return true;
          })
          .map((file) => ({
            id: crypto.randomUUID(),
            name: file.name,
            size: file.size,
            file,
            status: "selected" as const,
          })),
      ];
    });
  }
  function choose(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }
  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    addFiles(Array.from(event.dataTransfer.files));
  }
  async function upload() {
    setBusy(true);
    setError("");
    try {
      if (!demo && caseId.current === null)
        caseId.current = await createInvestigation(title.trim(), token!);
      for (const entry of entries.filter((e) => e.status !== "uploaded")) {
        setEntries((current) =>
          current.map((e) =>
            e.id === entry.id
              ? { ...e, status: "uploading", error: undefined }
              : e,
          ),
        );
        try {
          if (!demo && entry.file)
            await uploadCaseEvidence(
              caseId.current!,
              entry.file,
              token!,
              entry.id,
            );
          setEntries((current) =>
            current.map((e) =>
              e.id === entry.id ? { ...e, status: "uploaded" } : e,
            ),
          );
        } catch (cause) {
          setEntries((current) =>
            current.map((e) =>
              e.id === entry.id
                ? {
                    ...e,
                    status: "failed",
                    error:
                      cause instanceof Error
                        ? cause.message
                        : "Upload failed. Please retry.",
                  }
                : e,
            ),
          );
        }
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not upload evidence.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function review() {
    setReviewing(true);
    setError("");
    try {
      await onReview(caseId.current, title.trim() || "Sample investigation");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not load analysis. Please retry.",
      );
    } finally {
      setReviewing(false);
    }
  }
  function useSample() {
    setSample(true);
    setTitle("Sample investigation");
    setError("");
    setEntries(
      demoEvidence.map((e) => ({
        ...e,
        id: crypto.randomUUID(),
        status: "uploaded",
      })),
    );
  }
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="./index.html" className={styles.brand}>
          <span>P</span>Parakh
        </a>
        <span>Investigator workspace</span>
        <span className={styles.mode}>
          {demo ? "Demo mode · Offline" : "Signed in"}
        </span>
      </header>
      <main className={styles.main}>
        <button className={styles.back} onClick={onBack} disabled={locked}>
          <ArrowLeft /> Back to sign-in
        </button>
        <ol className={styles.steps} aria-label="Investigation workflow">
          <li aria-current={!ready ? "step" : undefined}>
            <span>1</span>Upload evidence
          </li>
          <li aria-current={ready ? "step" : undefined}>
            <span>2</span>Review evidence list
          </li>
          <li>
            <span>3</span>Investigate & report
          </li>
        </ol>
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>Start a new investigation</p>
            <h1>First, upload all your evidence.</h1>
            <p>
              Bring the source files together in one case. Review the list below
              before opening timelines, connections and analysis.
            </p>
          </div>
          <UploadCloud />
        </div>
        {demo && (
          <div className={styles.demoNotice}>
            <strong>You’re exploring demo mode.</strong> Files selected here
            stay in this browser session and are not uploaded or analysed. The
            next screen uses preloaded fictional sample analysis. To process
            your own evidence, sign in to the backend.
          </div>
        )}
        <div className={styles.layout}>
          <section className={styles.panel} aria-label="Evidence intake">
            <label htmlFor="new-case-title" className={styles.label}>
              Case name {demo && <span>(optional)</span>}
            </label>
            <input
              id="new-case-title"
              className={styles.caseInput}
              value={title}
              placeholder="Enter a case name"
              disabled={locked || caseId.current !== null || sample}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
            />
            <div
              className={`${styles.dropzone} ${dragging ? styles.dragging : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                if (!locked && !sample) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={drop}
            >
              <UploadCloud />
              <h2>Drop evidence files here</h2>
              <p>
                Add chats, bank statements, receipts, location history, call
                records, emails and more.
              </p>
              <div className={styles.buttons}>
                <button
                  onClick={() => input.current?.click()}
                  disabled={locked || sample}
                >
                  Choose files
                </button>
                <button
                  onClick={() => folder.current?.click()}
                  disabled={locked || sample}
                >
                  <FolderOpen /> Choose folder
                </button>
              </div>
              <small>
                Keep the original file formats. You can add multiple files
                before continuing.
              </small>
              <input
                ref={input}
                type="file"
                multiple
                onChange={choose}
                aria-label="Choose evidence files"
                hidden
              />
              <input
                ref={(el) => {
                  folder.current = el;
                  el?.setAttribute("webkitdirectory", "");
                }}
                type="file"
                multiple
                onChange={choose}
                aria-label="Choose evidence folder"
                hidden
              />
            </div>
            <div className={styles.listHeading}>
              <h2>
                Evidence list <span>{entries.length} files</span>
              </h2>
              {demo && !entries.length && (
                <button onClick={useSample}>
                  Use bundled demo evidence <ArrowRight />
                </button>
              )}
            </div>
            {!entries.length ? (
              <div className={styles.empty}>
                <FileText />
                <p>No evidence added yet.</p>
                <small>
                  Select the files for this investigation to get started.
                </small>
              </div>
            ) : (
              <ul className={styles.fileList}>
                {entries.map((entry) => (
                  <li key={entry.id}>
                    <FileText />
                    <div className={styles.fileName}>
                      <strong>{entry.name}</strong>
                      <small>
                        {sizeLabel(entry.size)}
                        {entry.error && (
                          <span role="alert"> · {entry.error}</span>
                        )}
                      </small>
                    </div>
                    <span className={styles.fileStatus}>
                      {entry.status === "uploading" ? (
                        <LoaderCircle className={styles.spinner} />
                      ) : entry.status === "uploaded" ? (
                        <Check />
                      ) : null}
                      {entry.status === "uploaded"
                        ? demo
                          ? "Ready for demo"
                          : "Uploaded"
                        : entry.status === "failed"
                          ? "Failed · retry"
                          : entry.status === "uploading"
                            ? "Uploading…"
                            : "Selected"}
                    </span>
                    {entry.status !== "uploaded" && (
                      <button
                        aria-label={`Remove ${entry.name}`}
                        disabled={locked}
                        onClick={() =>
                          setEntries((current) =>
                            current.filter((e) => e.id !== entry.id),
                          )
                        }
                      >
                        <Trash2 />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {error && (
              <p role="alert" className={styles.error}>
                {error}
              </p>
            )}
            <div className={styles.actions}>
              <p aria-live="polite">
                {busy
                  ? "Keep this page open while your evidence uploads."
                  : ready
                    ? demo
                      ? "Demo evidence list ready. Open the sample analysis to explore the next steps."
                      : "All files uploaded. Review the list, then open your case analysis."
                    : "Add all evidence files, then confirm the list."}
              </p>
              {ready ? (
                <button
                  className={styles.primary}
                  disabled={locked}
                  onClick={review}
                >
                  {reviewing
                    ? "Loading analysis…"
                    : demo
                      ? "Open sample analysis"
                      : "Open case analysis"}
                  <ArrowRight />
                </button>
              ) : (
                <button
                  className={styles.primary}
                  disabled={
                    locked || !entries.length || (!demo && !title.trim())
                  }
                  onClick={upload}
                >
                  {busy
                    ? "Uploading…"
                    : demo
                      ? "Confirm demo file list"
                      : "Upload evidence"}
                  <ArrowRight />
                </button>
              )}
            </div>
          </section>
          <aside className={styles.help}>
            <h2>What happens next?</h2>
            <div>
              <span>1</span>
              <h3>Upload the evidence</h3>
              <p>
                Select all source files for the investigation. Keep related
                records together.
              </p>
            </div>
            <div>
              <span>2</span>
              <h3>Review the list</h3>
              <p>
                Check the filenames and upload status. Retry any failed files
                before continuing.
              </p>
            </div>
            <div>
              <span>3</span>
              <h3>Explore and explain</h3>
              <p>
                Review the timeline, connections and source records, then
                prepare your findings.
              </p>
            </div>
            {demo && (
              <p className={styles.folderNote}>
                The 15 synthetic source files for the video demo are in{" "}
                <code>parakh/evidence/</code>. Choose that folder, or use the
                bundled demo list.
              </p>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
