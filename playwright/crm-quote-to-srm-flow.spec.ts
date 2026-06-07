import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM quote to SRM flow UI", () => {
  test("accept action triggers SRM conversion path", async ({ page }) => {
    await authenticateCrm(page);
    const calls: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/crm/quotes/1/accept")) calls.push(request.url());
    });
    await page.goto("/crm/quotes/1/builder", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /Accept and convert to SRM/ }).click();
    await expect.poll(() => calls.length).toBeGreaterThan(0);
  });
});
