import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM bank statement import", () => {
  test("imports statement and opens review detail", async ({ page }) => {
    await authenticate(page, "accountant");
    await expectHealthyFamRoute(page, "/fam/bank-statements");

    await expect(page.getByText("Manual import only")).toBeVisible();
    await page.getByRole("button", { name: "Import statement" }).click();
    await expect(page.getByText("Bank statement imported", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("hdfc-june.csv")).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/bank-statements/1");
    await expect(page.getByText("Customer receipt REF-1")).toBeVisible();
    await expect(page.getByRole("button", { name: "Auto-match" })).toBeVisible();
  });
});

