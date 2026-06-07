import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization formula builder renders and tests formula", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/formulas", "Formula Fields");
  await page.getByRole("button", { name: "Test Formula" }).click();
  await expect(page.getByText("Formula result 750", { exact: true }).first()).toBeVisible();
});

