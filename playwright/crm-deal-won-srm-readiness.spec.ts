import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM deal won SRM readiness", () => {
  test("marks a deal won through the CRM API and keeps SRM handoff links visible", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/deals/1", { waitUntil: "domcontentloaded" });
    const won = await page.evaluate(async () => {
      const response = await fetch("/api/v1/crm/deals/1/mark-won", { method: "POST" });
      return response.json();
    });
    expect(won.status).toBe("Won");

    await page.goto("/crm/deals/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Commercial Handoff" })).toBeVisible();
    await expect(page.getByText("SO-000001")).toBeVisible();
    await expect(page.getByText("ENG-000001")).toBeVisible();
  });
});
