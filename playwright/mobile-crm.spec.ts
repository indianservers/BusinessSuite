import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10, expectNoAccessDenied } from "./phase10-test-utils";

test("mobile CRM routes render responsive sales workspace", async ({ page }) => {
  await authenticatePhase10(page, "crm_sales_executive");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/mobile", "/mobile/leads", "/mobile/deals", "/mobile/activities"]) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expectNoAccessDenied(page);
    await expect(page.getByRole("heading", { name: "Mobile CRM" })).toBeVisible();
    await expect(page.getByText("Offline queue placeholder")).toBeVisible();
  }
});
