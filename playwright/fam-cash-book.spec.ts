import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM cash book", () => {
  test("renders cash book ledger postings and totals", async ({ page }) => {
    await authenticate(page, "auditor");
    await expectHealthyFamRoute(page, "/fam/cash-book");

    await expect(page.getByRole("heading", { name: "Cash Book", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Cash", exact: true })).toBeVisible();
    await expect(page.getByText("JV-00001")).toBeVisible();
    await expect(page.getByText("Debit", { exact: true })).toBeVisible();
  });
});
