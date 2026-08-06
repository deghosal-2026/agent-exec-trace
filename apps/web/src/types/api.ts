/**
 * TypeScript type definitions for the agent-exec-trace API responses.
 *
 * Mirrors the Pydantic models from `api/models.py` and `api/queries.py`
 * response shapes. These types represent the normalized data the API client
 * returns to React components (not the raw wire format).
 *
 * ## Organization
 * - **Core entities**: Span, Anomaly — represent individual trace events
 * - **Run-level responses**: RunTimelineResponse — full trace for a single run
 * - **Fleet-level responses**: FleetGroup, FleetResponse — aggregated fleet health
 * - **Comparison responses**: VersionCohort, VersionDeltas, ToolDelta, CompareResponse
 * - **List responses**: AnomalyItem, AnomalyListResponse — paginated lists
 * - **Error responses**: ApiError — normalized error shape
 */

/**
 * Represents a single span in an agent execution trace.
 *
 * Spans form a tree structure via `parent_span_id`: root spans have `null` parent,
 * child spans reference their parent. Each span records an atomic operation
 * (e.g. "invoke_agent", "execute_tool") with timing and metadata.
 */
export interface Span {
  /** Unique span identifier within the trace. */
  span_id: string;
  /** Parent span ID, or null for root spans. */
  parent_span_id: string | null;
  /** Operation type (e.g. "invoke_agent", "execute_tool", "retrieval"). */
  operation: string;
  /** Human-readable span name describing the operation. */
  name: string;
  /** ISO 8601 timestamp when the span started. */
  start_time: string;
  /** ISO 8601 timestamp when the span completed. */
  end_time: string;
  /** Span-level status (e.g. "success", "error"). */
  status: string;
  /** Arbitrary key-value metadata attached to the span. */
  attributes: Record<string, unknown>;
}

/**
 * Represents a detected anomaly within a run or span.
 *
 * Anomalies are flagged by the detector pipeline and carry a severity level,
 * machine-readable type, and human-readable explanation.
 */
export interface Anomaly {
  /** Unique anomaly identifier. */
  id: string;
  /** Anomaly classification (e.g. "loop", "retry_storm", "cost_spike"). */
  anomaly_type: string;
  /** Severity level: informational, warning, or critical. */
  severity: "info" | "warning" | "critical";
  /** Human-readable explanation of what was detected. */
  explanation: string;
  /** ISO 8601 timestamp when the anomaly was detected. */
  detected_at: string;
}

/**
 * Normalized response from GET /api/v1/runs/:runId.
 *
 * Contains the full execution trace: run metadata, span tree, and all
 * anomalies detected during this run.
 */
export interface RunTimelineResponse {
  /** The run's unique identifier. */
  run_id: string;
  /** Name of the agent that executed this run. */
  agent_name: string;
  /** Version string of the agent at execution time. */
  agent_version: string;
  /** Overall run status (e.g. "success", "error"). */
  status: string;
  /** Total wall-clock duration in milliseconds. */
  duration_ms: number;
  /** Estimated cost in USD for this run. */
  estimated_cost: number;
  /** Count of loop-type anomalies detected. */
  loop_count: number;
  /** Whether a loop was detected during this run. */
  loop_detected: boolean;
  /** ISO 8601 timestamp when the run started (empty string if unknown). */
  started_at: string;
  /** ISO 8601 timestamp when the run completed (empty string if unknown). */
  completed_at: string;
  /** All spans in the execution trace (flat array; tree built client-side). */
  spans: Span[];
  /** All anomalies detected during this run. */
  anomalies: Anomaly[];
}

/**
 * Aggregated fleet health data for one agent/version/workload combination.
 *
 * Represents a rollup of all runs matching a specific (agent_name, agent_version,
 * workload_type) tuple.
 */
export interface FleetGroup {
  /** Agent name. */
  agent_name: string;
  /** Agent version string. */
  agent_version: string;
  /** Workload type classification. */
  workload_type: string;
  /** Total number of runs in this group. */
  total_runs: number;
  /** Number of successful runs. */
  success_count: number;
  /** Number of failed runs. */
  error_count: number;
  /** Number of loop-affected runs. */
  loop_count: number;
  /** Total anomaly count across all runs in this group. */
  anomaly_count: number;
  /** Average run duration in milliseconds. */
  avg_duration_ms: number;
  /** Average cost per run in USD. */
  avg_cost: number;
}

/**
 * Normalized response from GET /api/v1/fleet.
 */
export interface FleetResponse {
  /** Array of fleet groups, one per agent/version/workload combination. */
  groups: FleetGroup[];
}

/**
 * Represents one side of a version comparison (left or right cohort).
 */
export interface VersionCohort {
  /** Version label (e.g. "v1.0.0"). */
  version: string;
  /** Number of runs sampled for this cohort. */
  run_count: number;
}

/**
 * Delta values between two version cohorts.
 *
 * Positive values mean the right cohort (Version B) has higher values
 * than the left cohort (Version A).
 */
export interface VersionDeltas {
  /** Difference in average cost (USD). */
  avg_cost_usd: number | null;
  /** Difference in retry rate (0-1 scale). */
  retry_rate: number | null;
  /** Difference in success rate (0-1 scale). */
  success_rate: number | null;
}

/**
 * Per-tool usage delta between two version cohorts.
 *
 * Tracks how usage of a specific tool changed between versions.
 */
export interface ToolDelta {
  /** Tool name. */
  tool_name: string;
  /** Invocation count in the left (A) cohort. */
  left_count: number;
  /** Invocation count in the right (B) cohort. */
  right_count: number;
  /** Absolute difference (right_count - left_count). */
  delta: number;
}

/**
 * Normalized response from GET /api/v1/compare.
 *
 * Contains left/right cohort data, global deltas, per-tool deltas,
 * and optional warning information for sparse data scenarios.
 */
export interface CompareResponse {
  /** Left (baseline) cohort data. */
  left: VersionCohort;
  /** Right (comparison) cohort data. */
  right: VersionCohort;
  /** Global deltas between cohorts. */
  deltas: VersionDeltas;
  /** Per-tool usage deltas. */
  tool_deltas: ToolDelta[];
  /** Optional warning flag indicating sparse/insufficient data. */
  warning?: string;
  /** Optional advisory note to display alongside the warning. */
  note?: string;
}

/**
 * A single anomaly item in the paginated anomaly list.
 *
 * Includes the associated run_id and agent_name for navigation context.
 */
export interface AnomalyItem {
  /** Unique anomaly identifier. */
  id: string;
  /** The run ID associated with this anomaly. */
  run_id: string;
  /** The agent name associated with this anomaly. */
  agent_name: string;
  /** Anomaly classification. */
  anomaly_type: string;
  /** Severity level. */
  severity: string;
  /** Human-readable explanation. */
  explanation: string;
  /** ISO 8601 timestamp of detection. */
  detected_at: string;
}

/**
 * Normalized paginated response from GET /api/v1/anomalies.
 *
 * Uses offset-based pagination (converted from the API's page-based format).
 */
export interface AnomalyListResponse {
  /** Array of anomaly items for the current page. */
  items: AnomalyItem[];
  /** Total number of anomalies matching the filters. */
  total: number;
  /** Page size (limit). */
  limit: number;
  /** Zero-based offset for the current page. */
  offset: number;
}

/**
 * Standardized error response shape.
 *
 * Returned by the API on non-2xx responses. Not directly used by the client
 * (errors are thrown as `Error`), but documented for completeness.
 */
export interface ApiError {
  /** Machine-readable error code. */
  error: string;
  /** Human-readable error message. */
  message: string;
}