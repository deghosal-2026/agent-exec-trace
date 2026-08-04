/** TypeScript type definitions for the agent-exec-trace API responses.
 *
 * Mirrors the Pydantic models from `api/models.py` on the backend.
 * Imported by the API client, hooks, and page components.
 */

/** A single span in a run's trace tree. */
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

/** An anomaly detected on a run. */
export interface Anomaly {
  id: string;
  anomaly_type: "loop" | "retry_storm" | "cost_spike";
  severity: "info" | "warning" | "critical";
  explanation: string;
  detected_at: string;
}

/** Full timeline response for a single run. */
export interface RunTimelineResponse {
  run_id: string;
  agent_name: string;
  agent_version: string;
  status: "success" | "error" | "loop";
  duration_ms: number;
  estimated_cost: number;
  loop_count: number;
  loop_detected: boolean;
  started_at: string;
  completed_at: string;
  spans: Span[];
  anomalies: Anomaly[];
}

/** A single group in the fleet health view. */
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

/** Fleet health API response. */
export interface FleetResponse {
  groups: FleetGroup[];
}

/** Per-version statistics for version comparison. */
export interface VersionStats {
  version: string;
  total_runs: number;
  success_count: number;
  avg_cost: number;
  avg_duration_ms: number;
  total_retries: number;
  top_tools: Record<string, number>;
}

/** Version comparison API response. */
export interface CompareResponse {
  version_a: VersionStats;
  version_b: VersionStats;
  cost_delta_pct: number;
  retry_delta_pct: number;
  duration_delta_pct: number;
}

/** A single anomaly in the anomaly inbox list. */
export interface AnomalyItem {
  id: string;
  run_id: string;
  agent_name: string;
  anomaly_type: string;
  severity: string;
  explanation: string;
  detected_at: string;
}

/** Paginated anomaly list response. */
export interface AnomalyListResponse {
  items: AnomalyItem[];
  total: number;
  limit: number;
  offset: number;
}

/** Standard API error shape. */
export interface ApiError {
  error: string;
  message: string;
}