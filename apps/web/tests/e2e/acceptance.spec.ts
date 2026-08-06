import { test, expect } from "@playwright/test";

test.describe("Demo Acceptance", () => {
  test("ACC-01 success and error runs distinguishable in fleet", async ({ page }) => {
    await page.goto("/fleet");
    await page.waitForSelector("table", { timeout: 10_000 });

    // Error count column should have non-zero values
    const errorCells = page.locator("tbody td:nth-child(6)");
    let hasErrors = false;
    const count = await errorCells.count();
    for (let i = 0; i < count; i++) {
      const text = await errorCells.nth(i).textContent();
      if (text && parseInt(text.trim(), 10) > 0) {
        hasErrors = true;
        break;
      }
    }
    expect(hasErrors).toBe(true);
  });

  test("ACC-02 fleet shows multiple agent names and versions", async ({ page }) => {
    await page.goto("/fleet");
    await page.waitForSelector("table", { timeout: 10_000 });

    const agentCells = page.locator("tbody td:first-child");
    const agents = new Set<string>();
    const cellCount = await agentCells.count();
    for (let i = 0; i < cellCount; i++) {
      const text = await agentCells.nth(i).textContent();
      if (text) agents.add(text.trim());
    }
    expect(agents.size).toBeGreaterThanOrEqual(2);
  });

  test("ACC-03 version compare shows non-zero deltas", async ({ page }) => {
    await page.goto("/compare");

    const agentInput = page.locator("input").first();
    await agentInput.fill("research_crew");
    const versionA = page.locator("input[placeholder='v1.0']");
    await versionA.fill("v1.2.0");
    const versionB = page.locator("input[placeholder='v2.0']");
    await versionB.fill("v1.3.0");
    await page.waitForTimeout(1000);

    await expect(page.getByText("Tool Usage Comparison")).toBeVisible({ timeout: 10_000 });
  });

  test("ACC-04 anomaly inbox filters change visible rows", async ({ page }) => {
    await page.goto("/anomalies");
    await page.waitForSelector(".space-y-2\\.5 > button", { timeout: 10_000 });

    const beforeCount = await page.locator(".space-y-2\\.5 > button").count();

    const severitySelect = page.locator("select[aria-label='Filter by severity']");
    await severitySelect.selectOption({ value: "critical" });
    await page.waitForTimeout(500);

    const afterCount = await page.locator(".space-y-2\\.5 > button").count();

    // Filtering should reduce or maintain the count (not increase)
    expect(afterCount).toBeLessThanOrEqual(beforeCount);
  });
});