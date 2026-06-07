import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication consent and opt-out page renders and saves opt-out", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/consents", "Consent and Opt-out");
  await expect(page.getByText("blocked@example.com")).toBeVisible();
  await page.getByRole("button", { name: "Opt Out" }).click();
  await expect(page.getByText("Opt-out saved", { exact: true }).first()).toBeVisible();
});

