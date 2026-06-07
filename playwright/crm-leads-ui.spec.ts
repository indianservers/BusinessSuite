import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM leads UI", () => {
  test("renders lead list, lead detail, score, timeline, and conversion action", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/leads", "Leads", "Nisha Rao");

    await page.goto("/crm/leads/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Nisha Rao" })).toBeVisible();
    await expect(page.getByText("Hot")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Activity Timeline" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Convert Lead/ })).toBeVisible();
  });
});
