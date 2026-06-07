import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10 } from "./phase10-test-utils";

test("developer hub creates masked scoped API key", async ({ page }) => {
  await authenticatePhase10(page);
  await page.goto("/developer/api-keys", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Create scoped API key" }).click();
  await expect(page.getByText("One-time key: bs_secret_once")).toBeVisible();
  await expect(page.getByText("bs_abc123")).toBeVisible();
});
