import { test, expect } from "../frontend/node_modules/playwright/test";

test.beforeEach(async ({ page, request }) => {
  const login = await request.post("http://127.0.0.1:1551/api/v1/auth/login", {
    data: { email: "admin@suiteqa.example.com", password: "SuiteQA@12345" },
  });
  expect(login.ok()).toBeTruthy();
  const tokens = await login.json();
  const access = await request.get("http://127.0.0.1:1551/api/v1/access/me", { headers: { Authorization: `Bearer ${tokens.access_token}` } });
  const user = { id: tokens.user_id, email: tokens.email, role: tokens.role, is_superuser: tokens.is_superuser, access: await access.json() };
  await page.addInitScript(({ tokens, user }) => {
    sessionStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user, isAuthenticated: true }, version: 0 }));
  }, { tokens, user });
  await page.route("**/api/v1/payroll/my-payslips", route => route.fulfill({ json: [{ id: 91, month: 5, year: 2026, net_salary: 42000.25, currency: "USD" }] }));
});

const payslip = { id: 91, payroll_status: "locked", currency: "USD", net_salary: 42000.25, gross_salary: 45000.5, total_deductions: 3000.25,
  employee: { employee_id: "EMP-91", first_name: "Asha", last_name: "Rao" },
  earnings: [{ component_name: "Basic", amount: 45000.5 }], deductions: [{ component_name: "Tax", amount: 3000.25 }] };

test("history selects a payslip, preserves decimals and submits a query", async ({ page }) => {
  let submitted: unknown;
  await page.route("**/api/v1/payroll/payslip?**", route => route.fulfill({ json: payslip }));
  await page.route("**/api/v1/payroll/payslip-queries", route => {
    submitted = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: { id: 1 } });
  });
  await page.goto("/hrms/my-payslips");
  await page.getByRole("button", { name: /May 2026/ }).click();
  await expect(page.getByLabel("Payslip month")).toHaveValue("5");
  await expect(page.getByLabel("Payslip year")).toHaveValue("2026");
  await expect(page.getByText(/42,000\.25/).first()).toBeVisible();
  await page.getByLabel("Question about this payslip?").fill("Please explain the tax deduction.");
  await page.getByRole("button", { name: "Send query to Payroll", exact: true }).click();
  await expect.poll(() => submitted).toMatchObject({ payroll_record_id: 91, description: "Please explain the tax deduction." });
  await expect(page.getByLabel("Question about this payslip?")).toHaveValue("");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `.tmp/payslips-${test.info().project.name}.png`, fullPage: true });
});

test("API errors show retry and PDF failures keep the page usable", async ({ page }) => {
  let failed = true;
  await page.route("**/api/v1/payroll/payslip?**", route => failed ? route.fulfill({ status: 500, json: { detail: "Unavailable" } }) : route.fulfill({ json: payslip }));
  await page.route("**/api/v1/payroll/payslip/91/pdf", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await page.goto("/hrms/my-payslips");
  await expect(page.getByRole("alert").filter({ hasText: "Could not load your payslip" })).toBeVisible();
  failed = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await page.getByRole("button", { name: "Download PDF", exact: true }).click();
  await expect(page.getByText("Could not download payslip", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download PDF", exact: true })).toBeEnabled();
});

test("HR viewer fetches run records and publishes PDFs with optional email", async ({ page }) => {
  let submitted: unknown;
  await page.route("**/api/v1/payroll/runs", route => route.fulfill({ json: [
    { id: 71, month: 5, year: 2026, status: "calculated" }, { id: 72, month: 6, year: 2026, status: "locked" },
  ] }));
  await page.route("**/api/v1/payroll/runs/*/records", route => route.fulfill({ json: [{ ...payslip, employee_id: 91 }] }));
  await page.route("**/api/v1/payroll/runs/72/payslip-publish", route => {
    submitted = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: { published_count: 1, email_dispatch_status: "Not requested" } });
  });
  await page.goto("/hrms/payroll");
  await page.getByRole("button", { name: "Payslip Viewer", exact: true }).click();
  await page.getByRole("button", { name: "May 2026", exact: true }).click();
  await expect(page.getByRole("button", { name: "Bulk publish", exact: true })).toBeDisabled();
  await expect(page.getByText("EMP-91", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "June 2026", exact: true }).click();
  await page.getByLabel("Notify employees by email").uncheck();
  await page.getByRole("button", { name: "Bulk publish", exact: true }).click();
  await expect.poll(() => submitted).toEqual({ send_email: false });
  await expect(page.getByText("1 PDFs ready. Email: Not requested.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Preview", exact: true }).first().click();
  await expect(page.getByText("Employee Payslip Preview", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download PDF", exact: true })).toBeVisible();
});
