import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM TDS", () => {
  test("manages configurable TDS sections and payable reporting without fake filing", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/tds");
    await page.getByRole("button", { name: /Calculate TDS/i }).click();
    await expect(page.getByText("TDS ₹0").first()).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/tds/sections");
    await expect(page.getByRole("cell", { name: "194J" })).toBeVisible();
    await page.getByRole("button", { name: /Save section/i }).click();
    await expect(page.getByText("TDS section saved").first()).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/tds/transactions");
    await expect(page.getByText("deducted", { exact: true }).last()).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/tds/payable");
    await expect(page.getByText("Filing/export is unsupported", { exact: false })).toBeVisible();
  });
});
