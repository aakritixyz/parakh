import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileArchive,
  FileText,
  FolderOpen,
  LoaderCircle,
  RotateCcw,
  Square,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { createInvestigation } from "../../api";
import {
  cancelIntakeJob,
  createDevice,
  createOwner,
  getDevices,
  getIntakeJobs,
  getOwners,
  importEvidence,
  retryIntakeJob,
  type Device,
  type Owner,
} from "../../caseApi";
import { demoEvidence } from "./demoEvidence";
import styles from "./Intake.module.css";

type Stage =
  | "Selected"
  | "Hashing"
  | "Stored"
  | "Parsing"
  | "Indexing"
  | "Done"
  | "Failed"
  | "Cancelled";
type Entry = {
  id: string;
  name: string;
  size: number;
  file?: File;
  sourceType: string;
  ownerId: number | null;
  deviceId: number | null;
  note: string;
  stage: Stage;
  jobId?: number;
  evidenceId?: number;
  duplicate?: boolean;
  warning?: string | null;
  error?: string;
};
type Props = {
  existingCaseId?: number;
  initialTitle?: string;
  backLabel?: string;
  token: string | null;
  onReview: (caseId: number | null, title: string) => Promise<void>;
  onBack: () => void;
};
const sourceTypes = [
  "whatsapp",
  "bank_statement",
  "receipt",
  "location_history",
  "call_records",
  "email",
  "browser_history",
  "device_log",
  "document",
  "archive",
];
const suggestSource = (name: string) => {
  const value = name.toLowerCase();
  if (value.endsWith(".zip")) return "archive";
  if (value.includes("whatsapp")) return "whatsapp";
  if (value.includes("receipt")) return "receipt";
  if (value.includes("gps") || value.includes("location"))
    return "location_history";
  if (value.includes("call") || value.includes("cdr")) return "call_records";
  if (value.endsWith(".eml")) return "email";
  if (value.includes("browser") || value.endsWith(".sqlite"))
    return "browser_history";
  if (value.includes("bank") || value.endsWith(".csv")) return "bank_statement";
  if (value.includes("device")) return "device_log";
  return "document";
};
const sizeLabel = (bytes: number) =>
  bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;

export function EvidenceIntake({
  token,
  onReview,
  onBack,
  existingCaseId,
  initialTitle = "",
  backLabel = "Back to sign-in",
}: Props) {
  const demo = !token;
  const [title, setTitle] = useState(initialTitle);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [owners, setOwners] = useState<Owner[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [ownerName, setOwnerName] = useState("Riya");
  const [deviceLabel, setDeviceLabel] = useState("");
  const [handedOverBy, setHandedOverBy] = useState("");
  const [acquiredAt, setAcquiredAt] = useState(
    new Date().toISOString().slice(0, 16),
  );
  const [method, setMethod] = useState("Logical export supplied by owner");
  const [acquisitionNotes, setAcquisitionNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [sample, setSample] = useState(false);
  const caseId = useRef<number | null>(existingCaseId ?? null);
  const input = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement | null>(null);
  const locked = busy || reviewing;
  const ready =
    entries.length > 0 && entries.every((entry) => entry.stage === "Done");

  useEffect(() => {
    if (demo || !caseId.current) return;
    void Promise.all([
      getOwners(caseId.current),
      getDevices(caseId.current),
    ]).then(([nextOwners, nextDevices]) => {
      setOwners(nextOwners);
      setDevices(nextDevices);
    });
  }, [demo]);

  function addFiles(files: File[]) {
    if (locked || sample) return;
    setError("");
    setEntries((current) => {
      const keys = new Set(
        current.map((entry) => `${entry.name}:${entry.size}`),
      );
      return [
        ...current,
        ...files
          .sort((a, b) => a.name.localeCompare(b.name))
          .filter((file) => {
            const key = `${file.name}:${file.size}`;
            if (keys.has(key)) return false;
            keys.add(key);
            return true;
          })
          .map((file) => ({
            id: crypto.randomUUID(),
            name: file.webkitRelativePath || file.name,
            size: file.size,
            file,
            sourceType: suggestSource(file.name),
            ownerId: owners[0]?.id ?? null,
            deviceId: devices[0]?.id ?? null,
            note: "",
            stage: "Selected" as const,
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
  function updateEntry(id: string, change: Partial<Entry>) {
    setEntries((current) =>
      current.map((entry) =>
        entry.id === id ? { ...entry, ...change } : entry,
      ),
    );
  }

  async function prepareContext() {
    if (caseId.current === null)
      caseId.current = await createInvestigation(title.trim(), token!);
    let owner = owners.find(
      (item) =>
        item.display_name.toLowerCase() === ownerName.trim().toLowerCase(),
    );
    if (!owner) {
      owner = await createOwner(caseId.current, ownerName.trim());
      setOwners((current) => [...current, owner!]);
    }
    let device: Device | null = null;
    if (deviceLabel.trim()) {
      device =
        devices.find(
          (item) =>
            item.label.toLowerCase() === deviceLabel.trim().toLowerCase(),
        ) ?? null;
      if (!device) {
        device = await createDevice(caseId.current, {
          label: deviceLabel.trim(),
          make: null,
          model: null,
          os: null,
          serial: null,
        });
        setDevices((current) => [...current, device!]);
      }
    }
    return { owner, device };
  }

  async function upload() {
    if (demo) {
      setEntries((current) =>
        current.map((entry) => ({ ...entry, stage: "Done" })),
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      const context = await prepareContext();
      const jobMap = new Map<number, string>();
      for (const entry of entries.filter((item) => item.stage !== "Done")) {
        if (!entry.file) continue;
        updateEntry(entry.id, { stage: "Hashing", error: undefined });
        try {
          const result = await importEvidence(
            caseId.current!,
            entry.file,
            entry.id,
            {
              sourceType: entry.sourceType,
              ownerId: entry.ownerId ?? context.owner.id,
              deviceId: entry.deviceId ?? context.device?.id ?? null,
              handedOverBy,
              acquiredAt: new Date(acquiredAt).toISOString(),
              acquisitionMethod: method,
              note: [acquisitionNotes, entry.note].filter(Boolean).join("\n"),
            },
          );
          const primary = result.items[0];
          updateEntry(entry.id, {
            stage: primary.job?.stage ?? "Done",
            jobId: primary.job?.id,
            evidenceId: primary.id,
            duplicate: primary.duplicate,
            warning: primary.magic_byte_warning,
          });
          if (primary.job && primary.job.status !== "completed")
            jobMap.set(primary.job.id, entry.id);
        } catch (cause) {
          updateEntry(entry.id, {
            stage: "Failed",
            error: cause instanceof Error ? cause.message : "Import failed.",
          });
        }
      }
      while (jobMap.size) {
        await new Promise((resolve) => window.setTimeout(resolve, 350));
        for (const job of await getIntakeJobs(caseId.current!)) {
          const entryId = jobMap.get(job.id);
          if (!entryId) continue;
          updateEntry(entryId, {
            stage: job.stage,
            error: job.error ?? undefined,
          });
          if (["completed", "failed", "cancelled"].includes(job.status))
            jobMap.delete(job.id);
        }
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not import evidence.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function cancel(entry: Entry) {
    if (!caseId.current || !entry.jobId) return;
    const job = await cancelIntakeJob(caseId.current, entry.jobId);
    updateEntry(entry.id, { stage: job.stage });
  }
  async function retry(entry: Entry) {
    if (!caseId.current || !entry.jobId) return;
    setBusy(true);
    try {
      const job = await retryIntakeJob(caseId.current, entry.jobId);
      updateEntry(entry.id, {
        jobId: job.id,
        stage: job.stage,
        error: undefined,
      });
      for (;;) {
        await new Promise((resolve) => window.setTimeout(resolve, 350));
        const current = (await getIntakeJobs(caseId.current)).find(
          (item) => item.id === job.id,
        );
        if (!current) throw new Error("Retry job disappeared from the queue.");
        updateEntry(entry.id, {
          stage: current.stage,
          error: current.error ?? undefined,
        });
        if (["completed", "failed", "cancelled"].includes(current.status))
          break;
      }
    } catch (cause) {
      updateEntry(entry.id, {
        stage: "Failed",
        error: cause instanceof Error ? cause.message : "Retry failed.",
      });
    } finally {
      setBusy(false);
    }
  }
  async function review() {
    setReviewing(true);
    try {
      await onReview(caseId.current, title.trim() || "Sample investigation");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not load analysis.",
      );
    } finally {
      setReviewing(false);
    }
  }
  function useSample() {
    setSample(true);
    setTitle("Sample investigation");
    setHandedOverBy("Riya");
    setAcquisitionNotes("Synthetic logical exports for product demonstration.");
    setEntries(
      demoEvidence.map((item) => ({
        ...item,
        id: crypto.randomUUID(),
        sourceType: suggestSource(item.name),
        ownerId: null,
        deviceId: null,
        note: "Synthetic demo evidence",
        stage: "Done" as const,
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
          {demo ? "Synthetic demo · Read-only" : "Signed in"}
        </span>
      </header>
      <main className={styles.main}>
        <button className={styles.back} onClick={onBack} disabled={locked}>
          <ArrowLeft /> {backLabel}
        </button>
        <ol className={styles.steps} aria-label="Evidence intake workflow">
          <li aria-current={!entries.length ? "step" : undefined}>
            <span>1</span>Acquisition context
          </li>
          <li aria-current={entries.length && !ready ? "step" : undefined}>
            <span>2</span>Seal & process
          </li>
          <li aria-current={ready ? "step" : undefined}>
            <span>3</span>Review sealed evidence
          </li>
        </ol>
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>Evidence intake</p>
            <h1>Seal the originals first.</h1>
            <p>
              Record where the evidence came from, then hash and preserve every
              original before parsing starts.
            </p>
          </div>
          <UploadCloud />
        </div>
        {demo && (
          <div className={styles.demoNotice}>
            <strong>Synthetic demo data · Read-only.</strong> No files, owners,
            devices or audit entries are written in demo mode.
          </div>
        )}
        <div className={styles.layout}>
          <section className={styles.panel} aria-label="Evidence intake wizard">
            <h2 className={styles.sectionTitle}>1. Acquisition context</h2>
            <div className={styles.formGrid}>
              <label>
                Case name
                <input
                  className={styles.caseInput}
                  value={title}
                  disabled={locked || caseId.current !== null || sample}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </label>
              <label>
                Owner
                <input
                  className={styles.caseInput}
                  value={ownerName}
                  disabled={locked || sample}
                  onChange={(event) => setOwnerName(event.target.value)}
                  placeholder="Riya"
                />
              </label>
              <label>
                Device <span>(optional)</span>
                <input
                  className={styles.caseInput}
                  value={deviceLabel}
                  disabled={locked || sample}
                  onChange={(event) => setDeviceLabel(event.target.value)}
                  placeholder="Riya's Android phone"
                />
              </label>
              <label>
                Who handed it over
                <input
                  className={styles.caseInput}
                  value={handedOverBy}
                  disabled={locked || sample}
                  onChange={(event) => setHandedOverBy(event.target.value)}
                />
              </label>
              <label>
                When received
                <input
                  className={styles.caseInput}
                  type="datetime-local"
                  value={acquiredAt}
                  disabled={locked || sample}
                  onChange={(event) => setAcquiredAt(event.target.value)}
                />
              </label>
              <label>
                Acquisition method
                <input
                  className={styles.caseInput}
                  value={method}
                  disabled={locked || sample}
                  onChange={(event) => setMethod(event.target.value)}
                />
              </label>
            </div>
            <label className={styles.fullLabel}>
              Acquisition notes
              <textarea
                className={styles.caseInput}
                value={acquisitionNotes}
                disabled={locked || sample}
                onChange={(event) => setAcquisitionNotes(event.target.value)}
                placeholder="Condition, handover context, export steps…"
              />
            </label>
            <h2 className={styles.sectionTitle}>
              2. Add files, folders or ZIP
            </h2>
            <div
              className={`${styles.dropzone} ${dragging ? styles.dragging : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (!locked && !sample) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={drop}
            >
              <UploadCloud />
              <h2>Drop evidence here</h2>
              <p>
                Files and folders are sealed individually. Safe ZIP members
                become separately hashed child evidence.
              </p>
              <div className={styles.buttons}>
                <button
                  onClick={() => input.current?.click()}
                  disabled={locked || sample}
                >
                  Choose files or ZIP
                </button>
                <button
                  onClick={() => folder.current?.click()}
                  disabled={locked || sample}
                >
                  <FolderOpen /> Choose folder
                </button>
              </div>
              <small>
                ZIP paths, expansion size, member count and compression ratios
                are checked before import.
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
                ref={(element) => {
                  folder.current = element;
                  element?.setAttribute("webkitdirectory", "");
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
                  Use bundled 15-file pack <ArrowRight />
                </button>
              )}
            </div>
            {!entries.length ? (
              <div className={styles.empty}>
                <FileText />
                <p>No evidence added yet.</p>
                <small>Add the full source pack before starting import.</small>
              </div>
            ) : (
              <ul className={styles.fileList}>
                {entries.map((entry) => (
                  <li key={entry.id} className={styles.fileRow}>
                    {entry.name.toLowerCase().endsWith(".zip") ? (
                      <FileArchive />
                    ) : (
                      <FileText />
                    )}
                    <div className={styles.fileName}>
                      <strong>{entry.name}</strong>
                      <small>
                        {sizeLabel(entry.size)}
                        {entry.duplicate &&
                          " · Exact duplicate — existing evidence reused"}
                        {entry.warning && <span> · {entry.warning}</span>}
                        {entry.error && (
                          <span role="alert"> · {entry.error}</span>
                        )}
                      </small>
                    </div>
                    <label className={styles.compactLabel}>
                      Source type
                      <select
                        value={entry.sourceType}
                        disabled={locked || entry.stage !== "Selected"}
                        onChange={(event) =>
                          updateEntry(entry.id, {
                            sourceType: event.target.value,
                          })
                        }
                      >
                        {sourceTypes.map((type) => (
                          <option key={type}>{type}</option>
                        ))}
                      </select>
                    </label>
                    <label className={styles.compactLabel}>
                      Owner
                      <select
                        value={entry.ownerId ?? "default"}
                        disabled={locked || entry.stage !== "Selected"}
                        onChange={(event) =>
                          updateEntry(entry.id, {
                            ownerId:
                              event.target.value === "default"
                                ? null
                                : Number(event.target.value),
                          })
                        }
                      >
                        <option value="default">
                          Use acquisition owner ({ownerName || "unnamed"})
                        </option>
                        {owners.map((owner) => (
                          <option key={owner.id} value={owner.id}>
                            {owner.display_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className={styles.compactLabel}>
                      Device
                      <select
                        value={entry.deviceId ?? "default"}
                        disabled={locked || entry.stage !== "Selected"}
                        onChange={(event) =>
                          updateEntry(entry.id, {
                            deviceId:
                              event.target.value === "default"
                                ? null
                                : Number(event.target.value),
                          })
                        }
                      >
                        <option value="default">
                          {deviceLabel || "No device"}
                        </option>
                        {devices.map((device) => (
                          <option key={device.id} value={device.id}>
                            {device.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className={styles.compactLabel}>
                      File note
                      <input
                        value={entry.note}
                        disabled={locked || entry.stage !== "Selected"}
                        onChange={(event) =>
                          updateEntry(entry.id, { note: event.target.value })
                        }
                      />
                    </label>
                    <span className={styles.fileStatus}>
                      {["Hashing", "Stored", "Parsing", "Indexing"].includes(
                        entry.stage,
                      ) && <LoaderCircle className={styles.spinner} />}
                      {entry.stage === "Done" && <Check />}
                      {entry.stage}
                    </span>
                    {entry.stage === "Selected" && (
                      <button
                        aria-label={`Remove ${entry.name}`}
                        disabled={locked}
                        onClick={() =>
                          setEntries((current) =>
                            current.filter((item) => item.id !== entry.id),
                          )
                        }
                      >
                        <Trash2 />
                      </button>
                    )}
                    {["Stored", "Parsing", "Indexing"].includes(
                      entry.stage,
                    ) && (
                      <button
                        aria-label={`Cancel ${entry.name}`}
                        onClick={() => void cancel(entry)}
                      >
                        <Square />
                      </button>
                    )}
                    {["Failed", "Cancelled"].includes(entry.stage) &&
                      entry.jobId && (
                        <button
                          aria-label={`Retry ${entry.name}`}
                          onClick={() => void retry(entry)}
                        >
                          <RotateCcw />
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
                  ? "Hashing, sealing, parsing and indexing. Originals remain unchanged."
                  : ready
                    ? "Every selected original is sealed. Review the evidence list before investigation."
                    : "Complete the acquisition record and confirm each file before import."}
              </p>
              {ready ? (
                <button
                  className={styles.primary}
                  disabled={locked}
                  onClick={review}
                >
                  {reviewing
                    ? "Loading…"
                    : demo
                      ? "Open sample analysis"
                      : "Open case analysis"}
                  <ArrowRight />
                </button>
              ) : (
                <button
                  className={styles.primary}
                  disabled={
                    locked ||
                    !entries.length ||
                    (!demo &&
                      (!title.trim() ||
                        !ownerName.trim() ||
                        !handedOverBy.trim() ||
                        !method.trim()))
                  }
                  onClick={upload}
                >
                  {busy
                    ? "Importing…"
                    : demo
                      ? "Confirm demo list"
                      : "Start import"}
                  <ArrowRight />
                </button>
              )}
            </div>
          </section>
          <aside className={styles.help}>
            <h2>Sealing sequence</h2>
            <div>
              <span>1</span>
              <h3>Hashing</h3>
              <p>
                SHA-256 and MD5 are computed as bytes stream into the vault.
              </p>
            </div>
            <div>
              <span>2</span>
              <h3>Stored</h3>
              <p>
                The original is content-addressed and read-only; exact
                duplicates are rejected.
              </p>
            </div>
            <div>
              <span>3</span>
              <h3>Parsing & indexing</h3>
              <p>
                A background job extracts reviewable records. Cancel and retry
                remain available.
              </p>
            </div>
            <p className={styles.folderNote}>
              A matching hash proves the stored bytes are unchanged. It does not
              prove that the source is true.
            </p>
          </aside>
        </div>
      </main>
    </div>
  );
}
