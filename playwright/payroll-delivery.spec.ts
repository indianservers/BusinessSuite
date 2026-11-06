import { test, expect } from "../frontend/node_modules/playwright/test";

test.beforeEach(async ({ page, request }) => {
  const response = await request.post("http://127.0.0.1:1553/api/v1/auth/login", { data: { email: "hr@suiteqa.example.com", password: "SuiteQA@12345" } });
  expect(response.ok()).toBeTruthy();
  const tokens = await response.json();
  expect(tokens.is_superuser).toBeFalsy();
  const access = await request.get("http://127.0.0.1:1553/api/v1/access/me", { headers: { Authorization: `Bearer ${tokens.access_token}` } });
  const user = { id: tokens.user_id, email: tokens.email, role: "hr", is_superuser: false, access: await access.json() };
  await page.addInitScript(({ tokens, user }) => sessionStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user, isAuthenticated: true }, version: 0 })), { tokens, user });
});

test("HR can save financial-year and payslip templates and download their preview", async ({ page }) => {
  await page.goto("/hrms/payroll");
  await page.getByRole("button", { name: "Payslip Templates", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Financial Year & Payslip Templates", exact: true })).toBeVisible();
  await page.getByLabel("Payslip YTD basis", { exact: true }).selectOption("financial");
  await page.getByLabel("Financial year starts", { exact: true }).selectOption("4");
  await page.getByLabel("Payslip layout", { exact: true }).selectOption("professional");
  await page.getByLabel("Payslip footer", { exact: true }).fill(`HR verified ${test.info().project.name} payslip`);
  await page.getByRole("button", { name: "Save payslip settings", exact: true }).click();
  await expect(page.getByText("Payslip templates and year settings saved", { exact: true })).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Preview saved template", exact: true }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe("regular-payslip-preview.pdf");
  await file.saveAs(`.tmp/payroll-delivery-regular-${test.info().project.name}.pdf`);
  await page.reload();
  await expect(page.getByLabel("Payslip layout", { exact: true })).toHaveValue("professional");
  await expect(page.getByLabel("Payslip footer", { exact: true })).toHaveValue(`HR verified ${test.info().project.name} payslip`);
  await page.getByLabel("Payslip document type", { exact: true }).selectOption("settlement");
  await expect(page.getByLabel("Payslip layout", { exact: true })).toBeVisible();
  await page.screenshot({ path: `.tmp/payroll-delivery-templates-${test.info().project.name}.png`, fullPage: true });
});

test("HR sees payout approvals and must confirm amount before test submission", async ({ page }) => {
  let approved = false, submitted: unknown;
  const batch = () => ({ id: 91, payroll_run_id: 71, total_amount: 45000, status: approved ? "Approved" : "Generated" });
  await page.route("**/api/v1/payroll/runs", route => route.fulfill({ json: [{ id: 71, month: 5, year: 2026, status: "locked" }] }));
  await page.route(/\/api\/v1\/payroll\/payments\/batches(?:\?.*)?$/, route => route.fulfill({ status: route.request().method() === "POST" ? 201 : 200, json: route.request().method() === "POST" ? batch() : [batch()] }));
  await page.route("**/api/v1/payroll/delivery/payment-batches", route => route.fulfill({ status: 201, json: batch() }));
  await page.route("**/api/v1/payroll/delivery/payouts/91", route => route.fulfill({ json: { ...batch(), approved_by: approved ? 99 : null, items: [] } }));
  await page.route("**/api/v1/payroll/delivery/payouts/91/approve", route => { approved = true; return route.fulfill({ json: { ...batch(), approved_by: 99, items: [] } }); });
  await page.route("**/api/v1/payroll/delivery/payouts/91/submit", route => { submitted = route.request().postDataJSON(); return route.fulfill({ json: { ...batch(), items: [] } }); });
  await page.goto("/hrms/payroll");
  await page.getByRole("button", { name: "Salary Payouts", exact: true }).click();
  await page.getByText("Configure payout connection", { exact: true }).click();
  await page.getByLabel("Payout API key ID", { exact: true }).fill("rzp_test_QA12345");
  await page.getByLabel("Payout API secret", { exact: true }).fill("synthetic-qa-secret");
  await page.getByLabel("Payout debit account", { exact: true }).fill("2323232323");
  await page.getByRole("button", { name: "Save payout connection", exact: true }).click();
  await expect(page.getByText(/Connection: TEST/)).toBeVisible();
  await page.getByLabel("Salary payout payroll run", { exact: true }).selectOption("71");
  await page.getByRole("button", { name: "Prepare salary payment batch", exact: true }).click();
  await page.getByRole("button", { name: "Approve payout batch", exact: true }).click();
  const send = page.getByRole("button", { name: "Send test salary payouts", exact: true });
  await expect(send).toBeDisabled();
  await page.getByLabel("Confirm salary payout total", { exact: true }).fill("45000");
  await page.getByLabel(/I authorize this test payout batch/).check();
  await expect(send).toBeEnabled();
  await send.click();
  await expect.poll(() => submitted).toMatchObject({ confirm_total: "45000", confirm_mode: "test" });
  await page.screenshot({ path: `.tmp/payroll-delivery-payouts-${test.info().project.name}.png`, fullPage: true });
});

test("HR finds Form 16 in statutory compliance with review and signed publication controls", async ({ page }) => {
  await page.route("**/api/v1/hrms/form16?**", route => route.fulfill({ json: [{ id: 91, employeeId: 71, employee: { id: 71, name: "Asha Rao", pan: "ABCDE1234F" }, financialYear: "2026-27", status: "generated", partAFilePath: "part-a.pdf", partBFilePath: "part-b.pdf", combinedFilePath: "combined.pdf", digitalSignatureStatus: "pending" }] }));
  await page.goto("/hrms/payroll");
  await page.getByRole("link", { name: "Open Form 16 & Statutory Compliance", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Employee Form 16 Records", exact: true })).toBeVisible();
  await expect(page.getByLabel("Form 16 signing trust certificate", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm review", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Publish verified Form 16", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Upload DSC-signed Form 16 for Asha Rao", { exact: true })).toBeDisabled();
  await page.screenshot({ path: `.tmp/payroll-delivery-form16-${test.info().project.name}.png`, fullPage: true });
});
