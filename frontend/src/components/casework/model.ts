import fixture from "./demo.json";
export type SourceRow = { ref: string; text: string };
export type Source = {
  id: number;
  file: string;
  owner: string;
  source: string;
  note: string;
  sha256: string;
  md5?: string;
  bytes: number;
  parser: string;
  records: number;
  rows: SourceRow[];
  table?: Record<string, string>[];
};
export type RecordEvent = {
  id: string;
  file: string;
  evidence_id: number;
  timestamp_utc: string | null;
  original_timestamp: string | null;
  action: string;
  content: string;
  raw_ref: string;
  confidence: number;
  actor_entities: string[];
  location?: { lat?: number; lon?: number } | null;
};
export type AuditEntry = {
  sequence: number;
  action: string;
  filename: string;
  sha256: string;
  previous_hash: string;
  actor: string;
  timestamp: string;
  entry_hash: string;
};
export const demo = fixture as unknown as {
  files: Source[];
  events: RecordEvent[];
  audit: AuditEntry[];
  notice: string;
};
export type Citation = { file: number; ref?: string; label?: string };
export type FindingStatus =
  "Established" | "Possible" | "Not established" | "Contradicted";
export type Finding = {
  id: string;
  question: string;
  answer: string;
  status: FindingStatus;
  limits: string;
  citations: Citation[];
};
export const findings: Finding[] = [
  {
    id: "F1",
    question: "Who contacted Riya?",
    answer:
      "The WhatsApp display name Agent Arjun contacted Riya. The primary export contains 30 messages plus a synthetic notice.",
    status: "Established",
    limits:
      "A display name does not establish the legal identity or account controller.",
    citations: [
      { file: 1, ref: "line:3", label: "Primary chat · line 3" },
      { file: 1, ref: "line:1", label: "Primary chat · full export" },
    ],
  },
  {
    id: "F2",
    question: "Where did the money go?",
    answer:
      "Two ₹25,000 debits name arjun.collect@demo. The collection statement shows matching credits and ₹49,500 in onward transfers.",
    status: "Established",
    limits:
      "Onward movement is directly recorded in the collection statement; attribution of either individual payment to a particular onward transfer is only possible under assumptions, not uniquely established.",
    citations: [
      { file: 3, ref: "line:4" },
      { file: 3, ref: "line:5" },
      { file: 5, ref: "line:2" },
      { file: 5, ref: "line:4" },
      { file: 5, ref: "line:5" },
    ],
  },
  {
    id: "F3",
    question: "Does the receipt match the bank record?",
    answer:
      "No. The receipt claims a ₹50,000 refund at 09:42 using DEMO-UPI-001; that reference identifies a ₹25,000 outgoing debit at 09:25.",
    status: "Contradicted",
    limits:
      "No matching credit appears in the supplied 11–13 September statement. This does not rule out a later refund, and does not by itself establish who altered or created the receipt.",
    citations: [
      { file: 6, ref: "page:1" },
      { file: 3, ref: "line:4" },
      { file: 11, ref: "line:1" },
    ],
  },
  {
    id: "F4",
    question: "What supports each conclusion?",
    answer:
      "Each finding links to original source records, with a row or line reference, source time and SHA-256 hash.",
    status: "Established",
    limits:
      "The CSV and PDF statement are two representations of the same record, not independent corroboration. Fixture hashes verify byte consistency, not truth.",
    citations: [
      { file: 3, ref: "line:4" },
      { file: 4, ref: "page:1" },
      { file: 14, ref: "line:1" },
    ],
  },
  {
    id: "F5",
    question: "Can each outgoing payment be attributed to Riya?",
    answer:
      "No unique per-inflow allocation is established. Onward transfers depend collectively on the inflows only under zero-opening-balance and complete-coverage assumptions.",
    status: "Possible",
    limits:
      "Do not describe a particular downstream payment as Riya’s money without stating the allocation model and its limits.",
    citations: [
      { file: 5, ref: "line:2" },
      { file: 5, ref: "line:3" },
      { file: 5, ref: "line:4" },
      { file: 5, ref: "line:5" },
    ],
  },
  {
    id: "F6",
    question: "Where was Agent Arjun?",
    answer:
      "No supporting evidence found for the contact’s location or co-location with Riya.",
    status: "Not established",
    limits:
      "Only complainant GPS and contextual tower records are supplied. Nearness does not prove co-location.",
    citations: [
      { file: 7, ref: "line:1" },
      { file: 9, ref: "line:1" },
      { file: 14, ref: "line:1" },
    ],
  },
  {
    id: "F7",
    question: "Were messages deleted from the tablet?",
    answer:
      "Not established. Ten matching message bodies are timestamped 30 minutes earlier in the linked-device excerpt.",
    status: "Not established",
    limits:
      "The export is explicitly a selected excerpt. The clock observation supports a correction only if a constant historical offset is assumed.",
    citations: [
      { file: 2, ref: "line:1" },
      { file: 13, ref: "line:5" },
      { file: 14, ref: "line:1" },
    ],
  },
];
export const time = (value?: string | null) =>
  value
    ? new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date(value)) + " IST"
    : "Time not established";
export const sha256 = async (data: BufferSource) =>
  Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", data)))
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
export async function verifyChain(entries: AuditEntry[]) {
  let previous = "0".repeat(64);
  for (const entry of entries) {
    const { entry_hash, ...payload } = entry;
    const canonical = JSON.stringify(
      Object.fromEntries(
        Object.entries(payload).sort(([a], [b]) => a.localeCompare(b)),
      ),
    );
    if (
      payload.previous_hash !== previous ||
      (await sha256(new TextEncoder().encode(canonical))) !== entry_hash
    )
      return false;
    previous = entry_hash;
  }
  return entries.length > 0;
}
export function download(
  name: string,
  content: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
