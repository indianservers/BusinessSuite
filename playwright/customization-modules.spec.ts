import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization module builder renders and creates module", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/modules", "Module Builder");
  await page.getByRole("button", { name: "Create Module" }).click();
  await expect(page.getByText("Module saved", { exact: true }).first()).toBeVisible();
});

