import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication campaigns create, preview, and send with tracked status", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/campaigns", "Campaigns");
  await expect(page.getByText("Nurture Campaign")).toBeVisible();
  await page.getByRole("button", { name: "Create Campaign" }).click();
  await expect(page.getByText("Campaign saved", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("Preview 1 recipients", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Campaign completed", { exact: true }).first()).toBeVisible();
});

