import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10 } from "./phase10-test-utils";

test("admin subscription shows plans and Ultimate override", async ({ page }) => {
  await authenticatePhase10(page);
  await page.goto("/admin/subscription", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("ultimate")).toBeVisible();
  await expect(page.getByText("starter")).toBeVisible();
  await page.getByRole("button", { name: "Set Ultimate with admin override" }).click();
  await expect(page.getByText("admin_override")).toBeVisible();
});
