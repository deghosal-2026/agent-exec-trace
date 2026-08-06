/** API client for the agent-exec-trace REST API.
 *
 * Provides typed methods for each API endpoint. The browser defaults to
 * relative `/api` requests so Vite's proxy works in local Docker and host-dev.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "";

type FleetApiRow = {
  agent_name: string;
  agent_version: string;
  workload_type: string;
  run_count: number;
  success_rate: number;
  avg_cost_usd: number | null;
  anomaly_count: number;
};

type FleetApiResponse = {
  data: { rows: FleetApiRow[] };
};

type TimelineApiResponse = {
  run: {
    run_id: string;
    agent_name: string;
    agent_version: string;
    status: string;
    estimated_cost_usd?: number | null;
  };
  summary: {
    duration_ms: number;
    loop_detected: boolean;
  };
  spans: import("../types/api").Span[];
  anomalies: Array<{
    anomaly_id?: string;
    id?: string;
    type?: string;
    anomaly_type?: string;
    severity: "info" | "warning" | "critical";
    explanation: string;
    created_at?: string;
    detected_at?: string;
  }>;
};

type AnomaliesApiResponse = {
  data: { items: Array<{
    anomaly_id?: string;
    id?: string;
    type?: string;
    anomaly_type?: string;
    severity: string;
    agent_name: string;
    run_id: string;
    explanation: string;
    created_at?: string;
    detected_at?: string;
  }>; };
  meta: { total: number; page: number; page_size: number };
};

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  /** Generic request handler with JSON parsing and error normalization. */
  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });

    const contentType = res.headers.get("content-type") ?? "";
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message =
        (body as { message?: string }).message ??
        `Request failed: ${res.status} ${res.statusText}`;
      throw new Error(message);
    }

    if (!contentType.includes("application/json")) {
      const body = await res.text().catch(() => "");
      const preview = body.slice(0, 80).replace(/\s+/g, " ").trim();
      throw new Error(
        `Expected JSON from ${path} but received ${contentType || "unknown content type"}${preview ? `: ${preview}` : ""}`
      );
    }

    return res.json() as Promise<T>;
  }

  /** Fetch the full timeline for a single run. */
  getRunTimeline(runId: string) {
    return this.request<TimelineApiResponse>(`/api/v1/runs/${encodeURIComponent(runId)}`).then((data) => ({
      run_id: data.run.run_id,
      agent_name: data.run.agent_name,
      agent_version: data.run.agent_version,
      status: data.run.status,
      duration_ms: data.summary.duration_ms,
      estimated_cost: data.run.estimated_cost_usd ?? 0,
      loop_count: data.anomalies.filter((a) => (a.type ?? a.anomaly_type) === "loop").length,
      loop_detected: data.summary.loop_detected,
      started_at: "",
      completed_at: "",
      spans: data.spans,
      anomalies: data.anomalies.map((a) => ({
        id: a.anomaly_id ?? a.id ?? "",
        anomaly_type: a.type ?? a.anomaly_type ?? "unknown",
        severity: a.severity,
        explanation: a.explanation,
        detected_at: a.created_at ?? a.detected_at ?? "",
      })),
    }));
  }

  /** Fetch fleet health rollups, optionally filtered. */
  getFleet(params?: {
    agent_name?: string;
    version?: string;
    workload_type?: string;
  }) {
    const qs = new URLSearchParams();
    if (params?.agent_name) qs.set("agent_name", params.agent_name);
    if (params?.version) qs.set("version", params.version);
    if (params?.workload_type) qs.set("workload_type", params.workload_type);
    const q = qs.toString();
    return this.request<FleetApiResponse>(`/api/v1/fleet${q ? `?${q}` : ""}`).then((data) => ({
      groups: data.data.rows.map((row) => {
        const successCount = Math.round(row.run_count * row.success_rate);
        return {
          agent_name: row.agent_name,
          agent_version: row.agent_version,
          workload_type: row.workload_type,
          total_runs: row.run_count,
          success_count: successCount,
          error_count: row.run_count - successCount,
          loop_count: 0,
          anomaly_count: row.anomaly_count,
          avg_duration_ms: 0,
          avg_cost: row.avg_cost_usd ?? 0,
        };
      }),
    }));
  }

  /** Compare two version cohorts side by side. */
  getCompare(params: {
    agent_name?: string;
    version_a: string;
    version_b: string;
  }) {
    const qs = new URLSearchParams({ version_a: params.version_a, version_b: params.version_b });
    if (params.agent_name) qs.set("agent_name", params.agent_name);
    return this.request<import("../types/api").CompareResponse>(
      `/api/v1/compare?${qs.toString()}`
    );
  }

  /** Fetch paginated anomalies, optionally filtered. */
  getAnomalies(params?: {
    severity?: string;
    anomaly_type?: string;
    agent_name?: string;
    limit?: number;
    offset?: number;
  }) {
    const qs = new URLSearchParams();
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.anomaly_type) qs.set("anomaly_type", params.anomaly_type);
    if (params?.agent_name) qs.set("agent_name", params.agent_name);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return this.request<AnomaliesApiResponse>(`/api/v1/anomalies${q ? `?${q}` : ""}`).then((data) => ({
      items: data.data.items.map((item) => ({
        id: item.anomaly_id ?? item.id ?? "",
        run_id: item.run_id,
        agent_name: item.agent_name,
        anomaly_type: item.type ?? item.anomaly_type ?? "unknown",
        severity: item.severity,
        explanation: item.explanation,
        detected_at: item.created_at ?? item.detected_at ?? "",
      })),
      total: data.meta.total,
      limit: data.meta.page_size,
      offset: (data.meta.page - 1) * data.meta.page_size,
    }));
  }

  /** Check API health. */
  getHealth() {
    return this.request<{ status: string }>("/api/v1/health");
  }
}

export const api = new ApiClient(BASE_URL);
