import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAi, expectAiRoute } from "./ai-test-utils";

test("AI report explainer route renders and generates report explanation", async ({ page }) => {
  await authenticateAi(page);
  await expectAiRoute(page, "/ai/report-explainer", "Report Explainer");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("source_data_summary")).toBeVisible();
});

