import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM lead conversion flow", () => {
  test("converts a qualified lead and navigates to the created deal", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/leads/1", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /Convert Lead/ }).click();
    await expect(page).toHaveURL(/\/crm\/deals\/1$/);
    await expect(page.getByRole("heading", { name: "Acme implementation" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Commercial Handoff" })).toBeVisible();
  });
});
