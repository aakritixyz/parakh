import type { DashboardData, LoginCredentials } from "./api";
export type Role = "admin" | "investigator" | "analyst" | "prosecutor";
export type Account = { id: number; username: string; role: Role };
export type Session = {
  access_token: string;
  expires_in: number;
  user: Account;
};
export type CaseInfo = {
  id: number;
  title: string;
  case_number: string;
  jurisdiction: string;
  offence_type: string;
  description: string;
  lead_investigator: string | null;
  status: string;
  evidence_count: number;
  last_activity: string;
  created_at: string;
  effective_role: Role;
  can_manage: boolean;
  can_edit: boolean;
};
export type Member = {
  user_id: number;
  username: string;
  system_role: Role;
  role: Role;
};
export type CaseInput = {
  title: string;
  case_number: string;
  jurisdiction: string;
  offence_type: string;
  description: string;
  lead_investigator: string;
  team_members: { username: string; role: Role }[];
};
export type Audit = {
  chain_verified: boolean;
  scope: string;
  entries: {
    id: number;
    action: string;
    actor: string;
    created_at: string;
    payload: Record<string, unknown>;
    previous_hash: string;
    entry_hash: string;
  }[];
};
export type Owner = { id: number; display_name: string; notes: string };
export type Device = {
  id: number;
  label: string;
  make: string | null;
  model: string | null;
  os: string | null;
  serial: string | null;
};
export type IntakeJob = {
  id: number;
  evidence_id: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  stage:
    | "Hashing"
    | "Stored"
    | "Parsing"
    | "Indexing"
    | "Done"
    | "Failed"
    | "Cancelled";
  progress: number;
  attempt: number;
  error: string | null;
  logs: string[];
};
export type IntakeItem = {
  id: number;
  filename: string;
  archive_path: string | null;
  parent_evidence_id: number | null;
  sha256: string;
  md5: string;
  size_bytes: number;
  source_type: string;
  mime: string;
  magic_byte_warning: string | null;
  duplicate: boolean;
  job: IntakeJob | null;
};
export type ImportDecision = {
  type: string;
  message: string;
  evidence_id: number;
  filename: string;
  line?: number;
  value?: string;
  selected?: string;
};
export type ImportReportData = {
  case_id: number;
  files_imported: number;
  total_events: number;
  status: "ready" | "needs_review";
  decisions: ImportDecision[];
  files: {
    evidence_id: number;
    filename: string;
    event_count: number;
    parser_name: string | null;
    parser_version: string | null;
    parse_status: string;
    format_confidence: number | null;
    warnings: (string | ImportDecision)[];
    document_extraction: null | {
      engine: string;
      engine_version: string;
      languages: string[];
      boxes: { text: string; page: number; bbox: number[] }[];
      fields: Record<
        string,
        {
          value: string;
          confidence: number;
          method: string;
          reason: string;
          receipt: { page: number; bbox: number[] | null; text?: string };
        }
      >;
    };
  }[];
};
export type SearchEvent = {
  event_id: number;
  evidence_id: number;
  type: string;
  action: string;
  app: string;
  owner: string;
  device: string;
  parties: string[];
  identifiers: string[];
  tags: string[];
  timestamp_utc: string | null;
  original_timestamp: string | null;
  timezone_offset: string | null;
  content: string;
  raw_ref: string;
  confidence: number;
  source: { filename: string; sha256: string; reference: string };
};
export type SearchResult = {
  items: SearchEvent[];
  total_matching: number;
  total_in_case: number;
  next_cursor: number | null;
  search_engine: string;
  facets: Record<string, { value: string; count: number }[]>;
  histogram: { bucket: string; count: number }[];
  semantic_search: { status: string; reason: string };
};
export type IdentityOverview = {
  suggestions: {
    id: number;
    party: string;
    identifier: string;
    identifier_type: string;
    confidence: number;
    base_confidence: number;
    status: "suggested" | "confirmed" | "reverted";
    reasons: string[];
    feedback_bonus: number;
  }[];
  links: { party: string; identifier: string; source: string }[];
  matcher: {
    kind: string;
    version: string;
    ml_status: string;
    labels_recorded: number;
    limits: string;
  };
  lookalike_domains: { left: string; right: string; distance: number; reason: string }[];
};
export type ModelCard = {
  id: number;
  name: string;
  version: string;
  licence: string;
  training_data: string;
  known_limits: string[];
  metrics: {
    label: string;
    precision: number;
    recall: number;
    pr_auc: number;
    calibration_curve: { mean_predicted: number; fraction_positive: number }[];
  };
  explanations: {
    tree: { method: string; values: Record<string, number>; limit?: string };
    top_words: { word: string; weight: number }[];
  };
  artifact_sha256: string;
  evaluation_label: string;
  seed: number;
  offline_only: boolean;
};
export type PatternSupport = {
  event_id: number;
  evidence_id: number;
  file: string;
  reference: string;
  timestamp: string | null;
  sha256: string;
};
export type PatternResult = {
  flags: {
    type: string;
    title: string;
    why: string;
    method: string;
    status: string;
    confidence: number;
    support: PatternSupport[];
    caveat: string;
    test?: { p_value: number; fdr_alpha: number; complete: boolean; seed: number };
  }[];
  summary: { events_checked: number; flag_count: number; fdr_alpha: number };
  classifier: {
    status: string;
    name?: string;
    version?: string;
    label?: string;
    metrics?: { precision: number; recall: number; pr_auc: number };
    reason?: string;
  };
  assumptions: Record<string, string | number>;
  fallback: string;
};
export type IntegrityResult = {
  valid: boolean;
  label: string;
  notice: string;
  files: { evidence_id: number; filename: string; status: string; expected_sha256: string; actual_sha256: string | null; merkle_proof: { side: string; hash: string }[] }[];
  audit: { valid: boolean; entries: number; signed_entries: number; unsigned_legacy_entries: number; tip_hash: string };
  merkle: { algorithm: string; root: string; leaf_count: number };
};
export type OriginResult = {
  display_timezone: string;
  provenance: { event_id: number; evidence_id: number; file: string; source_reference: string; device: string; owner: string; parser: string; extraction_time: string; timestamp_utc: string | null; original_timestamp: string | null; timezone_offset: string | null; unknown: string[] }[];
  clock_reconciliation: { device: string; observed_clock_offset_seconds: number; correction_seconds: number; range_seconds: number[]; matched_anchors: number; solver: { method: string; complete: boolean; time_limit_seconds: number; seed: number; fallback: string } };
  second_device_comparison: { primary_file: string | null; secondary_file: string | null; secondary_evidence_id: number | null; matched?: number; missing: { event_id: number; content: string; source_reference: string }[]; edited: { event_id: number; content: string; source_reference: string }[]; reordered: unknown[]; method: string };
  timeline_consistency: { consistent: boolean; negative_cycle: unknown };
  ordering_probability: { statement: string; probability: number; samples: number; seed: number };
  order_dependent_event_ids: number[];
};
export type FraudReview = {
  authenticity: {
    evidence_id: number;
    suspicion_score: number;
    score_range: number[];
    findings: { severity: string; explanation: string; signal: string; weight: number; contribution: number; heuristic: boolean }[];
    similar_documents: { evidence_id: number; filename: string; similarity: number; method: string }[];
    ocr_claims: Record<string, { value: string; confidence: number }>;
    limits: string;
    detector_status: Record<string, string | number>;
  }[];
  contradictions: {
    contradictions: {
      type: string; label: string;
      receipt: { evidence_id: number; file: string; reference: string; amount: number; utr: string };
      record: { event_id: number; evidence_id: number; reference: string; amount: number; direction: string; utr: string };
      match: { algorithm: string; cost: number; amount_match: boolean; reference_match: boolean };
      alternatives: { name: string; result: string; likelihood_ratio: number; reason: string }[];
      would_settle: string[];
    }[];
    limits: string;
  };
  leads: FraudLead[];
  ranked: FraudLead[];
  review_plan: { budget_minutes: number; selected_lead_ids: number[]; method: string; complete: boolean; seed: number; fallback: string };
  ranking: { method: string; assumption: string; feedback: string };
};
export type FraudLead = { id: number; title: string; status: "new" | "reviewing" | "confirmed" | "dismissed"; assignee: string | null; score: number; reasons: string[]; citations: { evidence_id: number; event_id?: number; reference?: string }[]; comments: { id: number; body: string; author: string; created_at: string }[]; dismissal_reason: string | null };
export type MoneySupport = {
  evidence_id: number;
  file: string;
  reference: string;
  timestamp: string | null;
  sha256: string;
};
export type MoneyResult = {
  transactions: {
    event_id: number;
    timestamp: string | null;
    account: string;
    counterparty: string;
    direction: string;
    amount: number;
    currency: string;
    utr: string;
    vpa: string;
    ifsc: string;
    balance: number;
    support: MoneySupport;
    representations: MoneySupport[];
  }[];
  graph: {
    nodes: { id: string }[];
    edges: { source: string; target: string; amount: number; utr: string; support: MoneySupport[] }[];
    choke_points: { account: string; cut_paths: number; method: string }[];
    cycles: string[][];
    gnn_mule_detection: string;
  };
  patterns: {
    pass_through: { account: string; minutes: number; incoming_amount: number; outgoing_amount: number; support: MoneySupport[]; caveat: string }[];
    fan_in: { account: string; count: number; type: string }[];
    fan_out: { account: string; count: number; type: string }[];
    benford: Record<string, string | number>;
  };
  tracing: {
    rule: "fifo" | "proportional" | "lifo";
    available_rules: string[];
    directly_shown: { text: string; support: MoneySupport }[];
    possible: { amount: number; from_utr: string; to_utr: string; to: string; support: MoneySupport[]; status: string }[];
    unexplained: string[];
    solver: { engine: string; status: string; incomplete: boolean; reason: string; seed: number; time_limit_seconds: number };
    warning: string;
  };
  anomalies: { title: string; reason: string; confidence: number; support: MoneySupport; caveat: string }[];
};
let session: Session | null = null;
let refreshFlight: Promise<Session> | null = null;
let generation = 0;
const listeners = new Set<(value: Session | null) => void>();
function publish(value: Session | null) {
  session = value;
  listeners.forEach((listener) => listener(value));
}
export function subscribeSession(listener: (value: Session | null) => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
async function error(response: Response): Promise<Error> {
  let detail = "Request failed. Please try again.";
  try {
    const result = await response.json();
    if (typeof result.detail === "string") detail = result.detail;
    else if (Array.isArray(result.detail))
      detail = result.detail.map((e: { msg: string }) => e.msg).join("; ");
    else if (result.error?.message) detail = result.error.message;
  } catch {
    detail = `Request failed (${response.status}). Check the server connection.`;
  }
  return new Error(detail);
}
function validateSession(value: Session): Session {
  if (
    !value ||
    typeof value.access_token !== "string" ||
    !value.access_token ||
    !value.user ||
    !Number.isInteger(value.user.id) ||
    typeof value.user.username !== "string" ||
    !["admin", "investigator", "analyst", "prosecutor"].includes(
      value.user.role,
    )
  )
    throw new Error("Invalid sign-in response from server.");
  return value;
}
export async function signIn(credentials: LoginCredentials) {
  const body = new URLSearchParams(credentials);
  const response = await fetch("/api/v2/auth/login", {
    method: "POST",
    body,
    credentials: "same-origin",
  });
  if (!response.ok) throw await error(response);
  generation++;
  const value = validateSession((await response.json()) as Session);
  publish(value);
  return value;
}
export async function refreshSession() {
  if (!refreshFlight) {
    const version = generation;
    refreshFlight = (async () => {
      const response = await fetch("/api/v2/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
      });
      if (!response.ok) {
        if (version === generation) publish(null);
        throw await error(response);
      }
      const value = validateSession((await response.json()) as Session);
      if (version !== generation)
        throw new Error("Session changed. Sign in again.");
      publish(value);
      return value;
    })().finally(() => {
      refreshFlight = null;
    });
  }
  return refreshFlight;
}
export async function sessionRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!session) throw new Error("Sign in to continue.");
  const send = () =>
    fetch(path, {
      ...options,
      credentials: "same-origin",
      headers: {
        ...options.headers,
        Authorization: `Bearer ${session!.access_token}`,
      },
    });
  let response = await send();
  if (response.status === 401) {
    await refreshSession();
    response = await send();
  }
  if (!response.ok) throw await error(response);
  return response.json() as Promise<T>;
}
export async function signOut() {
  generation++;
  try {
    const response = await fetch("/api/v2/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
    if (!response.ok) throw await error(response);
  } finally {
    publish(null);
  }
}
export function forgetSession() {
  generation++;
  publish(null);
}
const json = (body: unknown) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const getCases = () => sessionRequest<CaseInfo[]>("/api/v2/cases");
export const getAccounts = () => sessionRequest<Account[]>("/api/v2/users");
export const createCase = (value: CaseInput) =>
  sessionRequest<CaseInfo>("/api/v2/cases", json(value));
export const getCase = (id: number) =>
  sessionRequest<CaseInfo>(`/api/v2/cases/${id}`);
export const getMembers = (id: number) =>
  sessionRequest<Member[]>(`/api/v2/cases/${id}/members`);
export const getAudit = (id: number) =>
  sessionRequest<Audit>(`/api/v2/cases/${id}/audit`);
export const putMember = (id: number, username: string, role: Role) =>
  sessionRequest(`/api/v2/cases/${id}/members`, json({ username, role }));
export const removeMember = (id: number, userId: number) =>
  sessionRequest(`/api/v2/cases/${id}/members/${userId}`, { method: "DELETE" });
export const createAccount = (username: string, password: string, role: Role) =>
  sessionRequest<Account>("/api/v2/users", json({ username, password, role }));
export const caseDashboard = (id: number) =>
  sessionRequest<DashboardData>(`/api/v1/cases/${id}/dashboard`);
export async function uploadEvidence(id: number, file: File, key: string) {
  const body = new FormData();
  body.append("file", file);
  await sessionRequest(`/api/v1/cases/${id}/evidence`, {
    method: "POST",
    body,
    headers: { "Idempotency-Key": key },
  });
}

export const getOwners = (caseId: number) =>
  sessionRequest<Owner[]>(`/api/v2/cases/${caseId}/owners`);
export const createOwner = (caseId: number, displayName: string, notes = "") =>
  sessionRequest<Owner>(
    `/api/v2/cases/${caseId}/owners`,
    json({ display_name: displayName, notes }),
  );
export const getDevices = (caseId: number) =>
  sessionRequest<Device[]>(`/api/v2/cases/${caseId}/devices`);
export const createDevice = (caseId: number, value: Omit<Device, "id">) =>
  sessionRequest<Device>(`/api/v2/cases/${caseId}/devices`, json(value));
export async function importEvidence(
  caseId: number,
  file: File,
  key: string,
  metadata: {
    sourceType: string;
    ownerId: number;
    deviceId: number | null;
    handedOverBy: string;
    acquiredAt: string;
    acquisitionMethod: string;
    note: string;
  },
) {
  const body = new FormData();
  body.append("file", file);
  body.append("source_type", metadata.sourceType);
  body.append("owner_id", String(metadata.ownerId));
  if (metadata.deviceId !== null)
    body.append("device_id", String(metadata.deviceId));
  body.append("handed_over_by", metadata.handedOverBy);
  body.append("acquired_at", metadata.acquiredAt);
  body.append("acquisition_method", metadata.acquisitionMethod);
  body.append("note", metadata.note);
  return sessionRequest<{ items: IntakeItem[]; duplicate_count: number }>(
    `/api/v2/cases/${caseId}/intake`,
    { method: "POST", body, headers: { "Idempotency-Key": key } },
  );
}
export const getIntakeJobs = (caseId: number) =>
  sessionRequest<IntakeJob[]>(`/api/v2/cases/${caseId}/intake/jobs`);
export const cancelIntakeJob = (caseId: number, jobId: number) =>
  sessionRequest<IntakeJob>(
    `/api/v2/cases/${caseId}/intake/jobs/${jobId}/cancel`,
    { method: "POST" },
  );
export const retryIntakeJob = (caseId: number, jobId: number) =>
  sessionRequest<IntakeJob>(
    `/api/v2/cases/${caseId}/intake/jobs/${jobId}/retry`,
    { method: "POST" },
  );
export const getImportReport = (caseId: number) =>
  sessionRequest<ImportReportData>(`/api/v2/cases/${caseId}/import-report`);
export const confirmImportReport = (caseId: number) =>
  sessionRequest<{ confirmed: boolean }>(
    `/api/v2/cases/${caseId}/import-report/confirm`,
    { method: "POST" },
  );
export const reparseEvidence = (
  caseId: number,
  evidenceId: number,
  dateOrder: "day_first" | "month_first",
) =>
  sessionRequest<{ job_id: number; status: string }>(
    `/api/v2/cases/${caseId}/evidence/${evidenceId}/reparse`,
    json({ date_order: dateOrder }),
  );
export const searchCaseEvents = (
  caseId: number,
  spec: {
    q?: string;
    regex?: string;
    phrases?: string[];
    time?: Record<string, string>;
    facets?: Record<string, string | boolean>;
    page?: { cursor?: number; limit?: number };
  },
) =>
  sessionRequest<SearchResult>(
    `/api/v2/cases/${caseId}/search/events`,
    json(spec),
  );
export const getEventDetail = (caseId: number, eventId: number) =>
  sessionRequest(`/api/v2/cases/${caseId}/events/${eventId}/detail`);
export const getIdentities = (caseId: number) =>
  sessionRequest<IdentityOverview>(`/api/v2/cases/${caseId}/identities`);
export const getModelCards = () => sessionRequest<ModelCard[]>("/api/v2/models");
export const getPatterns = (caseId: number) =>
  sessionRequest<PatternResult>(`/api/v2/cases/${caseId}/patterns`);
export const getMoneyAnalysis = (caseId: number, rule: string) =>
  sessionRequest<MoneyResult>(`/api/v2/cases/${caseId}/money?rule=${encodeURIComponent(rule)}`);
export const confirmAlias = (caseId: number, suggestionId: number) =>
  sessionRequest(
    `/api/v2/cases/${caseId}/alias-suggestions/${suggestionId}/confirm`,
    { method: "POST" },
  );
export const unmergeAlias = (caseId: number, suggestionId: number) =>
  sessionRequest(
    `/api/v2/cases/${caseId}/alias-suggestions/${suggestionId}/unmerge`,
    { method: "POST" },
  );

export const verifyLiveIntegrity = (id: number) =>
  sessionRequest<{ valid: boolean }>(`/api/v1/evidence/${id}/integrity`);
export const getCaseIntegrity = (caseId: number, rehash = false) =>
  sessionRequest<IntegrityResult>(`/api/v2/cases/${caseId}/integrity${rehash ? "/rehash" : ""}`, rehash ? { method: "POST" } : {});
export const runTamperDemo = (caseId: number, target: "file" | "audit") =>
  sessionRequest<{ target: string; detected: boolean; failed_at: string; detail: string }>(`/api/v2/cases/${caseId}/integrity/tamper-demo?target=${target}`, { method: "POST" });
export const getOriginAnalysis = (caseId: number) =>
  sessionRequest<OriginResult>(`/api/v2/cases/${caseId}/origin`);
export const getFraudReview = (caseId: number) =>
  sessionRequest<FraudReview>(`/api/v2/cases/${caseId}/fraud-review`);
export const updateFraudLead = (caseId: number, leadId: number, status: string, assignee?: string, comment?: string) =>
  sessionRequest<FraudReview>(`/api/v2/cases/${caseId}/leads/${leadId}`, json({ status, assignee: assignee || null, comment: comment || null }));
export async function downloadVerifiedBundle(caseId: number) {
  if (!session) throw new Error("Sign in to continue.");
  const send = () => fetch(`/api/v2/cases/${caseId}/integrity/export`, { method: "POST", credentials: "same-origin", headers: { Authorization: `Bearer ${session!.access_token}` } });
  let response = await send();
  if (response.status === 401) { await refreshSession(); response = await send(); }
  if (!response.ok) throw await error(response);
  const href = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a"); anchor.href = href; anchor.download = `parakh-case-${caseId}-verified.zip`; anchor.click();
  URL.revokeObjectURL(href);
}
