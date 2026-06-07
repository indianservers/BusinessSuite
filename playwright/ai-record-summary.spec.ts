import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI record summary generates evidence-backed output", async ({ page }) => {
  await authenticateAi(page);
  await expectAiRoute(page, "/ai/record-summary", "Record Summary");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("Mock AI output with evidence and confidence.")).toBeVisible();
});

