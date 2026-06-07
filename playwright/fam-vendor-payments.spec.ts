import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM vendor payments", () => {
  test("prepares and posts vendor payment runs from payables", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/vendor-payments");
    await expect(page.getByText("Open payables")).toBeVisible();
    await page.getByRole("button", { name: /Prepare/i }).click();
    await expect(page.getByText("Payment run prepared").first()).toBeVisible();
    await page.getByRole("button", { name: /Post payment/i }).click();
    await expect(page.getByText("Vendor payment posted").first()).toBeVisible();
  });
});
