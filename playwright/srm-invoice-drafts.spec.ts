import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM invoice drafts UI", () => {
  test("invoice draft route renders draft records in the SRM shell", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await expectHealthySrmRoute(page, "/srm/invoice-drafts");
    await expect(page.getByRole("heading", { name: "Invoice Drafts", level: 1 })).toBeVisible();
    await expect(page.getByText("draft", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("250,000").first()).toBeVisible();
  });
});
