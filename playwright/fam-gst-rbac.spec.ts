import { test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied } from "./fam-test-utils";

test("FAM GST routes block non-FAM employee", async ({ page }) => {
  await authenticate(page, "employee");
  await expectDenied(page, "/fam/gst");
});
