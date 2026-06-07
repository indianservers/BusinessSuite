import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI email draft remains a reviewable draft", async ({ page }) => {
  await authenticateAi(page);
  await expectAiRoute(page, "/ai/copilot", "Copilot");
  await page.getByRole("button", { name: "Preview Action" }).click();
  await expect(page.getByText("requires_confirmation")).toBeVisible();
});

