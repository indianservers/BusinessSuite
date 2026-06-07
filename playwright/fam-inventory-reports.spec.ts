import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

const reportRoutes = [
  ["/fam/inventory/reports", "Inventory Reports"],
  ["/fam/inventory/warehouse-stock", "Warehouse Stock"],
  ["/fam/inventory/stock-aging", "Stock Aging"],
  ["/fam/inventory/reorder-report", "Reorder Report"],
  ["/fam/inventory/dead-stock", "Dead Stock"],
  ["/fam/inventory/fast-slow-moving", "Fast/Slow Moving Items"],
  ["/fam/inventory/gross-margin", "Gross Margin"],
] as const;

for (const [route, heading] of reportRoutes) {
  test(`FAM inventory report route renders ${heading}`, async ({ page }) => {
    await authenticate(page, "fam_admin");
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByText(/Inventory records|Total value/i)).toBeVisible();
  });
}
