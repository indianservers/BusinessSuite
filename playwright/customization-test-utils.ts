import { expect, type Page } from "../frontend/node_modules/playwright/test";

export async function authenticateCustomization(page: Page, role = "crm_org_admin") {
  await installCustomizationApiStubs(page);
  const user = { id: role === "employee" ? 301 : 101, email: `${role}@example.com`, role, is_superuser: role === "admin", employee_id: null };
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "customization-token",
      refreshToken: "customization-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: { accessToken: "customization-token", refreshToken: "customization-refresh", user: authUser, isAuthenticated: true },
      version: 0,
    }));
  }, user);
}

export async function installCustomizationApiStubs(page: Page) {
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
    } else if (path === "/customization/modules") {
      body = method === "GET" ? { items: [{ id: 1, module_api_name: "partner_projects", module_label: "Partner Project", plural_label: "Partner Projects", enabled: true }], total: 1 } : { id: 2, module_api_name: "partner_projects", module_label: "Partner Project", enabled: true };
    } else if (path === "/customization/fields") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", field_api_name: "project_name", field_label: "Project Name", field_type: "text", visible: true }], total: 1 } : { id: 2, module_name: "partner_projects", field_label: "Project Name", field_type: "text" };
    } else if (path === "/customization/layouts") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", name: "Default Detail", layout_type: "detail" }], total: 1 } : { id: 2, name: "Default Detail", module_name: "partner_projects" };
    } else if (path === "/customization/views") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", name: "Open Projects" }], total: 1 } : { id: 2, name: "Open Projects" };
    } else if (path === "/customization/kanban") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", name: "Project Kanban", group_by_field: "status" }], total: 1 } : { id: 2, name: "Project Kanban" };
    } else if (path === "/customization/validation-rules") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", name: "Budget must be positive", active: true }], total: 1 } : { id: 2, name: "Budget must be positive" };
    } else if (path === "/customization/buttons") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", label: "Submit Approval", action_type: "submit_approval" }], total: 1 } : { id: 2, label: "Submit Approval" };
    } else if (path === "/customization/picklists") {
      body = method === "GET" ? { items: [{ id: 1, api_name: "project_statuses", label: "Project Statuses" }], total: 1 } : { id: 2, api_name: "project_statuses", label: "Project Statuses" };
    } else if (path === "/customization/formulas") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", field_api_name: "margin", expression: "revenue - cost" }], total: 1 } : { id: 2, field_api_name: "margin" };
    } else if (path === "/customization/formulas/test") {
      body = { valid: true, result: "750" };
    } else if (path === "/customization/rollups") {
      body = method === "GET" ? { items: [{ id: 1, module_name: "partner_projects", field_api_name: "total_revenue", aggregate_function: "sum" }], total: 1 } : { id: 2, field_api_name: "total_revenue" };
    } else if (path === "/customization/audit-logs") {
      body = { items: [{ id: 1, entity_type: "module", action: "created" }], total: 1 };
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectCustomizationRoute(page: Page, route: string, text: string | RegExp) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(new RegExp(`${route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator("body")).toContainText(text);
}

