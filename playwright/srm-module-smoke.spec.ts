import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM module smoke", () => {
  test("SRM dashboard renders inside the common app shell", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await expectHealthySrmRoute(page, "/srm");
    await expect(page.getByRole("heading", { name: "Sales Revenue Management" })).toBeVisible();
    await expect(page.getByText("Orders, billing, collections", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh" })).toBeVisible();
  });
});
