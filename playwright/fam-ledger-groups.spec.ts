import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM ledger groups", () => {
  test("ledger group list and create workflow render", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/ledger-groups");
    await page.getByLabel("group name").fill("Deposits");
    await page.getByLabel("group code").fill("DEP");
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("ledger group created", { exact: true }).first()).toBeVisible();
  });
});
