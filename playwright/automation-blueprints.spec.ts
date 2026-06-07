import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation blueprints page renders and creates blueprint", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/blueprints", "Blueprints");
  await page.getByRole("button", { name: "Create Blueprint" }).click();
  await expect(page.getByText("Blueprint saved", { exact: true }).first()).toBeVisible();
});

