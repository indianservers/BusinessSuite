import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization layout builder renders and creates layout", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/layouts", "Layout Builder");
  await page.getByRole("button", { name: "Create Layout" }).click();
  await expect(page.getByText("Layout saved", { exact: true }).first()).toBeVisible();
});

