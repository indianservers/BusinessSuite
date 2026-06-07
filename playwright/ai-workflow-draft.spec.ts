import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI workflow draft route shows non-active workflow output", async ({ page }) => {
  await authenticateAi(page);
  await expectAiRoute(page, "/ai/workflow-builder", "Workflow Draft");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("workflow_json")).toBeVisible();
});

