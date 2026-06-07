import { test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation } from "./automation-test-utils";
import { expectDenied } from "./srm-test-utils";

test("Non-admin employee is blocked from Automation Studio routes", async ({ page }) => {
  await authenticateAutomation(page, "employee");
  await expectDenied(page, "/admin/automation/workflows");
});

