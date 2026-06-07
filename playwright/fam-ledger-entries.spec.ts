import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM ledger entries", () => {
  test("ledger entries and ledger drilldown render immutable postings", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/ledger-entries");
    await expect(page.getByRole("heading", { name: "Ledger Entries" })).toBeVisible();
    await expect(page.getByText("Running balance", { exact: false })).toBeVisible();
    await expectHealthyFamRoute(page, "/fam/ledgers/1/entries");
    await expect(page.getByRole("heading", { name: "Ledger Drill-Down" })).toBeVisible();
    await expect(page.getByText("Closing", { exact: true })).toBeVisible();
  });
});
