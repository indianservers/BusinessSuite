import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization view builder renders and creates view", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/views", "List View Builder");
  await page.getByRole("button", { name: "Create View" }).click();
  await expect(page.getByText("List saved", { exact: true }).first()).toBeVisible();
});

