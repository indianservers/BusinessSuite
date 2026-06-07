import { test } from "../frontend/node_modules/playwright/test";
import { authenticateCustomization } from "./customization-test-utils";
import { expectDenied } from "./srm-test-utils";

test("Sales or employee roles are blocked from Customization Studio", async ({ page }) => {
  await authenticateCustomization(page, "employee");
  await expectDenied(page, "/admin/customization/fields");
});

