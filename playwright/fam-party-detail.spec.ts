import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM party detail", () => {
  test("shows outstanding, statement bill references, and allocations", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/parties/1");

    await expect(page.getByRole("heading", { name: "Party Detail" })).toBeVisible();
    await expect(page.getByText("Acme Customer Private Limited")).toBeVisible();
    await expect(page.getByText("Statement and bill references")).toBeVisible();
    await expect(page.getByText("INV-001")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Allocations", exact: true })).toBeVisible();
    await expect(page.getByText("advance adjustment")).toBeVisible();
  });
});
