import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM revenue events UI", () => {
  test("labels revenue operations accurately and shows event history", async ({ page }) => {
    await authenticate(page, "srm_revenue_manager");
    await page.goto("/srm/revenue-recognition", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Revenue Events / Revenue Operations" })).toBeVisible();
    await expect(page.getByText("This is not presented as a full IFRS 15 automation engine.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Revenue Events", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Invoice / Receipt / Cash Events" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Milestone Events" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Audit-backed Event History" })).toBeVisible();
  });
});
