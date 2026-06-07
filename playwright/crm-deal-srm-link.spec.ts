import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM deal SRM link UI", () => {
  test("shows SRM sales order, engagement, billing plan, and PMS project links on won deal detail", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/deals/501", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Commercial Handoff" })).toBeVisible();
    await expect(page.getByText("SRM Sales Order")).toBeVisible();
    await expect(page.getByRole("link", { name: "SO-000001" })).toHaveAttribute("href", "/srm/sales-orders");
    await expect(page.getByRole("link", { name: "ENG-000001" })).toHaveAttribute("href", "/srm/engagements");
    await expect(page.getByRole("link", { name: "CTR-000001" })).toHaveAttribute("href", "/srm/contracts");
    await expect(page.getByRole("link", { name: "Milestone billing" })).toHaveAttribute("href", "/srm/billing-plans");
    await expect(page.getByRole("link", { name: "PMS-301" })).toHaveAttribute("href", "/pms/projects/301");
  });
});
