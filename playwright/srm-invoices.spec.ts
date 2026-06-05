import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM invoices UI", () => {
  test("invoice register renders and invoice actions call approve/send APIs", async ({ page }) => {
    const calls: string[] = [];
    await authenticate(page, "srm_admin");
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.includes("/api/v1/srm/invoices/1")) calls.push(`${request.method()} ${url.pathname}`);
    });
    await expectHealthySrmRoute(page, "/srm/invoices");
    await expect(page.getByRole("heading", { name: "Invoices", level: 1 })).toBeVisible();
    await expect(page.getByText("INV-000001").first()).toBeVisible();

    await page.getByRole("button", { name: "Approve Invoice" }).click();
    await page.getByRole("button", { name: "Send / Export Invoice" }).click();

    await expect.poll(() => calls).toContain("POST /api/v1/srm/invoices/1/approve");
    await expect.poll(() => calls).toContain("POST /api/v1/srm/invoices/1/send");
  });
});
