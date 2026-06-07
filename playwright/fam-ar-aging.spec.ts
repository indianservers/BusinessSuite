import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM AR aging", () => {
  test("shows customer invoice aging buckets and AR outstanding", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/ar/aging");

    await expect(page.getByRole("heading", { name: "AR Aging", exact: true })).toBeVisible();
    await expect(page.getByText("AR aging details")).toBeVisible();
    await expect(page.getByText("INV-001")).toBeVisible();
    await expect(page.getByRole("cell", { name: "Not due" })).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/ar/outstanding");
    await expect(page.getByText("AR total outstanding")).toBeVisible();
  });
});
