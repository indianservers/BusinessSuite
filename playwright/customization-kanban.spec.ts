import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization, expectCustomizationRoute } from "./customization-test-utils";

test("Customization Kanban builder renders and creates board", async ({ page }) => {
  await authenticateCustomization(page);
  await expectCustomizationRoute(page, "/admin/customization/kanban", "Kanban Builder");
  await page.getByRole("button", { name: "Create Kanban" }).click();
  await expect(page.getByText("Kanban saved", { exact: true }).first()).toBeVisible();
});

