import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation cadences page renders and creates cadence", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/cadences", "Cadences");
  await page.getByRole("button", { name: "Create Cadence" }).click();
  await expect(page.getByText("Cadence saved", { exact: true }).first()).toBeVisible();
});

