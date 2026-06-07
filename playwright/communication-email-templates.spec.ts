import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication email templates render and create template", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/email-templates", "Email Templates");
  await expect(page.getByText("Welcome Lead")).toBeVisible();
  await page.getByRole("button", { name: "Create Template" }).click();
  await expect(page.getByText("Email saved", { exact: true }).first()).toBeVisible();
});

