import { expect, type Page } from "../frontend/node_modules/playwright/test";

type Role =
  | "crm_org_admin"
  | "crm_sales_manager"
  | "crm_sales_executive"
  | "srm_finance_manager"
  | "srm_collection_executive"
  | "srm_viewer"
  | "employee";

export async function authenticateAi(page: Page, role: Role = "crm_org_admin") {
  await installAiApiStubs(page, role);
  const user = { id: 701, email: `${role}@example.com`, role, is_superuser: role === "crm_org_admin", employee_id: null };
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "ai-token",
      refreshToken: "ai-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: { accessToken: "ai-token", refreshToken: "ai-refresh", user: authUser, isAuthenticated: true },
      version: 0,
    }));
  }, user);
}

export async function installAiApiStubs(page: Page, role: Role = "crm_org_admin") {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let status = 200;
    let body: unknown = {};
    if (path.includes("/auth/me")) {
      body = { id: 701, email: `${role}@example.com`, role: { name: role }, is_superuser: role === "crm_org_admin" };
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (role === "employee" && path.startsWith("/ai")) {
      status = 403;
      body = { detail: "Forbidden" };
    } else if (path === "/ai/provider-settings") {
      body = method === "GET"
        ? { items: [{ id: 1, provider_name: "mock", model_name: "mock-business-suite", enabled: true, data_sharing_allowed: true }] }
        : { id: 2, provider_name: "mock", model_name: "mock-business-suite", enabled: true, data_sharing_allowed: true };
    } else if (path === "/ai/provider-settings/1/test") {
      body = { status: "ok", provider_configured: true, message: "Mock provider is ready for tests." };
    } else if (path === "/ai/prompt-templates") {
      body = method === "GET"
        ? { items: [{ id: 1, name: "CRM Record Summary", use_case: "summary", module_name: "crm", active: true }] }
        : { id: 2, name: "CRM Record Summary", use_case: "summary", module_name: "crm", active: true };
    } else if (path === "/ai/action-log") {
      body = { items: [{ id: 1, event_type: "ai_summary", status: "completed", module_name: "crm", record_type: "lead", record_id: 1, created_by: 701 }], total: 1 };
    } else if (path === "/ai/agent-action/preview") {
      body = { action: { id: 1, action_type: "draft_email", status: "previewed", requires_confirmation: true }, requires_confirmation: true, source_data_summary: { field_count: 3 } };
    } else if (path === "/ai/agent-action/confirm") {
      body = { action: { id: 1, action_type: "draft_email", status: "confirmed" }, result: { draft_only: true, message: "Action confirmed" } };
    } else if (path.startsWith("/ai/")) {
      body = {
        provider_configured: true,
        status: "completed",
        prompt_run_id: 10,
        module_name: path.includes("collection") ? "srm" : "crm",
        record_type: path.includes("deal") ? "deal" : "lead",
        source_data_summary: { field_count: 4, custom_field_count: 0 },
        confidence: 0.82,
        reasons: ["Mock provider", "Sanitized context"],
        output: {
          summary: "Mock AI output with evidence and confidence.",
          confidence: 0.82,
          reasons: ["Mock provider", "Sanitized context"],
          draft: { requires_review: true, subject: "Follow up" },
          workflow_json: { active: false },
        },
      };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectAiRoute(page: Page, route: string, text: string | RegExp) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator("body")).toContainText(text);
}

