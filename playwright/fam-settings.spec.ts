import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM settings", () => {
  test("settings page renders and saves company financial settings", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/settings");
    await page.getByLabel("Trade Name").fill("Acme Finance");
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByText("FAM settings saved", { exact: true }).first()).toBeVisible();
  });
});
