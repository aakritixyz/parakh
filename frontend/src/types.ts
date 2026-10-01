export type Evidence = {
  id: number;
  filename: string;
  source_type: string;
  sha256: string;
  size_bytes: number;
  created_at?: string;
};

export type EventItem = {
  event_id?: number;
  id?: number;
  evidence_id: number;
  timestamp_utc?: string | null;
  phase?: string;
  action: string;
  summary?: string;
  content?: string;
};

export type GraphNode = {
  id: string;
  centrality: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  weight: number;
};

export type AuthenticityFinding = {
  severity: "low" | "medium" | "high" | "critical";
  explanation: string;
  signal: string;
};

export type AuthenticityReport = {
  evidence_id: number;
  score: number;
  findings: AuthenticityFinding[];
  stub_detectors?: string[];
};
