import { test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory accounting routes allow FAM viewers and block non-FAM employees", async ({ page }) => {
  await authenticate(page, "fam_viewer");
  await expectHealthyFamRoute(page, "/fam/inventory/accounting");

  await authenticate(page, "employee");
  await expectDenied(page, "/fam/inventory/accounting");
});
