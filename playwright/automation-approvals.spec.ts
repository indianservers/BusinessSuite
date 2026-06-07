import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateAutomation, expectAutomationRoute } from "./automation-test-utils";

test("Automation approvals page renders and creates request", async ({ page }) => {
  await authenticateAutomation(page);
  await expectAutomationRoute(page, "/admin/automation/approvals", "Approvals");
  await page.getByRole("button", { name: "Create Request" }).click();
  await expect(page.getByText("Approval request created", { exact: true }).first()).toBeVisible();
});

