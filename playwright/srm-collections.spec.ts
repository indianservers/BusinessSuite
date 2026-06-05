import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM collections UI", () => {
  test("collections aging route renders outstanding aging buckets", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await expectHealthySrmRoute(page, "/srm/collections");
    await expect(page.getByRole("heading", { name: "Collections", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Invoice Aging" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Customer Outstanding" })).toBeVisible();
    await expect(page.getByText("INV-000001")).toBeVisible();
  });
});
