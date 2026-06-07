import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM ledgers", () => {
  test("ledger list and create workflow render", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/ledgers");
    await page.getByLabel("ledger code").fill("BANK-HDFC");
    await page.getByLabel("ledger name").fill("HDFC Bank");
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("ledger created", { exact: true }).first()).toBeVisible();
  });
});
