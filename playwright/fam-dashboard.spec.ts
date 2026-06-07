import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM dashboard", () => {
  test("renders India accounting foundation dashboard in the common shell", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam");
    await expect(page.getByRole("heading", { name: "FAM Dashboard" })).toBeVisible();
    await expect(page.getByText("GST compliance placeholder", { exact: false })).toBeVisible();
    await expect(page.getByText("FAM is the statutory books engine", { exact: false })).toBeVisible();
  });
});
