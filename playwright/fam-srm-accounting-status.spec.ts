import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM SRM accounting status", () => {
  test("shows accounting status through posting job detail mappings", async ({ page }) => {
    await authenticate(page, "auditor");
    await expectHealthyFamRoute(page, "/fam/posting-jobs/1");

    await expect(page.getByText("posted").first()).toBeVisible();
    await expect(page.getByRole("cell", { name: "voucher" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "bill reference" })).toBeVisible();
  });
});
