import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication consent and opt-out page renders and saves opt-out", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/consents", "Consent & preferences");
  await expect(page.getByText("blocked@example.com")).toBeVisible();
  await page.getByRole("main").getByRole("button", { name: "Record customer choice", exact: true }).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Customer email",{exact:true}).fill("blocked@example.com");
  await dialog.getByRole("combobox",{name:"Customer choice",exact:true}).selectOption("opted_out");
  await dialog.getByLabel("Source or consent evidence").fill("Customer requested an opt-out in the QA scenario");
  await dialog.locator("form").getByRole("button",{name:"Review customer choice",exact:true}).click();
  const saved=page.waitForRequest(r=>r.method()==="POST"&&r.url().endsWith("/communication/consents"));
  await dialog.getByRole("button",{name:"Confirm and save",exact:true}).click();
  expect((await saved).postDataJSON()).toMatchObject({status:"opted_out",email:"blocked@example.com"});
  await expect(page.getByText("Saved successfully.",{exact:true})).toBeVisible();
});

