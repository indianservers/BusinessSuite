import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied } from "./srm-test-utils";

async function postStatus(page: Page, path: string) {
  return page.evaluate(async (apiPath) => {
    const response = await fetch(`/api/v1${apiPath}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    return response.status;
  }, path);
}

test.describe("SRM seeded E2E role restrictions", () => {
  test("restricted roles cannot perform protected direct actions", async ({ page }) => {
    await authenticate(page, "srm_sales_executive");
    await expectDenied(page, "/srm/invoices");
    expect(await postStatus(page, "/srm/invoices/1/approve")).toBe(403);
    expect(await postStatus(page, "/srm/receipts/1/allocate")).toBe(403);

    await authenticate(page, "srm_collection_executive");
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Create Receipt" })).toBeVisible();
    expect(await postStatus(page, "/srm/invoices/1/lines")).toBe(403);
    expect(await postStatus(page, "/srm/settings/invoice_number_prefix")).toBe(403);

    await authenticate(page, "srm_viewer");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Save Settings" })).toHaveCount(0);
    expect(await postStatus(page, "/srm/sales-orders")).toBe(403);
    expect(await postStatus(page, "/srm/sales-orders/1/approve")).toBe(403);

    await authenticate(page, "srm_finance_manager");
    expect(await postStatus(page, "/srm/settings/invoice_number_prefix")).toBe(403);

    await authenticate(page, "employee");
    await expectDenied(page, "/srm");
  });
});
