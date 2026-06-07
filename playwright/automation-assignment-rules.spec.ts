import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation assignment rules page renders and creates rule", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/assignment-rules", "Assignment Rules");
  await page.getByRole("button", { name: "Create Rule" }).click();
  await expect(page.getByText("Assignment rule saved", { exact: true }).first()).toBeVisible();
});

