import { expect, type Page } from "../frontend/node_modules/playwright/test";

export const automationFixtures = {
  workflows: [{ id: 1, name: "Quote discount approval", module_name: "crm", record_type: "quote", trigger_type: "quote_submitted", is_active: true, status: "active" }],
  blueprints: [{ id: 1, name: "Deal Qualification Blueprint", module_name: "crm", record_type: "deal", is_active: true }],
  approvals: [{ id: 1, module_name: "crm", record_type: "quote", record_id: 501, status: "pending", name: "Quote approval" }],
  assignments: [{ id: 1, name: "Website lead assignment", module_name: "crm", record_type: "lead", is_active: true }],
  cadences: [{ id: 1, name: "New lead nurture", module_name: "crm", target_type: "lead", status: "active" }],
  webhooks: [{ id: 1, name: "Revenue operations hook", target_url: "https://example.com/hooks/revenue", status: "active" }],
  logs: [{ id: 1, workflow_id: 1, module_name: "crm", record_type: "quote", status: "success", trigger_type: "quote_submitted" }],
};

export async function authenticateAutomation(page: Page, role = "crm_org_admin") {
  await installAutomationApiStubs(page);
  const user = { id: role === "employee" ? 201 : 101, email: `${role}@example.com`, role, is_superuser: role === "admin", employee_id: null };
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "automation-token",
      refreshToken: "automation-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: { accessToken: "automation-token", refreshToken: "automation-refresh", user: authUser, isAuthenticated: true },
      version: 0,
    }));
  }, user);
}

export async function installAutomationApiStubs(page: Page) {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let body: unknown = {};

    if (path.includes("/auth/me")) {
      body = { id: 101, email: "crm-admin@example.com", role: { name: "crm_org_admin" }, is_superuser: false };
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (path === "/automation/module-info") {
      body = { module: "automation", title: "Automation Studio" };
    } else if (path === "/automation/workflows") {
      body = method === "GET" ? { items: automationFixtures.workflows, total: 1 } : { id: 2, name: "Quote discount approval", module_name: "crm", record_type: "quote", is_active: true };
    } else if (path.includes("/automation/workflows/1/test")) {
      body = { id: 2, workflow_id: 1, module_name: "crm", record_type: "quote", status: "success", result_json: { actions: [] } };
    } else if (path === "/automation/blueprints") {
      body = method === "GET" ? { items: automationFixtures.blueprints, total: 1 } : { id: 2, name: "Deal Qualification Blueprint", module_name: "crm", record_type: "deal" };
    } else if (path.includes("/automation/blueprints/1/validate-transition")) {
      body = { allowed: true, requires_approval: false };
    } else if (path === "/automation/approvals") {
      body = method === "GET" ? { items: automationFixtures.approvals, total: 1 } : { id: 2, module_name: "crm", record_type: "quote", record_id: 501, status: "draft" };
    } else if (path === "/automation/approvals/rules") {
      body = { id: 1, name: "Quote margin approval" };
    } else if (path === "/automation/assignment-rules") {
      body = method === "GET" ? { items: automationFixtures.assignments, total: 1 } : { id: 2, name: "Website lead assignment" };
    } else if (path.includes("/automation/assignment-rules/1/test")) {
      body = { matched: true, assignment: { owner_strategy: "round_robin" } };
    } else if (path === "/automation/cadences") {
      body = method === "GET" ? { items: automationFixtures.cadences, total: 1 } : { id: 2, name: "New lead nurture", status: "active" };
    } else if (path.includes("/automation/cadences/1/enroll")) {
      body = { id: 10, status: "scheduled" };
    } else if (path === "/automation/webhooks") {
      body = method === "GET" ? { items: automationFixtures.webhooks, total: 1 } : { id: 2, name: "Revenue operations hook", target_url: "https://example.com/hooks/revenue" };
    } else if (path.includes("/automation/webhooks/1/test")) {
      body = { id: 3, status: "success", result_json: { delivery: "logged_only" } };
    } else if (path === "/automation/logs") {
      body = { items: automationFixtures.logs, total: 1 };
    } else if (path.includes("/automation/logs/1/retry")) {
      body = { id: 4, status: "success" };
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectAutomationRoute(page: Page, route: string, text: RegExp | string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(new RegExp(`${route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator("body")).toContainText(text);
}

