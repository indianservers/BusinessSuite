import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM funnel Phase 2", () => {
  test("renders lead-to-cash funnel including SRM stages", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/funnel", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Sales Funnel" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "SRM Invoice Generated" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Receipt Collected" })).toBeVisible();
  });
});
