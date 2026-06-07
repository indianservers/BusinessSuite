import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory COGS report renders posted delivery accounting evidence", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/cogs", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "COGS Report" })).toBeVisible();
  await expect(page.getByText("MOV-OUT-001")).toBeVisible();
  await expect(page.getByText("500")).toBeVisible();
});
