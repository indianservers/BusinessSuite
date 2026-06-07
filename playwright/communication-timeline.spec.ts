import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication } from "./communication-test-utils";

test("CRM record detail shows Communication Timeline and email action uses Communication Hub backend", async ({ page }) => {
  await authenticateCommunication(page);
  await page.goto("/crm/leads/1", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Communication Timeline" })).toBeVisible();
  await expect(page.getByText("No configured communication email provider")).toBeVisible();
  await page.getByRole("button", { name: "Send Email" }).click();
  await page.locator("text=Send Email").last().waitFor();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("No configured communication email provider").last()).toBeVisible();
});

