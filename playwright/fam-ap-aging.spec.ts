import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM AP aging", () => {
  test("shows vendor bill aging buckets and AP outstanding", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/ap/aging");

    await expect(page.getByRole("heading", { name: "AP Aging", exact: true })).toBeVisible();
    await expect(page.getByText("AP aging details")).toBeVisible();
    await expect(page.getByText("BILL-001")).toBeVisible();
    await expect(page.getByRole("cell", { name: "Not due" })).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/ap/outstanding");
    await expect(page.getByText("AP total outstanding")).toBeVisible();
  });
});
