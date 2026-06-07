import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM bank book", () => {
  test("renders bank book ledger postings and totals", async ({ page }) => {
    await authenticate(page, "auditor");
    await expectHealthyFamRoute(page, "/fam/bank-book");

    await expect(page.getByRole("heading", { name: "Bank Book", exact: true })).toBeVisible();
    await expect(page.getByText("HDFC Bank")).toBeVisible();
    await expect(page.getByText("RV-00001")).toBeVisible();
    await expect(page.getByText("Closing", { exact: true })).toBeVisible();
  });
});
