import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM day book", () => {
  test("day book renders voucher register totals", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/day-book");
    await expect(page.getByRole("heading", { name: "Day Book" })).toBeVisible();
    await expect(page.getByText("Debit total")).toBeVisible();
    await expect(page.getByText("JV-00001")).toBeVisible();
  });
});
