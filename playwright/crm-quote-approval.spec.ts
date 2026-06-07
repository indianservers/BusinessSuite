import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM quote approvals UI", () => {
  test("renders quote approval queue", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/quote-approvals", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Quote Approvals", exact: true })).toBeVisible();
    await expect(page.getByText("Discount approval")).toBeVisible();
  });
});
