import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM targets Phase 2", () => {
  test("renders target creation and target performance", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/targets", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Sales Targets" })).toBeVisible();
    await expect(page.getByText("Target Performance")).toBeVisible();
    await expect(page.getByText("Achievement Percent")).toBeVisible();
  });
});
