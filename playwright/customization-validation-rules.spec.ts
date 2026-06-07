import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization validation rule builder renders and creates rule", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/validation-rules", "Validation Rules");
  await page.getByRole("button", { name: "Create Rule" }).click();
  await expect(page.getByText("Validation saved", { exact: true }).first()).toBeVisible();
});

