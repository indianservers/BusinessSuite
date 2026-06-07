import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM CPQ UI", () => {
  test("renders CPQ rules and evaluates a configuration", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/cpq", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "CPQ Rules", exact: true })).toBeVisible();
    await expect(page.getByText("High discount approval").first()).toBeVisible();
    await page.getByRole("button", { name: /Evaluate/ }).first().click();
    await expect(page.getByText("Rules checked")).toBeVisible();
  });
});
