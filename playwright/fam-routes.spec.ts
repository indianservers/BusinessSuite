import { test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute, famRoutes } from "./fam-test-utils";

test.describe("FAM routes", () => {
  test("all FAM frontend routes render for FAM Admin", async ({ page }) => {
    test.setTimeout(120_000);
    await authenticate(page, "fam_admin");
    for (const route of famRoutes) {
      await expectHealthyFamRoute(page, route);
    }
  });
});
