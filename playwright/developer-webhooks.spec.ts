import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10 } from "./phase10-test-utils";

test("developer webhooks create HTTPS endpoint and queue test delivery", async ({ page }) => {
  await authenticatePhase10(page);
  await page.goto("/developer/webhooks", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Create HTTPS webhook" }).click();
  await expect(page.getByText("CRM event webhook").first()).toBeVisible();
  await page.getByRole("button", { name: "Test" }).first().click();
  await expect(page.getByText("active").first()).toBeVisible();
});
