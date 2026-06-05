import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM invoices UI", () => {
  test("shows invoice detail, approval, send/export, PDF, lines, history, and allocation sections", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Invoices", level: 1 })).toBeVisible();
    await expect(page.getByText("Invoice Number")).toBeVisible();
    await expect(page.getByText("Balance Amount")).toBeVisible();
    await expect(page.getByRole("link", { name: "Download PDF" })).toHaveAttribute("href", /\/api\/v1\/srm\/invoices\/1\/pdf/);

    await page.getByRole("button", { name: "Approve Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Invoice approval completed");

    await page.getByRole("button", { name: "Send / Export Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Invoice send/export completed");

    await page.getByRole("button", { name: "Add Invoice Line" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Invoice line completed");

    await expect(page.getByText("Invoice Lines")).toBeVisible();
    await expect(page.getByText("Receipt Allocations")).toBeVisible();
    await expect(page.getByText("Audit / History")).toBeVisible();
  });

  test("shows invoice validation errors from the API", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    await page.route("**/api/v1/srm/invoices/1/send", async (route) => {
      await route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "Only approved invoices can be sent" }) });
    });
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Send / Export Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Only approved invoices can be sent");
  });
});
