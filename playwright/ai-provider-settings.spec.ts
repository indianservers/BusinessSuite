import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI provider settings render and test configured mock provider", async ({ page }) => {
  await authenticateAi(page);
  await expectAiRoute(page, "/ai/provider-settings", "AI Provider Settings");
  await expect(page.getByText("mock / mock-business-suite")).toBeVisible();
  await page.getByRole("button", { name: "Test" }).click();
});

