import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM lost analysis Phase 2", () => {
  test("renders lost reasons, competitors, and AI placeholder", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/lost-analysis", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Lost Analysis" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Budget frozen" }).first()).toBeVisible();
    await expect(page.getByText("AI pattern detection")).toBeVisible();
  });
});
