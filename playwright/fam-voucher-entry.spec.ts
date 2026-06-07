import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM voucher entry", () => {
  test("new voucher screen shows balanced debit credit grid and draft action", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/vouchers/new");
    await expect(page.getByRole("heading", { name: "New Voucher" })).toBeVisible();
    await expect(page.getByText("Debit / Credit lines")).toBeVisible();
    await expect(page.getByText("Difference")).toBeVisible();
    await expect(page.getByRole("button", { name: /Save draft/i })).toBeVisible();
  });
});
