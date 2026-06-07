import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM activities UI", () => {
  test("renders activity list and supports completion API path", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/activities", "Activities", "Discovery call");

    const completed = await page.evaluate(async () => {
      const response = await fetch("/api/v1/crm/activities/1/complete", { method: "POST" });
      return response.json();
    });
    expect(completed.status).toBe("Completed");
  });
});
