import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM reorder alerts render low-stock items", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/reorder-alerts");
  await expect(page.getByRole("heading", { name: "Reorder Alerts" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "SKU-001" })).toBeVisible();
});
