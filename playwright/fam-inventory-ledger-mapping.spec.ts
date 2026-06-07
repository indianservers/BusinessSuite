import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory ledger mapping page renders and saves mapping controls", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/items/1/ledger-mapping", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Item Ledger Mapping", exact: true })).toBeVisible();
  await expect(page.getByLabel("inventory ledger id")).toBeVisible();
  await expect(page.getByLabel("grni ledger id")).toBeVisible();
  await page.getByRole("button", { name: /save mapping/i }).click();
  await expect(page.getByText(/Inventory ledger mapping saved/i).first()).toBeVisible();
});
