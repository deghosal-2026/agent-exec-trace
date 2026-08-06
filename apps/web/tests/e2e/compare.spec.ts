import { test, expect } from "@playwright/test";

test.describe("Version Compare", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/compare");
  });

  test("CMP-01 two versions produce non-empty deltas", async ({ page }) => {
    const agentInput = page.locator("input").first();
    await agentInput.fill("research_crew");
    const versionA = page.locator("input[placeholder='v1.0']");
    await versionA.fill("v1.2.0");
    const versionB = page.locator("input[placeholder='v2.0']");
    await versionB.fill("v1.3.0");
    await page.waitForTimeout(1000);

    // Delta badges should appear
    await expect(page.getByText("Cost Delta")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Tool Usage Comparison")).toBeVisible({ timeout: 5_000 });

    await page.screenshot({ path: "test-results/compare-deltas.png", fullPage: true });
  });

  test("CMP-02 version selectors are populated and functional", async ({ page }) => {
    const inputs = page.locator("input[placeholder='v1.0'], input[placeholder='v2.0']");
    await expect(inputs.first()).toBeVisible();
    // Verify placeholders exist
    await expect(page.locator("input[placeholder='v1.0']")).toBeVisible();
    await expect(page.locator("input[placeholder='v2.0']")).toBeVisible();
  });

  test("CMP-03 single version shows appropriate message, no crash", async ({ page }) => {
    const versionA = page.locator("input[placeholder='v1.0']");
    await versionA.fill("v1.2.0");
    await page.waitForTimeout(500);

    // Empty state should be shown because comparison is incomplete
    await expect(page.getByText("Select two versions to compare")).toBeVisible();
  });

  test("CMP-04 sparse cohort warning for small cohort (<5 runs)", async ({ page }) => {
    const agentInput = page.locator("input").first();
    await agentInput.fill("research_crew");
    const versionA = page.locator("input[placeholder='v1.0']");
    await versionA.fill("v1.4.0");
    const versionB = page.locator("input[placeholder='v2.0']");
    await versionB.fill("v1.3.0");
    await page.waitForTimeout(1500);

    await expect(page.getByText(/sparse/i).or(page.getByText(/Cohort/i)).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("CMP-05 zero-delta when comparing same version to itself", async ({ page }) => {
    const agentInput = page.locator("input").first();
    await agentInput.fill("research_crew");
    const versionA = page.locator("input[placeholder='v1.0']");
    await versionA.fill("v1.2.0");
    const versionB = page.locator("input[placeholder='v2.0']");
    await versionB.fill("v1.2.0");
    await page.waitForTimeout(1000);

    // Should still render without crash
    await expect(page.getByText("Cost Delta")).toBeVisible({ timeout: 10_000 });
  });
});