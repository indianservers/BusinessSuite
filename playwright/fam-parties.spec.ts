import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM parties", () => {
  test("renders party master creation and list with ledger-backed parties", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/parties");

    await expect(page.getByRole("heading", { name: "Parties" })).toBeVisible();
    await expect(page.getByText("Create party")).toBeVisible();
    await expect(page.getByText("party masters")).toBeVisible();
    await expect(page.getByText("Acme Customer Private Limited")).toBeVisible();
    await expect(page.getByText("Reliable Vendor LLP")).toBeVisible();
    await expect(page.getByRole("button", { name: /Create with ledger/i })).toBeVisible();
  });
});

