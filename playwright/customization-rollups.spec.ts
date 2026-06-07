import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization rollup builder renders and creates rollup", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/rollups", "Rollup Fields");
  await page.getByRole("button", { name: "Create Rollup" }).click();
  await expect(page.getByText("Rollup saved", { exact: true }).first()).toBeVisible();
});

