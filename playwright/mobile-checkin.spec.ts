import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10 } from "./phase10-test-utils";

test("mobile check-in creates visit record from responsive UI", async ({ page }) => {
  await authenticatePhase10(page, "crm_sales_executive");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/mobile/check-in", { waitUntil: "domcontentloaded" });
  await page.getByPlaceholder("Customer name").fill("Acme");
  await page.getByRole("button", { name: "Check in" }).click();
  await expect(page.getByText("checked_in").first()).toBeVisible();
});
