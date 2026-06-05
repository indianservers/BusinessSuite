import { test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthySrmRoute, srmRoutes } from "./srm-test-utils";

test.describe("SRM routes", () => {
  test("all required SRM routes render for SRM Admin", async ({ page }) => {
    await authenticate(page, "srm_admin");
    for (const route of srmRoutes) {
      await expectHealthySrmRoute(page, route);
    }
  });
});

