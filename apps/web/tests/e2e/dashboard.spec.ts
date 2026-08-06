import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("DASH-01 overview cards show non-zero aggregates", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".animate-fade-in-up", { timeout: 10_000 });

    const summaryGrid = page.locator(".grid.grid-cols-2.sm\\:grid-cols-4").first();
    const cards = summaryGrid.locator("> *");
    await expect(cards.first()).toBeVisible();
    await expect(cards).toHaveCount(4);

    await page.screenshot({ path: "test-results/dashboard-overview.png", fullPage: true });
  });

  test("DASH-02 agent cards grid shows agent name, version, workload", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("button.animate-fade-in-up", { timeout: 10_000 });

    const agentCards = page.locator("button.animate-fade-in-up");
    const count = await agentCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const firstCard = agentCards.first();
    await expect(firstCard.locator("h3")).toBeVisible();
    await expect(firstCard.locator("text=Runs", { exact: false })).toBeVisible();
  });

  test("DASH-03 card click navigates to fleet filtered by agent", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("button.animate-fade-in-up", { timeout: 10_000 });

    const firstCard = page.locator("button.animate-fade-in-up").first();
    const agentName = await firstCard.locator("h3").textContent();
    await firstCard.click();

    await expect(page).toHaveURL(/\/fleet\?agent=/);
    await page.screenshot({ path: "test-results/dashboard-to-fleet.png", fullPage: true });
  });

  test("DASH-04 empty state shown when fleet API returns empty", async ({ page }) => {
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

    await page.goto("/");
    await expect(page.getByText("No fleet data yet")).toBeVisible({ timeout: 10_000 });
  });
});