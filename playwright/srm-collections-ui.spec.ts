import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM collections UI", () => {
  test("shows aging buckets, sends reminders, escalates, and requests write-off", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });

    for (const label of ["Not due", "Due", "Overdue", "Escalated", "Collected", "Written-off"]) {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(page.getByText("Invoice Aging")).toBeVisible();
    await expect(page.getByText("Reminder / Escalation / Write-off History")).toBeVisible();

    await page.getByRole("button", { name: "Send Reminder" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Reminder sent completed");

    await page.getByRole("button", { name: "Escalate" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Collection escalated completed");

    const writeOffResponse = page.waitForResponse((response) => response.url().includes("/api/v1/srm/collections/1/write-off-request") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Request Write-off" }).click();
    expect((await writeOffResponse).ok()).toBeTruthy();
  });
});
