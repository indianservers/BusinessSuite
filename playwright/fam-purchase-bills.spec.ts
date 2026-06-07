import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM purchase bills", () => {
  test("lists, creates, opens, posts, and cancels vendor purchase bills", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/purchase-bills");
    await expect(page.getByRole("cell", { name: "PB-001" })).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/purchase-bills/new");
    await expect(page.getByLabel("vendor id")).toBeVisible();
    await expect(page.getByText("Input GST")).toBeVisible();
    await expect(page.getByText("TDS deduction")).toBeVisible();
    await page.getByRole("button", { name: /Save bill/i }).click();

    await expectHealthyFamRoute(page, "/fam/purchase-bills/1");
    await page.getByRole("button", { name: /Post bill/i }).click();
    await expect(page.getByText("Purchase bill posted").first()).toBeVisible();
    await page.getByRole("button", { name: /Cancel bill/i }).click();
    await expect(page.getByText("Purchase bill cancelled").first()).toBeVisible();
  });
});
