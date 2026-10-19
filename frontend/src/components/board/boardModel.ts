export type BoardReceipt = {
  evidence_id?: number | null;
  file: string;
  reference: string;
  sha256: string;
};
export type BoardCardKind =
  | "person" | "identifier" | "message" | "event" | "bank" | "call"
  | "document" | "location" | "finding" | "note";
export type BoardCard = {
  id: string;
  kind: BoardCardKind;
  title: string;
  body: string;
  timestamp: string | null;
  source_badge: string;
  receipt?: BoardReceipt | null;
  x: number;
  y: number;
  locked: boolean;
  community: number;
  size: number;
  selected?: boolean;
};
export type BoardLinkStatus = "established" | "possible" | "hypothesis" | "contradicted" | "not_established";
export type BoardLink = {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
  status: BoardLinkStatus;
  auto: boolean;
  support: string[];
  reasons: string[];
  confidence?: number | null;
  model_name?: string | null;
  model_version?: string | null;
};
export type BoardZone = { id: string; label: string; x: number; y: number; width: number; height: number; community: number };
export type BoardState = {
  schema_version: 1;
  seed: number;
  cards: BoardCard[];
  links: BoardLink[];
  zones: BoardZone[];
  exhibit_ids: string[];
  caption: string;
  viewport: { x: number; y: number; zoom: number };
};
export type BoardEnvelope = {
  schema_version: 1;
  revision: number;
  updated_by: string | null;
  updated_at: string | null;
  board_hash: string;
  can_edit: boolean;
  realtime: { status: "planned"; tier: "T3" };
  state: BoardState;
};
export type BoardSnapshot = { id: number; name: string; revision: number; board_hash: string; created_by: string; created_at?: string; state?: BoardState };

export const BOARD_SEED = 51026;
export const BOARD_WARNING = "A line on this board shows a relationship in the records, or a hypothesis. It does not prove involvement.";

const receipt = (evidence_id: number, file: string, reference: string, sha256: string): BoardReceipt => ({ evidence_id, file, reference, sha256 });
export const riyaBoard = (hashes: Record<number, string> = {}): BoardState => ({
  schema_version: 1,
  seed: BOARD_SEED,
  caption: "Riya synthetic investment-fraud evidence board",
  viewport: { x: 0, y: 0, zoom: 1 },
  exhibit_ids: [],
  zones: [
    { id: "zone-lure", label: "Lure", x: 40, y: 40, width: 520, height: 300, community: 1 },
    { id: "zone-payment", label: "Payment", x: 600, y: 40, width: 610, height: 520, community: 2 },
    { id: "zone-onward", label: "Onward movement", x: 1250, y: 40, width: 540, height: 520, community: 3 },
  ],
  cards: [
    { id: "riya", kind: "person", title: "Riya", body: "Victim / complainant in the synthetic pack", timestamp: "2026-09-12T09:05:00+05:30", source_badge: "WhatsApp", receipt: receipt(1, "01_whatsapp_riya_android.txt", "line:1", hashes[1] ?? ""), x: 100, y: 110, locked: true, community: 1, size: 1.35 },
    { id: "arjun", kind: "identifier", title: "Agent Arjun", body: "Display name; legal identity not established", timestamp: "2026-09-12T09:06:00+05:30", source_badge: "WhatsApp", receipt: receipt(1, "01_whatsapp_riya_android.txt", "line:2", hashes[1] ?? ""), x: 330, y: 90, locked: false, community: 1, size: 1.3 },
    { id: "guarantee", kind: "message", title: "Guaranteed return pitch", body: "Pressure language and guaranteed returns", timestamp: "2026-09-12T09:06:00+05:30", source_badge: "WhatsApp", receipt: receipt(1, "01_whatsapp_riya_android.txt", "line:2", hashes[1] ?? ""), x: 315, y: 220, locked: false, community: 1, size: 1 },
    { id: "handle", kind: "identifier", title: "arjun.collect@demo", body: "Payment identifier supplied in the chat", timestamp: "2026-09-12T09:18:00+05:30", source_badge: "WhatsApp", receipt: receipt(1, "01_whatsapp_riya_android.txt", "line:10", hashes[1] ?? ""), x: 650, y: 90, locked: false, community: 2, size: 1.25 },
    { id: "riya-account", kind: "bank", title: "DEMO-ACCT-RIYA-001", body: "Victim account; two INR 25,000 debits", timestamp: "2026-09-12T09:25:00+05:30", source_badge: "Victim bank CSV", receipt: receipt(3, "03_bank_statement_riya.csv", "row:4", hashes[3] ?? ""), x: 650, y: 230, locked: true, community: 2, size: 1.4 },
    { id: "payment-1", kind: "bank", title: "DEMO-UPI-001 · INR 25,000", body: "First outgoing payment", timestamp: "2026-09-12T09:25:00+05:30", source_badge: "Victim bank CSV", receipt: receipt(3, "03_bank_statement_riya.csv", "row:4", hashes[3] ?? ""), x: 860, y: 185, locked: false, community: 2, size: 1 },
    { id: "payment-2", kind: "bank", title: "DEMO-UPI-002 · INR 25,000", body: "Second outgoing payment", timestamp: "2026-09-12T09:33:00+05:30", source_badge: "Victim bank CSV", receipt: receipt(3, "03_bank_statement_riya.csv", "row:5", hashes[3] ?? ""), x: 860, y: 315, locked: false, community: 2, size: 1 },
    { id: "collection", kind: "bank", title: "DEMO-ACCT-COLLECT-009", body: "Receiving account; legal operator unknown", timestamp: "2026-09-12T09:25:05+05:30", source_badge: "Collection bank CSV", receipt: receipt(5, "05_bank_statement_collection.csv", "row:2", hashes[5] ?? ""), x: 1060, y: 250, locked: true, community: 2, size: 1.5 },
    { id: "cashout-one", kind: "bank", title: "cashout.one@demo", body: "INR 30,000 onward transfer", timestamp: "2026-09-12T09:36:00+05:30", source_badge: "Collection bank CSV", receipt: receipt(5, "05_bank_statement_collection.csv", "row:4", hashes[5] ?? ""), x: 1320, y: 160, locked: false, community: 3, size: 1.2 },
    { id: "cashout-two", kind: "bank", title: "cashout.two@demo", body: "INR 19,500 onward transfer", timestamp: "2026-09-12T09:38:00+05:30", source_badge: "Collection bank CSV", receipt: receipt(5, "05_bank_statement_collection.csv", "row:5", hashes[5] ?? ""), x: 1320, y: 330, locked: false, community: 3, size: 1.2 },
    { id: "refund", kind: "document", title: "False refund receipt", body: "Claims INR 50,000 refund using DEMO-UPI-001; no matching credit in supplied coverage", timestamp: "2026-09-12T09:42:00+05:30", source_badge: "Refund receipt PDF", receipt: receipt(6, "06_refund_receipt_claim.pdf", "page:1", hashes[6] ?? ""), x: 975, y: 430, locked: false, community: 2, size: 1.35 },
    { id: "arjun-phone", kind: "call", title: "DEMO-PHONE-ARJUN", body: "Three answered calls around the payment requests; contents unknown", timestamp: "2026-09-12T09:14:00+05:30", source_badge: "Call records", receipt: receipt(8, "08_call_records_riya.csv", "row:2", hashes[8] ?? ""), x: 110, y: 410, locked: false, community: 1, size: 1.1 },
    { id: "victim-location", kind: "location", title: "Riya device locations", body: "Victim location only; no suspect location evidence", timestamp: "2026-09-12T03:15:00Z", source_badge: "GPS JSON", receipt: receipt(7, "07_gps_location_riya.json", "record:1", hashes[7] ?? ""), x: 340, y: 410, locked: false, community: 1, size: 1 },
    { id: "caution", kind: "note", title: "Do not infer account control", body: "Investigator note, not evidence: a display name and payment handle do not establish legal identity.", timestamp: null, source_badge: "Investigator note, not evidence", receipt: null, x: 1510, y: 430, locked: false, community: 3, size: 1 },
  ],
  links: [
    { id: "l-riya-account", source: "riya", target: "riya-account", label: "account holder", type: "same identifier", status: "established", auto: true, support: ["3:row:4"], reasons: ["Statement names Riya and the account"], confidence: 1 },
    { id: "l-arjun-handle", source: "arjun", target: "handle", label: "handle supplied in chat", type: "same identifier", status: "possible", auto: true, support: ["1:line:10"], reasons: ["Display name supplied the handle; legal control remains unknown"], confidence: 0.82 },
    { id: "l-arjun-phone", source: "arjun", target: "arjun-phone", label: "contact label", type: "same identifier", status: "possible", auto: true, support: ["8:row:2"], reasons: ["Call record contact label"], confidence: 0.71 },
    { id: "l-handle-collection", source: "handle", target: "collection", label: "payment destination", type: "same identifier", status: "established", auto: true, support: ["1:line:10", "5:row:2"], reasons: ["Chat request and matching bank credit"], confidence: 1 },
    { id: "l-riya-payment1", source: "riya-account", target: "payment-1", label: "debited", type: "payment between accounts", status: "established", auto: true, support: ["3:row:4"], reasons: ["Direct bank row"], confidence: 1 },
    { id: "l-riya-payment2", source: "riya-account", target: "payment-2", label: "debited", type: "payment between accounts", status: "established", auto: true, support: ["3:row:5"], reasons: ["Direct bank row"], confidence: 1 },
    { id: "l-payment1-collection", source: "payment-1", target: "collection", label: "credited 5 seconds later", type: "payment between accounts", status: "established", auto: true, support: ["3:row:4", "5:row:2"], reasons: ["Same UTR and amount in both supplied statements"], confidence: 1 },
    { id: "l-payment2-collection", source: "payment-2", target: "collection", label: "credited 5 seconds later", type: "payment between accounts", status: "established", auto: true, support: ["3:row:5", "5:row:3"], reasons: ["Same UTR and amount in both supplied statements"], confidence: 1 },
    { id: "l-collection-one", source: "collection", target: "cashout-one", label: "INR 30,000 onward", type: "payment between accounts", status: "established", auto: true, support: ["5:row:4"], reasons: ["Direct bank row"], confidence: 1 },
    { id: "l-collection-two", source: "collection", target: "cashout-two", label: "INR 19,500 onward", type: "payment between accounts", status: "established", auto: true, support: ["5:row:5"], reasons: ["Direct bank row"], confidence: 1 },
    { id: "l-refund", source: "refund", target: "riya-account", label: "claimed refund conflicts with statement", type: "document claim", status: "contradicted", auto: true, support: ["6:page:1", "3:rows:4-5"], reasons: ["Amount, direction and timing differ; no matching credit in supplied coverage"], confidence: 1 },
    { id: "l-unsupported", source: "arjun", target: "cashout-one", label: "controls end account?", type: "investigator hypothesis", status: "not_established", auto: false, support: [], reasons: ["No cited card or note supports legal control"] },
  ],
});

export const cloneBoard = (value: BoardState): BoardState => JSON.parse(JSON.stringify(value)) as BoardState;

export const deleteBoardCards = (value: BoardState, cardIds: string[]): BoardState => {
  const next = cloneBoard(value);
  const removed = new Set(cardIds);
  next.cards = next.cards.filter((card) => !removed.has(card.id));
  next.links = next.links.filter((link) => !removed.has(link.source) && !removed.has(link.target));
  return next;
};
