import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication individual email shows honest blocked provider status", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/emails", "Individual Emails");
  await page.getByRole("button", { name: "Send Email" }).click();
  await expect(page.getByText("Email blocked", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Create Draft" }).click();
  await expect(page.getByText("Draft 11", { exact: true }).first()).toBeVisible();
});

