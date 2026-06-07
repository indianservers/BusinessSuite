import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory dashboard renders merged source evidence", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/dashboard");
  await expect(page.getByRole("heading", { name: "Inventory Dashboard" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source merge audit" })).toBeVisible();
});
