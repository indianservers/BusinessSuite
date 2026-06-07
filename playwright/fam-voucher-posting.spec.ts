import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM voucher posting", () => {
  test("voucher detail exposes post cancel reverse and clone lifecycle actions", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/vouchers/1");
    await expect(page.getByRole("heading", { name: "Voucher Detail" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Post voucher/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Cancel voucher/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Reverse voucher/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Clone voucher/i })).toBeVisible();
  });
});
