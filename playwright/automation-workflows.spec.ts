import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation workflows page renders and creates/tests workflow", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/workflows", "Workflow Registry");
  await page.getByRole("button", { name: "Save Workflow" }).click();
  await expect(page.getByText("Workflow saved", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Test First" }).click();
  await expect(page.getByText("Workflow test logged", { exact: true }).first()).toBeVisible();
});

