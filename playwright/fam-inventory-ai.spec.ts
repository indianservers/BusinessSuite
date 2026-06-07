import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory AI logs honest provider readiness", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/ai");
  await expect(page.getByRole("heading", { name: "Inventory AI" })).toBeVisible();
  await page.getByRole("button", { name: "Run inventory AI" }).click();
  await expect(page.getByText("Inventory AI provider is not configured")).toBeVisible();
});
