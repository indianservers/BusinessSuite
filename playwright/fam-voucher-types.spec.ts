import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM voucher types", () => {
  test("voucher type page renders system voucher categories and create form", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/voucher-types");
    await expect(page.getByRole("heading", { name: "Voucher Types" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Journal", exact: true })).toBeVisible();
    await expect(page.getByLabel("voucher type code")).toBeVisible();
  });
});
