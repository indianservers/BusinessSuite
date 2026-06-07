import { test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation logs page renders execution evidence", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/logs", "Execution Logs");
});

