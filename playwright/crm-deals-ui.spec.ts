import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM deals UI", () => {
  test("renders deal list, deal detail, pipeline fields, timeline, and SRM handoff card", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/deals", "Deals", "Acme implementation");

    await page.goto("/crm/deals/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Acme implementation" })).toBeVisible();
    await expect(page.getByText("Open").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Commercial Handoff" })).toBeVisible();
    await expect(page.getByText("SRM Sales Order")).toBeVisible();
  });
});
