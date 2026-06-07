import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM purchase RBAC", () => {
  test("FAM roles can view purchase areas and non-FAM employees are denied", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/purchase-bills");
    await expectHealthyFamRoute(page, "/fam/tds/payable");

    await authenticate(page, "employee");
    await expectDenied(page, "/fam/purchase-bills");
  });

  test("read-only viewer cannot create purchase bills through the API", async ({ page }) => {
    await authenticate(page, "fam_viewer");
    await expectHealthyFamRoute(page, "/fam/purchase-bills");
    const status = await page.evaluate(async () => {
      const response = await fetch("/api/v1/fam/purchase-bills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vendor_id: 2, bill_number: "BLOCKED", bill_date: "2026-06-06", lines: [] }),
      });
      return response.status;
    });
    expect(status).toBe(403);
  });
});
