/** API client for the agent-exec-trace REST API.
 *
 * Provides typed methods for each API endpoint.  The base URL is read from
 * the Vite env var `VITE_API_URL` at import time, with a fallback to localhost:8000.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message =
        (body as { message?: string }).message ??
        `Request failed: ${res.status} ${res.statusText}`;
      throw new Error(message);
    }
    return res.json() as Promise<T>;
  }

  /** Fetch the full timeline for a single run. */
  getRunTimeline(runId: string) {
    return this.request<import("../types/api").RunTimelineResponse>(
      `/api/v1/runs/${encodeURIComponent(runId)}`
    );
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
    return this.request<import("../types/api").FleetResponse>(
      `/api/v1/fleet${q ? `?${q}` : ""}`
    );
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
    return this.request<import("../types/api").AnomalyListResponse>(
      `/api/v1/anomalies${q ? `?${q}` : ""}`
    );
  }

  /** Check API health. */
  getHealth() {
    return this.request<{ status: string }>("/api/v1/health");
  }
}

export const api = new ApiClient(BASE_URL);