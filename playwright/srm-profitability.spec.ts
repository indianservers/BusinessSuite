import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM profitability UI", () => {
  test("profitability route renders margin snapshot rows", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await expectHealthySrmRoute(page, "/srm/profitability");
    await expect(page.getByRole("heading", { name: "Profitability", level: 1 })).toBeVisible();
    await expect(page.getByText("healthy").first()).toBeVisible();
    await expect(page.getByText("250,000").first()).toBeVisible();
  });
});
