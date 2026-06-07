import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI deal coach route generates confidence and reasons", async ({ page }) => {
  await authenticateAi(page);
  await expectAiRoute(page, "/ai/deal-coach", "Deal Coach");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.locator("pre")).toContainText("Sanitized context");
});
