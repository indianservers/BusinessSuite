import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM territories Phase 2", () => {
  test("renders territories and supports assignment API", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/territories", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Territory Settings" })).toBeVisible();
    await expect(page.getByText("West India")).toBeVisible();

    const response = await page.evaluate(async () => {
      const result = await fetch("/api/v1/crm/territories/1/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId: 100, assignmentType: "owner" }),
      });
      return result.json();
    });
    expect(response.item.territoryId).toBe(1);
  });
});
