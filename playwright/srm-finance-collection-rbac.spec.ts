import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied } from "./srm-test-utils";

test.describe("SRM finance and collection RBAC", () => {
  test("Finance Manager can access invoice actions and profitability", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Approve Invoice" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Send / Export Invoice" })).toBeVisible();
    await page.goto("/srm/profitability", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Profitability", level: 1 })).toBeVisible();
  });

  test("Collection Executive can manage collections and only view settings", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Create Receipt" })).toBeVisible();
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save Settings" })).toHaveCount(0);
  });

  test("Sales Executive cannot access finance revenue routes", async ({ page }) => {
    await authenticate(page, "srm_sales_executive");
    await expectDenied(page, "/srm/invoices");
    await expectDenied(page, "/srm/collections");
    await expectDenied(page, "/srm/profitability");
  });

  test("Business Owner has read-only revenue visibility", async ({ page }) => {
    await authenticate(page, "srm_business_owner");
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only revenue access", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve Invoice" })).toHaveCount(0);
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only collection access", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Receipt" })).toHaveCount(0);
  });

  test("Non-SRM employee is blocked from SRM revenue routes", async ({ page }) => {
    await authenticate(page, "employee");
    await expectDenied(page, "/srm/invoices");
    await expectDenied(page, "/srm/collections");
  });
});
