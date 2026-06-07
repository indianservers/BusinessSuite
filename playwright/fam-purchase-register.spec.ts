import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM purchase and payable registers", () => {
  test("renders purchase, expense, and payables dashboards", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/purchases");
    await expect(page.getByRole("link", { name: /Purchase Bills/i })).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/purchase-register");
    await expect(page.getByRole("cell", { name: "PB-001" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "gst total" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "tds amount" })).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/expense-register");
    await expect(page.getByRole("cell", { name: "EXP-001" })).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/payables/dashboard");
    await expect(page.getByText("Total payable")).toBeVisible();
  });
});
