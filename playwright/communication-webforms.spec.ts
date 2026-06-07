import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication webforms render, create, and submit lead", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/webforms", "Webforms");
  await expect(page.getByText("Lead Capture")).toBeVisible();
  await page.getByRole("button", { name: "Create Webform" }).click();
  await expect(page.getByText("Webform saved", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Submit Demo Lead" }).click();
  await expect(page.getByText("Submission lead", { exact: true }).first()).toBeVisible();
});

