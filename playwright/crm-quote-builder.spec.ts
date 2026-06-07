import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM quote builder", () => {
  test("renders line editor and calls quote workflow actions", async ({ page }) => {
    await authenticateCrm(page);
    const calls: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/crm/quotes/1")) calls.push(`${request.method()} ${new URL(request.url()).pathname}`);
    });

    await page.goto("/crm/quotes/1/builder", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Quote Builder" })).toBeVisible();
    await page.getByRole("button", { name: /Add/ }).click();
    await page.getByRole("button", { name: /Recalculate/ }).click();
    await page.getByRole("button", { name: /Submit for approval/ }).click();
    await page.getByRole("button", { name: /^Approve$/ }).click();
    await expect.poll(() => calls.some((call) => call.includes("/quotes/1/approve"))).toBeTruthy();
  });
});
