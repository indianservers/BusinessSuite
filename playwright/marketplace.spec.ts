import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10 } from "./phase10-test-utils";

test("marketplace shows internal-only apps and installed apps", async ({ page }) => {
  await authenticatePhase10(page);
  await page.goto("/marketplace/apps", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Internal extensions only")).toBeVisible();
  await page.getByRole("button", { name: "Create internal app" }).click();
  await page.getByRole("button", { name: "Install" }).first().click();
  await page.goto("/marketplace/installed", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("installed").first()).toBeVisible();
});
