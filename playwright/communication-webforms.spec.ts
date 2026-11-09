import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication webforms render, create, and submit lead", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/webforms", "Webforms");
  await expect(page.getByText("Lead Capture", { exact: true })).toBeVisible();
  await page.getByRole("main").getByRole("button", { name: "Create webform",exact:true }).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Webform name",{exact:true}).fill("QA enquiry");
  await dialog.getByLabel("Public URL slug",{exact:true}).fill("qa-enquiry");
  await dialog.locator("form").getByRole("button",{name:"Review configuration",exact:true}).click();
  await dialog.getByRole("button",{name:"Confirm and save",exact:true}).click();
  await expect(page.getByText("Saved successfully.",{exact:true})).toBeVisible();
  await page.goto("/forms/communication/lead-capture-phase-6");
  await page.getByLabel("First name *",{exact:true}).fill("QA");
  await page.getByLabel("Email *",{exact:true}).fill("qa@example.test");
  await page.getByRole("button",{name:"Submit enquiry",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Thank you. Your request was received.",exact:true})).toBeVisible();
});

