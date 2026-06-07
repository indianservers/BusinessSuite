import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM posting jobs", () => {
  test("lists jobs, exposes retry, and opens job detail mappings", async ({ page }) => {
    await authenticate(page, "accountant");
    await expectHealthyFamRoute(page, "/fam/posting-jobs");

    await expect(page.getByRole("heading", { name: "Posting Jobs" })).toBeVisible();
    await expect(page.getByText("SRM posting queue")).toBeVisible();
    await expect(page.getByText("sales invoice")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" }).first()).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/posting-jobs/1");
    await expect(page.getByText("Accounting mappings")).toBeVisible();
    await expect(page.getByRole("cell", { name: "bill reference" })).toBeVisible();
  });
});
