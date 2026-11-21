import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM quotes UI", () => {
  test("closes the quote dialog after saving", async ({ page }) => {
    await authenticateCrm(page);
    let writes = 0;
    await page.route("**/api/v1/crm/quotations", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      writes++;
      await route.fulfill({ status: 201, json: { ...route.request().postDataJSON(), id: 42 } });
    });
    await page.goto("/crm/quotes");
    await page.getByRole("button", { name: "Create Quote", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByPlaceholder("QT-2026-001").fill("QA-QT-042");
    await dialog.getByRole("combobox", { name: "Linked deal" }).selectOption({ label: "Acme implementation" });
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith("/api/v1/crm/quotations") && response.status() === 201),
      dialog.getByRole("button", { name: "Create", exact: true }).click(),
    ]);
    await expect(dialog).toHaveCount(0);
    await expect(page.getByText("QA-QT-042", { exact: true }).first()).toBeVisible();
    expect(writes).toBe(1);
  });

  test("renders quote list and opens builder route", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/quotes", "Quotes", "QT-001");
    await page.goto("/crm/quotes/1/builder", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/common\/quotations\/1\/builder\?module=crm$/);
    await expect(page.getByRole("heading", { name: "Quote Builder" })).toBeVisible();
  });
});
