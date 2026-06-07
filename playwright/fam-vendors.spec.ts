import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM vendors", () => {
  test("filters vendor party masters and keeps vendor ledger context visible", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/vendors");

    await expect(page.getByRole("heading", { name: "Vendors" })).toBeVisible();
    await expect(page.getByText("Create vendor")).toBeVisible();
    await expect(page.getByText("Reliable Vendor LLP")).toBeVisible();
    await expect(page.getByText("Acme Customer Private Limited")).toHaveCount(0);
    await expect(page.getByRole("columnheader", { name: "LEDGER ID" })).toBeVisible();
  });
});
