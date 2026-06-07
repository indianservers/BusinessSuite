import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM banking RBAC", () => {
  test("viewer can read banking pages but cannot mutate banking records", async ({ page }) => {
    await authenticate(page, "fam_viewer");
    await expectHealthyFamRoute(page, "/fam/bank-book");
    await expectHealthyFamRoute(page, "/fam/cash-book");
    await expectHealthyFamRoute(page, "/fam/bank-accounts");

    const forbidden = page.waitForResponse((response) => response.url().includes("/api/v1/fam/bank-accounts") && response.request().method() === "POST" && response.status() === 403);
    await page.getByRole("button", { name: "Save bank account" }).click();
    await forbidden;
  });

  test("non-FAM employee is blocked from banking routes", async ({ page }) => {
    await authenticate(page, "employee");
    await expectDenied(page, "/fam/banking");
    await expectDenied(page, "/fam/bank-reconciliation");
  });
});

