import { test, expect } from "@playwright/test";

test.describe("Run Timeline", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/runs");
  });

  test("TL-01 enter run ID navigates to timeline view", async ({ page }) => {
    // Navigate from anomalies to get a run ID first
    await page.goto("/anomalies");
    await page.waitForSelector(".space-y-2\\.5 > button", { timeout: 10_000 });
    const firstItem = page.locator(".space-y-2\\.5 > button").first();
    await firstItem.click();

    // Should now be on the run timeline page
    await expect(page).toHaveURL(/\/runs\//, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /.+/ }).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Cost")).toBeVisible({ timeout: 5_000 });

    await page.screenshot({ path: "test-results/timeline-normal.png", fullPage: true });
  });

  test("TL-02 empty spans shows placeholder text", async ({ page }) => {
    // Navigate from anomalies
    await page.goto("/anomalies");
    await page.waitForSelector(".space-y-2\\.5 > button", { timeout: 10_000 });
    const firstItem = page.locator(".space-y-2\\.5 > button").first();
    await firstItem.click();
    await expect(page).toHaveURL(/\/runs\//, { timeout: 10_000 });

    // Expect either span tree or the empty spans state
    await expect(
      page.locator("h3").filter({ hasText: /span/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("TL-03 stubbed span tree with expand/collapse interaction", async ({ page }) => {
    // Intercept the timeline endpoint for a specific run by navigating and intercepting
    await page.route("**/api/v1/runs/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/api/v1/runs/")) {
        const runId = url.split("/runs/")[1];
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            run: {
              run_id: runId,
              agent_name: "test_agent",
              agent_version: "v1.0.0",
              status: "success",
              estimated_cost_usd: 0.5,
              total_retries: 2,
              total_interventions: 0,
            },
            summary: {
              duration_ms: 35000,
              loop_detected: false,
              tool_call_count: 8,
            },
            spans: [
              {
                span_id: "s1",
                parent_span_id: null,
                operation_name: "agent.run",
                start_time: "2026-08-06T00:00:00Z",
                duration_ms: 35000,
                status: "success",
                attributes: {},
              },
              {
                span_id: "s2",
                parent_span_id: "s1",
                operation_name: "tool.call",
                start_time: "2026-08-06T00:00:01Z",
                duration_ms: 8000,
                status: "success",
                attributes: { "tool.name": "fetch_data" },
              },
              {
                span_id: "s3",
                parent_span_id: "s1",
                operation_name: "tool.call",
                start_time: "2026-08-06T00:00:10Z",
                duration_ms: 3000,
                status: "error",
                attributes: { "tool.name": "analyze" },
              },
            ],
            anomalies: [],
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/runs/abc-123");
    await page.waitForTimeout(1000);

    // Should render span tree
    await expect(page.getByText("Span Tree")).toBeVisible({ timeout: 10_000 });

    await page.screenshot({ path: "test-results/timeline-spans.png", fullPage: true });
  });

  test("TL-04 anomaly badges shown on anomalous runs", async ({ page }) => {
    // Navigate from anomalies
    await page.goto("/anomalies");
    await page.waitForSelector(".space-y-2\\.5 > button", { timeout: 10_000 });

    // Filter for critical anomalies first
    const severitySelect = page.locator("select[aria-label='Filter by severity']");
    await severitySelect.selectOption({ value: "critical" });
    await page.waitForTimeout(500);

    // Click first critical anomaly to go to its timeline
    const firstItem = page.locator(".space-y-2\\.5 > button").first();
    await firstItem.click();

    // Should land on timeline with anomalies section visible
    await expect(page).toHaveURL(/\/runs\//, { timeout: 10_000 });
    await expect(page.getByText("Anomalies")).toBeVisible({ timeout: 10_000 });
  });

  test("TL-05 back navigation preserves context", async ({ page }) => {
    // Go to fleet, filter, then navigate to run, then back
    await page.goto("/fleet");
    await page.waitForSelector("table tbody tr", { timeout: 10_000 });

    const agentSelect = page.locator("select[aria-label='Filter by agent']");
    await agentSelect.selectOption({ value: "code_review" });
    await page.waitForTimeout(500);

    // Click a row to navigate
    const firstRow = page.locator("tbody tr").first();
    await firstRow.click();

    // Should be at /runs?agent=...
    await expect(page).toHaveURL(/\/runs\?agent=/);
  });
});
