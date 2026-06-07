import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM bill allocations", () => {
  test("renders bill-wise tracking and allocation workflow surfaces", async ({ page }) => {
    await authenticate(page, "accountant");
    await expectHealthyFamRoute(page, "/fam/bill-references");
    await expect(page.getByRole("heading", { name: "Bill References" })).toBeVisible();
    await expect(page.getByText("Create bill reference")).toBeVisible();
    await expect(page.getByText("Bill-wise tracking")).toBeVisible();
    await expect(page.getByText("INV-001")).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/bill-allocations");
    await expect(page.getByRole("heading", { name: "Bill Allocations" })).toBeVisible();
    await expect(page.getByText("Allocate bill")).toBeVisible();
    await expect(page.getByText("advance adjustment")).toBeVisible();
  });
});
