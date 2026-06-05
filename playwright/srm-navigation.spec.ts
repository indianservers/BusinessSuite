import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

const sidebarEntries = [
  ["Dashboard", "/srm/dashboard"],
  ["Sales Orders", "/srm/sales-orders"],
  ["Contracts", "/srm/contracts"],
  ["Engagements", "/srm/engagements"],
  ["Billing Plans", "/srm/billing-plans"],
  ["Invoice Drafts", "/srm/invoice-drafts"],
  ["Invoices", "/srm/invoices"],
  ["Collections", "/srm/collections"],
  ["Revenue Recognition", "/srm/revenue-recognition"],
  ["Profitability", "/srm/profitability"],
  ["Customer 360", "/srm/customer-360"],
  ["Reports", "/srm/reports"],
  ["Settings", "/srm/settings"],
] as const;

test.describe("SRM navigation", () => {
  test("sidebar entries navigate and active route highlighting follows selection", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });

    for (const [label] of sidebarEntries) {
      await expect(page.getByRole("link", { name: new RegExp(label, "i") })).toBeVisible();
    }

    await page.getByRole("link", { name: "Sales Orders" }).click();
    await expect(page).toHaveURL(/\/srm\/sales-orders$/);
    await expect(page.getByRole("link", { name: "Sales Orders" })).toHaveClass(/nav-link-active/);

    await page.getByRole("link", { name: "Customer 360" }).click();
    await expect(page).toHaveURL(/\/srm\/customer-360$/);
    await expect(page.getByRole("heading", { name: "Customer 360" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Customer 360" })).toHaveClass(/nav-link-active/);
  });

  test("collection role sees collection navigation and read-only settings, but not finance invoices", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("link", { name: "Collections", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Settings", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Invoices", exact: true })).toHaveCount(0);
  });
});
