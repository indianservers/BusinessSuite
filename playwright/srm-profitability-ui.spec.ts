import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM profitability UI", () => {
  test("supports profitability filters and displays revenue, cost, and margin fields", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    await page.goto("/srm/profitability", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Profitability", level: 1 })).toBeVisible();
    await page.getByLabel("customer id").fill("10");
    await page.getByLabel("sales order id").fill("1");

    await expect(page.getByText("Engagement Profitability")).toBeVisible();
    await expect(page.getByText("Profitability Values")).toBeVisible();
    for (const label of ["quoted value", "sales order value", "contract value", "billing plan value", "gross margin", "cash margin", "collection status"]) {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
    }
  });
});
