import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute, srmRoutes } from "./srm-test-utils";

test.describe("SRM UI route completion", () => {
  test("all SRM routes render with breadcrumbs and without console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    await authenticate(page, "srm_admin");
    for (const route of srmRoutes) {
      await expectHealthySrmRoute(page, route);
      await expect(page.locator("body")).toContainText("SRM");
    }
    expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([]);
  });

  test("non-SRM employee is blocked from the SRM shell", async ({ page }) => {
    await authenticate(page, "employee");
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
  });
});
