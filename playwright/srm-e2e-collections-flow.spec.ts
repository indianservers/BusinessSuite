import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM seeded E2E collections flow", () => {
  test("runs aging, reminder, escalation, write-off request, audit, and status verification", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Overdue" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Invoice Aging" })).toBeVisible();

    await page.getByRole("button", { name: "Send Reminder" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Reminder sent completed");
    await page.getByRole("button", { name: "Escalate" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Collection escalated completed");
    await page.getByRole("button", { name: "Request Write-off" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Write-off requested completed");

    const records = await page.evaluate(async () => {
      const customer = await fetch("/api/v1/srm/collections/customer/10").then((res) => res.json());
      const lifecycle = await fetch("/api/v1/srm/engagements/2/lifecycle").then((res) => res.json());
      return { customer, lifecycle };
    });
    expect(records.customer.reminders.length).toBeGreaterThanOrEqual(3);
    expect(records.customer.invoices[0].balance_amount).toBeGreaterThan(0);
    expect(records.lifecycle.audit.length).toBeGreaterThan(0);
  });
});
