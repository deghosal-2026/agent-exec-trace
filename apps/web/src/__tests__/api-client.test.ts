import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api client normalization", () => {
  it("surfaces the request path when a successful response is HTML instead of JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? "text/html" : null) },
      text: async () => '<!doctype html><html><body>fallback</body></html>',
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("../api/client");

    await expect(api.getFleet()).rejects.toThrow(
      "Expected JSON from /api/v1/fleet but received text/html"
    );
  });

  it("normalizes fleet responses into dashboard groups", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({
        data: {
          rows: [
            {
              agent_name: "research_crew",
              agent_version: "v1.3.0",
              workload_type: "research_crew",
              run_count: 12,
              success_rate: 0.75,
              avg_cost_usd: 1.25,
              anomaly_count: 4,
            },
          ],
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("../api/client");
    const result = await api.getFleet();

    expect(result.groups).toEqual([
      {
        agent_name: "research_crew",
        agent_version: "v1.3.0",
        workload_type: "research_crew",
        total_runs: 12,
        success_count: 9,
        error_count: 3,
        loop_count: 0,
        anomaly_count: 4,
        avg_duration_ms: 0,
        avg_cost: 1.25,
      },
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/fleet",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      })
    );
  });

  it("normalizes anomaly list responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({
        data: {
          items: [
            {
              anomaly_id: "a1",
              type: "loop",
              severity: "critical",
              agent_name: "research_crew",
              run_id: "r1",
              explanation: "loop detected",
              created_at: "2026-08-06T00:00:00Z",
            },
          ],
        },
        meta: { total: 1, page: 2, page_size: 50 },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("../api/client");
    const result = await api.getAnomalies({ limit: 50, offset: 50 });

    expect(result).toEqual({
      items: [
        {
          id: "a1",
          run_id: "r1",
          agent_name: "research_crew",
          anomaly_type: "loop",
          severity: "critical",
          explanation: "loop detected",
          detected_at: "2026-08-06T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 50,
    });
  });
});
