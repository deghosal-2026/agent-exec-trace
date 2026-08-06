/**
 * API client normalization tests.
 *
 * Tests the internal normalization logic of the ApiClient class,
 * verifying that raw API responses are correctly transformed into
 * the shapes expected by React components.
 *
 * ## Strategy
 * Each test mocks the global `fetch` function (via `vi.stubGlobal`) to
 * simulate a specific API response. The module under test (`api/client.ts`)
 * is dynamically imported after stubbing to ensure the mock is in place.
 * Mocks are restored after each test via `vi.restoreAllMocks()`.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

// Restore all mocks after each test to prevent cross-test contamination
afterEach(() => {
  vi.restoreAllMocks();
});

describe("api client normalization", () => {
  /**
   * Guards against a common proxy/nginx misconfiguration where a 200 OK
   * response returns HTML instead of JSON.
   *
   * The client should throw a descriptive error containing the request path
   * and the received content type, helping operators diagnose routing issues.
   */
  it("surfaces the request path when a successful response is HTML instead of JSON", async () => {
    // Simulate a proxy returning an HTML fallback page with 200 OK
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? "text/html" : null) },
      text: async () => '<!doctype html><html><body>fallback</body></html>',
    });
    vi.stubGlobal("fetch", fetchMock);

    // Dynamic import to pick up the mocked fetch
    const { api } = await import("../api/client");

    // The error message must include the request path and the unexpected content type
    await expect(api.getFleet()).rejects.toThrow(
      "Expected JSON from /api/v1/fleet but received text/html"
    );
  });

  /**
   * Verifies fleet response normalization.
   *
   * The raw fleet API returns rows with `run_count` and `success_rate`.
   * The client derives `success_count` (= round(run_count × success_rate))
   * and `error_count` (= run_count − success_count), and fills in defaults
   * for `loop_count` (0) and `avg_duration_ms` (0).
   */
  it("normalizes fleet responses into dashboard groups", async () => {
    // Mock fleet response with a single row
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

    // Verify normalized shape: success_count = round(12 × 0.75) = 9
    expect(result.groups).toEqual([
      {
        agent_name: "research_crew",
        agent_version: "v1.3.0",
        workload_type: "research_crew",
        total_runs: 12,
        success_count: 9,
        error_count: 3,       // 12 − 9
        loop_count: 0,        // default
        anomaly_count: 4,
        avg_duration_ms: 0,   // default
        avg_cost: 1.25,       // from avg_cost_usd
      },
    ]);

    // Verify the request was made correctly (Content-Type header)
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/fleet",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      })
    );
  });

  /**
   * Verifies anomaly list response normalization.
   *
   * The raw anomaly API uses `anomaly_id` and `type` field names, with
   * page-based pagination (`meta.page`). The client:
   * - Coalesces `anomaly_id` → `id`, `type` → `anomaly_type`
   * - Coalesces `created_at` → `detected_at`
   * - Converts page-based to offset-based pagination
   */
  it("normalizes anomaly list responses", async () => {
    // Mock page 2 response with one anomaly item
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

    // Verify: anomaly_id → id, type → anomaly_type, created_at → detected_at
    // offset = (page - 1) × page_size = (2 - 1) × 50 = 50
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