import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("CRM communication roles can open hub while non-CRM employee is blocked", async ({ page }) => {
  await authenticateCommunication(page, "crm_marketing_user");
  await expectCommunicationRoute(page, "/crm/communication-hub", "Communication Hub");

  await authenticateCommunication(page, "employee");
  await page.goto("/crm/communication-hub", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
});

