import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

const modules = [{key: "crm", label: "CRM"}, {key: "project_management", label: "Projects"}];
test("public company and individual signup reuse the trial request form", async ({page}) => {
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/v1/**", route => route.fulfill({json: {items: []}}));
  await page.route("**/api/v1/auth/signup/options", route => route.fulfill({json: {modules}}));
  await page.route("**/api/v1/auth/signup", async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({status: 202, json: {message: "Submitted"}});
  });
  await page.setViewportSize({width: 390, height: 844});
  await page.goto("/signup");
  await expect(page.getByRole("heading", {name: "Sign up for a software trial"})).toBeVisible();
  await page.getByLabel("Your name", {exact: true}).fill("Trial Owner");
  await page.getByLabel("Company name", {exact: true}).fill("Trial Company");
  await page.getByLabel("Individual", {exact: true}).check();
  await expect(page.getByLabel("Company name", {exact: true})).toHaveCount(0);
  await page.getByLabel("Company", {exact: true}).check();
  await page.getByLabel("Company name", {exact: true}).fill("Trial Company");
  await page.getByLabel("Email", {exact: true}).fill("trial@example.com");
  await page.getByRole("textbox", {name: "Mobile / phone", exact: true}).fill("9876543210");
  await page.getByLabel("CRM", {exact: true}).check();
  await page.getByLabel(/I agree to be contacted/).check();
  await page.getByRole("button", {name: "Request trial access"}).click();
  await expect(page.getByRole("heading", {name: "Request submitted"})).toBeVisible();
  expect(submitted).toMatchObject({applicant_type: "company", company_name: "Trial Company", email: "trial@example.com", phone: "9876543210", phone_country_code: "+91", requested_modules: ["crm"], consent: true});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("Super Admin can review a pending signup and choose the trial duration", async ({page}) => {
  await authenticateCrm(page);
  const row = {id: 7, applicant_type: "company", name: "Trial Owner", company_name: "Trial Company", email: "trial@example.com", phone: "9876543210", phone_country_code: "+91", requested_modules: ["crm"], status: "pending", created_at: "2026-11-05T10:00:00Z"};
  let approved = false;
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/v1/access/setup", route => route.fulfill({json: {ready: true, items: [], moduleItems: [], optionalItems: []}}));
  await page.route("**/api/v1/auth/signup-requests?*", route => route.fulfill({json: {items: approved ? [] : [row], total: approved ? 0 : 1, modules}}));
  await page.route("**/api/v1/auth/signup-requests/7/review", async route => {
    submitted = route.request().postDataJSON(); approved = true;
    await route.fulfill({json: {request: {...row, status: "approved"}, invitation_url: "https://example.com/invite-access?token=private-test", delivery: "queued"}});
  });
  await page.goto("/admin/signup-requests");
  await page.getByRole("button", {name: "Review request"}).click();
  await page.getByLabel("Trial duration (days)", {exact: true}).fill("21");
  await page.getByLabel("Review reason", {exact: true}).fill("Approved after qualification");
  await page.getByRole("button", {name: "Approve and create workspace"}).click();
  await expect(page.getByRole("textbox", {name: "Private activation link"})).toBeVisible();
  expect(submitted).toMatchObject({decision: "approve", trial_days: 21, modules: ["crm"]});
});
