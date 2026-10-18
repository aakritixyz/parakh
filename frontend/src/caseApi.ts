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

export const verifyLiveIntegrity = (id: number) =>
  sessionRequest<{ valid: boolean }>(`/api/v1/evidence/${id}/integrity`);
