import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM chart of accounts", () => {
  test("chart tree and ledgers render from FAM APIs", async ({ page }) => {
    await authenticate(page, "accountant");
    await expectHealthyFamRoute(page, "/fam/chart-of-accounts");
    await expect(page.getByText("Current Assets")).toBeVisible();
    await expect(page.getByRole("cell", { name: "Cash", exact: true })).toBeVisible();
  });
});
