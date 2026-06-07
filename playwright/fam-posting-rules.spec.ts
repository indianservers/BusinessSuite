import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM posting rules", () => {
  test("renders SRM ledger rule configuration", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/posting-rules");

    await expect(page.getByRole("heading", { name: "Posting Rules", exact: true })).toBeVisible();
    await expect(page.getByText("Create posting rule")).toBeVisible();
    await expect(page.getByText("sales invoice")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save posting rule" })).toBeVisible();
  });
});
