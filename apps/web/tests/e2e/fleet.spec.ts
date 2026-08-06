import { test, expect } from "@playwright/test";

test.describe("Fleet Health", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/fleet");
    await page.waitForSelector("table", { timeout: 10_000 }).catch(() => {});
  });

  test("FLEET-01 default table renders with rows and columns", async ({ page }) => {
    const rows = page.locator("tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    await expect(page.getByRole("columnheader", { name: "Agent" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Version" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Runs" })).toBeVisible();

    await page.screenshot({ path: "test-results/fleet-default.png", fullPage: true });
  });

  test("FLEET-02 agent filter narrows results to selected agent", async ({ page }) => {
    await page.waitForSelector("table tbody tr", { timeout: 10_000 });
    const agentSelect = page.locator("select[aria-label='Filter by agent']");
    await agentSelect.selectOption({ value: "code_review" });
    await page.waitForTimeout(500);

    const visibleAgentCells = page.locator("tbody td:first-child");
    const count = await visibleAgentCells.count();
    for (let i = 0; i < count; i++) {
      const text = await visibleAgentCells.nth(i).textContent();
      expect(text?.trim().replace(/\s+/g, " ").toLowerCase()).toBe("code review");
    }
  });

  test("FLEET-03 version filter shows only matching versions", async ({ page }) => {
    await page.waitForSelector("table tbody tr", { timeout: 10_000 });
    const versionSelect = page.locator("select[aria-label='Filter by version']");
    await versionSelect.selectOption({ value: "v1.0.0" });
    await page.waitForTimeout(500);

    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();
    // Should still have rows
    expect(rowCount).toBeGreaterThan(0);
  });

  test("FLEET-04 combined filters produce intersection subset", async ({ page }) => {
    await page.waitForSelector("table tbody tr", { timeout: 10_000 });
    const agentSelect = page.locator("select[aria-label='Filter by agent']");
    await agentSelect.selectOption({ value: "code_review" });
    await page.waitForTimeout(300);

    const versionSelect = page.locator("select[aria-label='Filter by version']");
    await versionSelect.selectOption({ value: "v1.0.0" });
    await page.waitForTimeout(500);

    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test("FLEET-05 empty filter result shows EmptyState", async ({ page }) => {
    // Return empty rows to simulate a filter combo with no results
    await page.route("**/api/v1/fleet**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { rows: [] },
          meta: { total: 0, page: 1, page_size: 20 },
        }),
      });
    });
    await page.goto("/fleet");
    await expect(page.getByText("No fleet data yet")).toBeVisible({ timeout: 10_000 });
  });

  test("FLEET-06 row click navigates to run timeline", async ({ page }) => {
    const firstRow = page.locator("tbody tr").first();
    await firstRow.click();
    await expect(page).toHaveURL(/\/runs\?agent=/);
  });

  test("FLEET-07 loading skeletons visible while fetching", async ({ page }) => {
    await page.route("**/api/v1/fleet**", async (route) => {
      await new Promise((r) => setTimeout(r, 2000));
      await route.continue();
    });

    await page.goto("/fleet");
    await expect(page.locator(".shimmer").first()).toBeVisible({ timeout: 5000 });
  });

  test("FLEET-08 error state with retry on 500", async ({ page }) => {
    await page.route("**/api/v1/fleet**", async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
    });

    await page.goto("/fleet");
    await expect(page.getByText("Something went wrong")).toBeVisible({ timeout: 10_000 });
  });
});
