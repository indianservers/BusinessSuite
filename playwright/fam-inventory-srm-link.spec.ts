import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory SRM link page shows reservations and source records", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/srm-link", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "SRM Inventory Link" })).toBeVisible();
  await expect(page.getByText("RSV-001")).toBeVisible();
});
