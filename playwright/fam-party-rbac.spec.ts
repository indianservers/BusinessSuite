import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM party and AR/AP RBAC", () => {
  test("viewer can read party and aging routes but cannot create records", async ({ page }) => {
    await authenticate(page, "fam_viewer");
    await expectHealthyFamRoute(page, "/fam/parties");
    await expectHealthyFamRoute(page, "/fam/ar/aging");
    await expectHealthyFamRoute(page, "/fam/ap/aging");

    await expectHealthyFamRoute(page, "/fam/parties");
    const createButton = page.getByRole("button", { name: /Create with ledger/i }).first();
    const forbidden = page.waitForResponse((response) => response.url().includes("/api/v1/fam/parties") && response.request().method() === "POST" && response.status() === 403);
    await createButton.click();
    await forbidden;
  });

  test("non-FAM employee is blocked from Phase 3 party and AR/AP routes", async ({ page }) => {
    await authenticate(page, "employee");
    await expectDenied(page, "/fam/parties");
    await expectDenied(page, "/fam/ar/aging");
    await expectDenied(page, "/fam/ap/aging");
  });
});
