import { test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory route guards allow FAM users and block non-FAM employees", async ({ page }) => {
  await authenticate(page, "fam_viewer");
  await expectHealthyFamRoute(page, "/fam/inventory/stock-summary");

  await authenticate(page, "employee");
  await expectDenied(page, "/fam/inventory/items");
});
