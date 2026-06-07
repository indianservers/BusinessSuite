import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization field builder renders and creates field", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/fields", "Field Builder");
  await page.getByRole("button", { name: "Create Field" }).click();
  await expect(page.getByText("Field saved", { exact: true }).first()).toBeVisible();
});

