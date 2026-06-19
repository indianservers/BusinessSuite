import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test("CRM theme toggle applies the dark product shell", async ({ page }) => {
  await authenticateCrm(page);
  await page.route("**/api/v1/business-os/modules", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled_modules: ["crm"] }),
    });
  });
  await page.goto(`${process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173"}/crm`, { waitUntil: "domcontentloaded" });

  const shell = page.locator(".product-shell.product-crm");
  await expect(shell).toBeVisible();

  const lightBackground = await shell.evaluate((element) => getComputedStyle(element).backgroundColor);
  await page.getByRole("button", { name: "Switch to dark theme" }).click();

  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Switch to light theme" })).toBeVisible();
  await expect
    .poll(() => shell.evaluate((element) => getComputedStyle(element).backgroundColor))
    .not.toBe(lightBackground);
});
