import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

async function setup(page: Page) {
  await page.addInitScript(() => { window.__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" }; });
  await page.route("**/api/v1/**", route => route.fulfill({ json: [] }));
  await authenticateCrm(page);
  await page.route(/\/api\/v1\/employees\/?\?/, route => route.fulfill({ json: { items: [{ id: 3, first_name: "HR", last_name: "Manager", employee_id: "HR-3", employment_type: "Full-time" }], total: 1 } }));
  for (const [path, json] of Object.entries({
    branches: [{ id: 1, name: "Head Office" }],
    departments: [{ id: 2, name: "Engineering", branch_id: 1 }],
    designations: [{ id: 4, name: "Intern", department_id: 2 }],
  })) await page.route(`**/api/v1/company/${path}/`, route => route.fulfill({ json }));
}

test("link an existing login in Complete Profile and unlock the profile", async ({ page }, testInfo) => {
  await setup(page);
  let userId: number | null = null;
  await page.route("**/api/v1/employees/2", route => route.fulfill({ json: { id: 2, first_name: "Suresh", last_name: "Sharma", employee_id: "EMP0002", user_id: userId, employment_type: "Full-time", status: "Active", personal_email: "suresh@example.com", education: [], experience: [], skills: [], documents: [] } }));
  await page.route("**/api/v1/employees/user-options?*", route => route.fulfill({ json: [{ id: 7, email: "suresh@example.com", role: "employee" }] }));
  await page.route("**/api/v1/employees/2/user-link", async route => { userId = route.request().postDataJSON().user_id; await route.fulfill({ json: { user_id: userId } }); });
  await page.route("**/api/v1/profiles/employees/2", route => route.fulfill({ json: { userId: 7, employeeId: 2, displayName: "Suresh Sharma", loginEmail: "suresh@example.com", values: {}, version: "1", completeness: 0, missingFields: [], pendingRequests: [], documents: [], canEdit: true, canManage: true, requiresApprovalFields: [] } }));
  await page.goto("/hrms/employees/2");
  await page.getByRole("button", { name: "Complete Profile", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Set up employee login" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create Login" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("employee-login-actions.png"), fullPage: true, animations: "disabled" });
  await page.getByLabel("Link an existing login account").selectOption("7");
  await page.getByRole("button", { name: "Link Account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Set up employee login" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Suresh Sharma", exact: true }).last()).toBeVisible();
  expect(userId).toBe(7);
});

test("All Interns opens the intern list directly and exposes signup approvals", async ({ page }, testInfo) => {
  await setup(page);
  let internFilter = "";
  await page.route("**/api/v1/interns-hub/management/**", async route => {
    const url = new URL(route.request().url());
    let json: any = {};
    if (url.pathname.endsWith("/access")) json = { allowed: true };
    else if (url.pathname.endsWith("/options")) json = { staff: [], departments: [], batches: [], projects: [] };
    else if (url.pathname.endsWith("/interns")) { internFilter = url.searchParams.get("include_employees") || ""; json = { items: [{ id: 8, name: "Ananya Rao", intern_id: "IH-008", email: "ananya@example.com", skills: [], batches: [], status: "Active" }], total: 1 }; }
    else if (url.pathname.endsWith("/batches")) json = { items: [], total: 0 };
    await route.fulfill({ json });
  });
  await page.goto("/hrms/interns/list");
  await expect(page.getByRole("heading", { name: "All Interns", exact: true }).first()).toBeVisible();
  await expect(page.getByText("Ananya Rao", { exact: true })).toBeVisible();
  expect(internFilter).toBe("false");
  await page.screenshot({ path: testInfo.outputPath("intern-list-desktop.png"), fullPage: true, animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator("main").evaluate(element => element.getBoundingClientRect().width)).toBeGreaterThan(350);
  await expect(page.getByText("Ananya Rao", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("intern-list-mobile.png"), fullPage: true, animations: "disabled" });
  const nav = page.getByRole("navigation", { name: "Intern quick access" });
  await expect(nav.getByRole("link", { name: /Signups & Approvals/ })).toHaveAttribute("href", "/hrms/interns/applications");
  await expect(nav.getByRole("link", { name: /Batches/ , exact: false }).last()).toBeVisible();
});

test("review a signup and approve an intern from the direct approvals page", async ({ page }, testInfo) => {
  await setup(page);
  let status = "Pending";
  let decision: any;
  const applicant = () => ({ id: 5, full_name: "Ananya Rao", email: "ananya@example.com", reference: "APP-005", status, details: { role: "Software Intern", available_from: "2026-10-26" } });
  await page.route("**/api/v1/interns-hub/admin/applications", route => route.fulfill({ json: [applicant()] }));
  await page.route("**/api/v1/interns-hub/admin/application-settings", route => route.fulfill({ json: { roles: ["Software Intern"], version: 1 } }));
  await page.route("**/api/v1/interns-hub/admin/applications/5/decision", async route => { decision = route.request().postDataJSON(); status = decision.status; await route.fulfill({ json: { ...applicant(), intern_id: "IH-005" } }); });
  await page.goto("/hrms/interns/applications");
  await expect(page.getByRole("heading", { name: "Signups & Approvals" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Pending.*1/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Internship roles for applications" })).not.toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("signup-approval.png"), fullPage: true, animations: "disabled" });
  await page.getByLabel("Branch *", { exact: true }).selectOption("1");
  await page.getByLabel("Department *", { exact: true }).selectOption("2");
  await page.getByLabel("Designation *", { exact: true }).selectOption("4");
  await page.getByLabel("Reporting Manager *", { exact: true }).selectOption("3");
  await page.getByLabel("Joining Date *", { exact: true }).fill("2026-10-26");
  await page.getByRole("button", { name: "Approve & Onboard" }).click();
  await expect(page.getByRole("button", { name: /Approved.*1/ })).toBeVisible();
  expect(decision).toMatchObject({ status: "Approved", branch_id: 1, department_id: 2, designation_id: 4, reporting_manager_id: 3 });
});


async function setupBulkApplications(page: Page, failId?: number) {
  await setup(page);
  const applications = [
    { id: 5, full_name: "Ananya Rao", status: "Pending" },
    { id: 6, full_name: "Ravi Kumar", status: "Pending" },
    { id: 7, full_name: "Meera Shah", status: "Correction Requested" },
    { id: 8, full_name: "Approved Intern", status: "Approved" },
    { id: 9, full_name: "Rejected Intern", status: "Rejected" },
  ].map(item => ({ ...item, email: `intern-${item.id}@example.com`, reference: `APP-${item.id}`, details: { role: "Software Intern", available_from: "2026-10-26" } }));
  const decisions: { id: number; body: any }[] = [];
  await page.route("**/api/v1/interns-hub/admin/applications", route => route.fulfill({ json: applications }));
  await page.route("**/api/v1/interns-hub/admin/application-settings", route => route.fulfill({ json: { roles: ["Software Intern"], version: 1 } }));
  await page.route("**/api/v1/interns-hub/admin/applications/*/decision", async route => {
    const id = Number(new URL(route.request().url()).pathname.split("/").at(-2));
    const body = route.request().postDataJSON();
    decisions.push({ id, body });
    if (id === failId) { await route.fulfill({ status: 409, json: { detail: "Account already exists. Resolve it before approval." } }); return; }
    const item = applications.find(item => item.id === id)!;
    item.status = body.status;
    await route.fulfill({ json: { ...item, intern_id: `IH-${id}` } });
  });
  await page.goto("/hrms/interns/applications");
  await expect(page.getByRole("heading", { name: "Signups & Approvals" })).toBeVisible();
  return decisions;
}

test("bulk selection respects search, status and reviewed application boundaries", async ({ page }) => {
  const decisions = await setupBulkApplications(page);
  await page.getByRole("checkbox", { name: "Select Ananya Rao", exact: true }).check();
  await expect(page.getByRole("checkbox", { name: "Select all reviewable signups" })).toHaveJSProperty("indeterminate", true);
  await page.getByLabel("Search signups").fill("Ravi");
  await expect(page.getByRole("status").filter({ hasText: "0 selected" })).toBeVisible();
  await page.getByRole("checkbox", { name: "Select all reviewable signups" }).check();
  await expect(page.getByRole("checkbox", { name: "Select Ravi Kumar", exact: true })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Select Ananya Rao", exact: true })).toHaveCount(0);
  await page.getByLabel("Search signups").fill("");
  await page.getByRole("button", { name: /All Applications/ }).click();
  await expect(page.getByRole("checkbox", { name: "Select Approved Intern", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: "Select Rejected Intern", exact: true })).toBeDisabled();
  await page.getByRole("checkbox", { name: "Select all reviewable signups" }).check();
  await expect(page.getByRole("status").filter({ hasText: "3 selected" })).toBeVisible();
  await page.getByRole("button", { name: "Reject selected", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel", exact: true }).click();
  expect(decisions).toEqual([]);
});

test("bulk approval validates shared job details and only approves selected signups", async ({ page }, testInfo) => {
  const decisions = await setupBulkApplications(page);
  await page.getByRole("checkbox", { name: "Select all reviewable signups" }).check();
  await page.getByRole("button", { name: "Approve selected", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Approve & onboard selected", exact: true }).click();
  expect(decisions).toEqual([]);
  await dialog.getByLabel("Branch *", { exact: true }).selectOption("1");
  await dialog.getByLabel("Department *", { exact: true }).selectOption("2");
  await dialog.getByLabel("Designation *", { exact: true }).selectOption("4");
  await dialog.getByLabel("Reporting Manager *", { exact: true }).selectOption("3");
  await dialog.getByLabel("Joining Date *", { exact: true }).fill("2026-10-26");
  await page.screenshot({ path: testInfo.outputPath("bulk-approval.png"), animations: "disabled" });
  await dialog.getByRole("button", { name: "Approve & onboard selected", exact: true }).click();
  await expect(page.getByRole("region", { name: "Bulk review results" })).toContainText("2 application(s) updated. 0 failed.");
  expect(decisions.map(item => item.id)).toEqual([5, 6]);
  for (const { body } of decisions) expect(body).toMatchObject({ status: "Approved", branch_id: 1, department_id: 2, designation_id: 4, reporting_manager_id: 3, date_of_joining: "2026-10-26" });
});

for (const action of [
  { button: "Reject selected", confirm: "Confirm rejection", status: "Rejected" },
  { button: "Request corrections for selected", confirm: "Send correction requests", status: "Correction Requested" },
]) test(`bulk ${action.status} requires a reason and preserves partial failures`, async ({ page }) => {
  const decisions = await setupBulkApplications(page, 6);
  await page.getByRole("button", { name: /All Applications/ }).click();
  await page.getByRole("checkbox", { name: "Select all reviewable signups" }).check();
  await page.getByRole("button", { name: action.button, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Branch *", { exact: true })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: action.confirm, exact: true })).toBeDisabled();
  await dialog.getByLabel("Reason / instructions *", { exact: true }).fill("  ");
  await expect(dialog.getByRole("button", { name: action.confirm, exact: true })).toBeDisabled();
  await dialog.getByLabel("Reason / instructions *", { exact: true }).fill("Please review your application details.");
  await dialog.getByRole("button", { name: action.confirm, exact: true }).click();
  const results = page.getByRole("region", { name: "Bulk review results" });
  await expect(results).toContainText("2 application(s) updated. 1 failed.");
  await expect(results).toContainText("Ravi Kumar: Account already exists");
  await expect(page.getByRole("checkbox", { name: "Select Ravi Kumar", exact: true })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Select Ananya Rao", exact: true })).not.toBeChecked();
  expect(decisions.map(item => item.id)).toEqual([5, 6, 7]);
  for (const { body } of decisions) expect(body).toEqual({ status: action.status, review_note: "Please review your application details." });
  await page.getByRole("button", { name: action.button, exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("1 selected application(s)");
  await page.getByRole("dialog").getByRole("button", { name: "Cancel", exact: true }).click();
});
