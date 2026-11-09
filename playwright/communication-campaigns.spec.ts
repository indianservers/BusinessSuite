import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication, expectCommunicationRoute } from "./communication-test-utils";

test("Communication campaigns create, preview, and send with tracked status", async ({ page }) => {
  await authenticateCommunication(page);
  await expectCommunicationRoute(page, "/crm/campaigns", "Campaigns");
  await expect(page.getByText("Nurture Campaign")).toBeVisible();
  await page.getByRole("main").getByRole("button", { name: "Create campaign",exact:true }).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Campaign name",{exact:true}).fill("QA campaign");
  await dialog.getByRole("combobox",{name:"Email template",exact:true}).selectOption("1");
  await dialog.getByRole("contentinfo").getByRole("button",{name:"Review & save draft",exact:true}).click();
  await dialog.getByRole("contentinfo").getByRole("button",{name:"Create reviewed draft",exact:true}).click();
  await expect(page.getByText("Campaign draft created. Preview its audience before sending.",{exact:true})).toBeVisible();
  await page.getByRole("complementary",{name:"Campaign selection"}).getByRole("button",{name:/Nurture Campaign/}).click();
  await page.getByRole("button",{name:"Preview audience for Nurture Campaign",exact:true}).click();
  await expect(page.getByText("Audience preview updated.",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Review send",exact:true}).click();
  await page.getByRole("checkbox",{name:"I reviewed the selected campaign, recipients, exclusions and message."}).check();
  await page.getByRole("button",{name:"Send reviewed campaign #1",exact:true}).click();
  await expect(page.getByText("Campaign processed. Check its recorded delivery results.",{exact:true})).toBeVisible();
});

