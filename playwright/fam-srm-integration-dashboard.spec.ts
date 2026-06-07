import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM SRM integration dashboard", () => {
  test("shows posting health, duplicate prevention, and manual posting actions", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/integrations/srm");

    await expect(page.getByRole("heading", { name: "SRM Accounting Integration" })).toBeVisible();
    await expect(page.getByText("Pending postings")).toBeVisible();
    await expect(page.getByText("Duplicate prevention")).toBeVisible();
    await expect(page.getByRole("button", { name: "Post SRM invoice" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Post SRM receipt" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Post allocation" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reverse posting" })).toBeVisible();
  });
});

