import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM customers", () => {
  test("filters customer party masters and exposes AR-friendly terms", async ({ page }) => {
    await authenticate(page, "accountant");
    await expectHealthyFamRoute(page, "/fam/customers");

    await expect(page.getByRole("heading", { name: "Customers" })).toBeVisible();
    await expect(page.getByText("Create customer")).toBeVisible();
    await expect(page.getByText("Acme Customer Private Limited")).toBeVisible();
    await expect(page.getByText("Reliable Vendor LLP")).toHaveCount(0);
    await expect(page.getByRole("columnheader", { name: "PAYMENT TERMS DAYS" })).toBeVisible();
  });
});
