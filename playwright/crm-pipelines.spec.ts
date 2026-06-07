import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM pipelines Phase 2", () => {
  test("renders pipeline manager and reorders stages through the API", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/pipelines", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Pipeline Settings" })).toBeVisible();
    await expect(page.getByText("Enterprise Sales")).toBeVisible();
    await expect(page.locator('input[value="Qualification"]')).toBeVisible();

    const response = await page.evaluate(async () => {
      const result = await fetch("/api/v1/crm/pipeline-stages/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: [{ id: 1, orderIndex: 1 }, { id: 2, orderIndex: 2 }] }),
      });
      return result.json();
    });
    expect(response.total).toBe(2);
  });
});
