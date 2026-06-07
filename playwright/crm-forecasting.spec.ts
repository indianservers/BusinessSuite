import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM forecasting Phase 2", () => {
  test("renders scenario forecast and owner/team/territory tables", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/forecasts", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Forecasting" })).toBeVisible();
    await expect(page.getByText("Conservative")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Forecast by Owner" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Forecast by Team" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Forecast by Territory" })).toBeVisible();
  });
});
