import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation webhooks page renders and creates webhook", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/webhooks", "Webhooks");
  await page.getByRole("button", { name: "Create Webhook" }).click();
  await expect(page.getByText("Webhook saved", { exact: true }).first()).toBeVisible();
});

