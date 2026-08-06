/** TypeScript type definitions for the agent-exec-trace API responses.
 *  Mirrors the Pydantic models from `api/models.py` and `api/queries.py` response shapes.
 */

export interface Span {
  span_id: string;
  parent_span_id: string | null;
  operation: string;
  name: string;
  start_time: string;
  end_time: string;
  status: string;
  attributes: Record<string, unknown>;
}

export interface Anomaly {
  id: string;
  anomaly_type: string;
  severity: "info" | "warning" | "critical";
  explanation: string;
  detected_at: string;
}

export interface RunTimelineResponse {
  run_id: string;
  agent_name: string;
  agent_version: string;
  status: string;
  duration_ms: number;
  estimated_cost: number;
  loop_count: number;
  loop_detected: boolean;
  started_at: string;
  completed_at: string;
  spans: Span[];
  anomalies: Anomaly[];
}

export interface FleetGroup {
  agent_name: string;
  agent_version: string;
  workload_type: string;
  total_runs: number;
  success_count: number;
  error_count: number;
  loop_count: number;
  anomaly_count: number;
  avg_duration_ms: number;
  avg_cost: number;
}

export interface FleetResponse {
  groups: FleetGroup[];
}

export interface VersionCohort {
  version: string;
  run_count: number;
}

export interface VersionDeltas {
  avg_cost_usd: number | null;
  retry_rate: number | null;
  success_rate: number | null;
}

export interface ToolDelta {
  tool_name: string;
  left_count: number;
  right_count: number;
  delta: number;
}

export interface CompareResponse {
  left: VersionCohort;
  right: VersionCohort;
  deltas: VersionDeltas;
  tool_deltas: ToolDelta[];
  warning?: string;
  note?: string;
}

export interface AnomalyItem {
  id: string;
  run_id: string;
  agent_name: string;
  anomaly_type: string;
  severity: string;
  explanation: string;
  detected_at: string;
}

export interface AnomalyListResponse {
  items: AnomalyItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  error: string;
  message: string;
}