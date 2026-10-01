import type { AuthenticityReport, Evidence, EventItem, GraphEdge, GraphNode } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export type DashboardData = {
  online: boolean;
  summary?: {
    evidence_count: number;
    event_count: number;
    risk_score: number;
    audit_chain_valid: boolean;
    source_counts: Record<string, number>;
    phase_counts: Record<string, number>;
  };
  evidence: Evidence[];
  timeline: EventItem[];
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  fraud: Array<Record<string, unknown>>;
  anomalies: Array<Record<string, unknown>>;
  reconstruction: {
    phases: string[];
    narrative: string;
    gaps: string[];
    citation_verification?: { valid: boolean };
  };
  authenticity: AuthenticityReport[];
  audit?: { valid?: boolean; entries?: number; tip_hash?: string };
  collaboration?: { lead_counts?: Record<string, number>; comments?: unknown[]; leads?: unknown[] };
};

async function getJson<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

async function login(): Promise<string> {
  const body = new URLSearchParams();
  body.set("username", "admin");
  body.set("password", "admin123");
  const response = await fetch(`${API_BASE}/auth/token`, {
    method: "POST",
    body
  });
  if (!response.ok) {
    throw new Error("Backend login failed");
  }
  const data = (await response.json()) as { access_token: string };
  return data.access_token;
}

export async function loadDashboard(caseId = 1): Promise<DashboardData> {
  try {
    const token = await login();
    try {
      const dashboard = await getJson<Omit<DashboardData, "online">>(
        `/cases/${caseId}/dashboard`,
        token
      );
      return { online: true, ...dashboard };
    } catch {
      // Older backend fallback follows.
    }
    const evidence = await getJson<Evidence[]>(`/cases/${caseId}/evidence`, token);
    const timeline = await getJson<EventItem[]>(`/cases/${caseId}/timeline`, token);
    const graph = await getJson<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
      `/cases/${caseId}/graph`,
      token
    );
    const fraud = await getJson<Array<Record<string, unknown>>>(`/cases/${caseId}/fraud`, token);
    const anomalies = await getJson<Array<Record<string, unknown>>>(
      `/cases/${caseId}/anomalies`,
      token
    );
    const reconstruction = await getJson<DashboardData["reconstruction"]>(
      `/cases/${caseId}/reconstruction`,
      token
    );
    const authenticity = await Promise.all(
      evidence.slice(0, 4).map((item) =>
        getJson<AuthenticityReport>(`/evidence/${item.id}/authenticity`, token)
      )
    );
    return { online: true, evidence, timeline, graph, fraud, anomalies, reconstruction, authenticity };
  } catch {
    return fallbackDashboard;
  }
}

export const fallbackDashboard: DashboardData = {
  online: false,
  summary: {
    evidence_count: 7,
    event_count: 28,
    risk_score: 86,
    audit_chain_valid: true,
    source_counts: {
      whatsapp_chat: 1,
      bank_upi_statement: 1,
      gps: 1,
      pdf: 1,
      image: 2,
      browser_history: 1
    },
    phase_counts: {
      lure_or_credential_capture: 2,
      financial_transfer: 3,
      movement: 1,
      communications: 4
    }
  },
  evidence: [
    {
      id: 1,
      filename: "whatsapp_investment_scam.txt",
      source_type: "whatsapp_chat",
      sha256: "7fb1...c91e",
      size_bytes: 1240
    },
    {
      id: 2,
      filename: "upi_bank_statement.csv",
      source_type: "bank_upi_statement",
      sha256: "84ac...9e21",
      size_bytes: 982
    },
    {
      id: 3,
      filename: "gps_location_takeout.json",
      source_type: "gps",
      sha256: "1fe4...a13b",
      size_bytes: 520
    },
    {
      id: 4,
      filename: "suspicious_receipt.pdf",
      source_type: "pdf",
      sha256: "41da...7f02",
      size_bytes: 1612
    }
  ],
  timeline: [
    {
      event_id: 10,
      evidence_id: 1,
      timestamp_utc: "2026-09-12T03:40:00Z",
      phase: "lure_or_credential_capture",
      action: "message",
      summary: "Guaranteed return investment plan sent with KYC update link"
    },
    {
      event_id: 12,
      evidence_id: 1,
      timestamp_utc: "2026-09-12T03:47:00Z",
      phase: "lure_or_credential_capture",
      action: "message",
      summary: "Victim asked to enter OTP urgently"
    },
    {
      event_id: 22,
      evidence_id: 2,
      timestamp_utc: "2026-09-12T03:55:00Z",
      phase: "financial_transfer",
      action: "debit",
      summary: "INR 25,000 transferred to arjun@upi"
    },
    {
      event_id: 25,
      evidence_id: 2,
      timestamp_utc: "2026-09-12T04:17:00Z",
      phase: "financial_transfer",
      action: "pass-through",
      summary: "Funds moved from mule account to cashout@upi"
    }
  ],
  graph: {
    nodes: [
      { id: "Riya", centrality: 0.9 },
      { id: "Agent Arjun", centrality: 0.84 },
      { id: "arjun@upi", centrality: 0.78 },
      { id: "cashout@upi", centrality: 0.48 },
      { id: "+919876543210", centrality: 0.44 }
    ],
    edges: [
      { source: "Riya", target: "Agent Arjun", weight: 7 },
      { source: "Agent Arjun", target: "arjun@upi", weight: 4 },
      { source: "arjun@upi", target: "cashout@upi", weight: 2 },
      { source: "+919876543210", target: "Agent Arjun", weight: 1 }
    ]
  },
  fraud: [
    { type: "scam_language", rule: "guaranteed return", explanation: "Common investment scam phrase" },
    { type: "mule_account_fan_in", upi: "arjun@upi", features: { mentions: 4 } }
  ],
  anomalies: [
    { type: "communication_burst", actor: "Agent Arjun", features: { count: 8, day: "2026-09-12" } },
    { type: "odd_hours", event_id: 12, features: { hour_utc: 3 } }
  ],
  reconstruction: {
    phases: ["lure_or_credential_capture", "financial_transfer", "movement"],
    narrative:
      "The suspect contact initiated a high-pressure investment pitch, moved the victim to a fake KYC flow, then directed two UPI transfers to the same beneficiary with rapid pass-through behavior.",
    gaps: ["Need bank KYC details for mule account.", "Need device-origin confirmation for chat export."],
    citation_verification: { valid: true }
  },
  authenticity: [
    {
      evidence_id: 1,
      score: 82,
      findings: [{ severity: "low", explanation: "Chat export has expected format.", signal: "format_consistent" }]
    },
    {
      evidence_id: 4,
      score: 62,
      findings: [
        {
          severity: "high",
          explanation: "PDF has multiple EOF markers suggesting incremental updates.",
          signal: "eof_count=3"
        }
      ]
    }
  ],
  audit: { valid: true, entries: 11, tip_hash: "f2c8...91aa" },
  collaboration: { lead_counts: { suggested: 4, accepted: 1, rejected: 0 } }
};
