import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi } from "./ai-test-utils";

test("non-authorized employee is blocked from AI Copilot routes", async ({ page }) => {
  await authenticateAi(page, "employee");
  await page.goto("/ai/copilot", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
});

