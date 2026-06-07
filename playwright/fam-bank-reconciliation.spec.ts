import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM bank reconciliation", () => {
  test("shows reconciliation summary and supports match workflow actions", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/bank-statements/1");

    await page.getByRole("button", { name: "Auto-match" }).click();
    await expect(page.getByText("Bank reconciliation updated", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Confirm match" }).click();
    await expect(page.getByText("Bank reconciliation updated", { exact: true }).first()).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/bank-reconciliation");
    await expect(page.getByText("Unmatched statement lines")).toBeVisible();
    await expect(page.getByText("reconciled", { exact: true })).toBeVisible();
  });
});
