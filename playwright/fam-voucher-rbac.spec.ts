import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM voucher RBAC", () => {
  test("accountant can open vouchers and non-FAM employee is blocked", async ({ page }) => {
    await authenticate(page, "accountant");
    await expectHealthyFamRoute(page, "/fam/vouchers");
    await expect(page.getByRole("heading", { name: "Vouchers" })).toBeVisible();

    await authenticate(page, "employee");
    await expectDenied(page, "/fam/vouchers");
  });
});
