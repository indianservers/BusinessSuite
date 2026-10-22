import { test, expect } from "../frontend/node_modules/playwright/test";

// Real HTTP API + disposable migrated PostgreSQL database; no route mocks.
test.skip(({ baseURL }) => baseURL !== "http://127.0.0.1:5182", "Requires the PostgreSQL browser regression server.");
const api = "http://127.0.0.1:8766/api/v1";
const modules: Record<string, string[]> = {
  HRMS: ["/hrms/admin-home", "/hrms/employees", "/hrms/attendance", "/hrms/leave", "/hrms/payroll", "/hrms/recruitment", "/hrms/performance", "/hrms/helpdesk", "/hrms/documents", "/hrms/lms", "/hrms/benefits", "/hrms/reports"],
  CRM: ["/crm", "/crm/leads", "/crm/contacts", "/crm/companies", "/crm/deals", "/crm/pipeline", "/crm/quotes", "/crm/forecasting", "/crm/activities"],
  PMS: ["/pms/workspaces", "/pms/projects", "/pms/tasks", "/pms/gantt", "/pms/sprints", "/pms/time-tracking", "/pms/timesheets", "/pms/reports", "/pms/risk-register"],
  SRM: ["/srm", "/srm/sales-orders", "/srm/contracts", "/srm/engagements", "/srm/billing-plans", "/srm/invoices", "/srm/collections", "/srm/pos", "/srm/inventory/dashboard", "/srm/inventory/items"],
  FAM: ["/fam", "/fam/chart-of-accounts", "/fam/vouchers", "/fam/parties", "/fam/bank-accounts", "/fam/bank-reconciliation", "/fam/purchase-bills", "/fam/gst", "/fam/inventory/accounting", "/fam/inventory/reconciliation"],
  Platform: ["/business-os", "/admin/business-os/modules", "/admin/automation", "/admin/customization", "/analytics", "/ai/copilot", "/admin/security", "/admin/subscription", "/developer/api-keys"],
};

for (const [module, routes] of Object.entries(modules)) {
  test(`${module}: live PostgreSQL pages render without API or runtime failures`, async ({ page, request }) => {
    test.setTimeout(180_000);
    const login = await request.post(`${api}/auth/login`, { data: { email: "admin@aihrms.com", password: "Admin@123456" } });
    expect(login.status()).toBe(200);
    const auth = await login.json();
    await page.addInitScript(auth => {
      localStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: auth.access_token, refreshToken: auth.refresh_token, isAuthenticated: true,
        user: { id: auth.user_id, email: auth.email, role: auth.role, is_superuser: auth.is_superuser } }, version: 0 }));
    }, auth);
    let failures: string[] = [];
    page.on("pageerror", e => failures.push(e.message));
    page.on("response", response => {
      if (response.url().includes("/api/v1/") && response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`);
    });
    for (const route of routes) {
      await test.step(route, async () => {
        failures = [];
        await page.goto(route, { waitUntil: "networkidle" });
        await expect(page).not.toHaveURL(/\/login/);
        await expect(page.locator("body")).not.toContainText(/Something went wrong|Unable to load|Internal Server Error|403 Access Denied/);
        expect(failures, `${route} API/runtime errors`).toEqual([]);
      });
    }
  });
}
