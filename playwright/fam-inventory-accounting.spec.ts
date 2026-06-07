import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory accounting dashboard shows GL, GRNI, COGS and GST controls", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/accounting", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Inventory Accounting" })).toBeVisible();
  await expect(page.getByText("Accounting controls")).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "GRNI", exact: true })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "COGS", exact: true })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "GST", exact: true })).toBeVisible();
});
