import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI collection risk route renders for finance user", async ({ page }) => {
  await authenticateAi(page, "srm_finance_manager");
  await expectAiRoute(page, "/ai/collection-risk", "Collection Risk");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("provider_configured")).toBeVisible();
});

