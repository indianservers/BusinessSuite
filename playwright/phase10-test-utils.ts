import { expect, type Page } from "../frontend/node_modules/playwright/test";

type Role = "crm_org_admin" | "crm_sales_executive" | "employee" | "ceo";

export async function authenticatePhase10(page: Page, role: Role = "crm_org_admin") {
  await installPhase10ApiStubs(page, role);
  const user = { id: 901, email: `${role}@example.com`, role, is_superuser: role === "crm_org_admin", employee_id: null };
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "phase10-token",
      refreshToken: "phase10-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: { accessToken: "phase10-token", refreshToken: "phase10-refresh", user: authUser, isAuthenticated: true },
      version: 0,
    }));
  }, user);
}

export async function installPhase10ApiStubs(page: Page, role: Role = "crm_org_admin") {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let status = 200;
    let body: unknown = {};
    if (path.includes("/auth/me")) {
      body = { id: 901, email: `${role}@example.com`, role: { name: role }, is_superuser: role === "crm_org_admin" };
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (role === "employee" && (path.startsWith("/developer") || path.startsWith("/marketplace") || path.startsWith("/admin") || path.startsWith("/mobile"))) {
      status = 403;
      body = { detail: "Forbidden" };
    } else if (path === "/customer-portal/me") {
      body = { user: { id: 1, display_name: "Customer User", portal_type: "customer" }, customer_ids: [100] };
    } else if (path === "/customer-portal/quotes") {
      body = { items: [{ id: 1, quote_number: "QT-001", status: "Sent", total_amount: 10000 }], total: 1 };
    } else if (path === "/customer-portal/invoices") {
      body = { items: [{ id: 2, invoice_number: "INV-001", status: "sent", balance_amount: 5000 }], total: 1 };
    } else if (path === "/customer-portal/projects") {
      body = { items: [{ id: 3, name: "Implementation", status: "Active" }], total: 1 };
    } else if (path === "/partner-portal/dashboard") {
      body = { submitted_leads: 1, open_deals: 0, commission_status: "placeholder" };
    } else if (path === "/partner-portal/leads") {
      body = method === "POST" ? { id: 9, company_name: "Partner Co", source: "Partner Portal" } : { items: [{ id: 9, company_name: "Partner Co", status: "New" }], total: 1 };
    } else if (path === "/mobile/check-in") {
      body = method === "POST" ? { id: 1, customer_name: "Acme", status: "checked_in" } : { items: [{ id: 1, customer_name: "Acme", status: "checked_in" }], total: 1 };
    } else if (path === "/developer/api-keys") {
      body = method === "POST" ? { id: 1, name: "Integration key", key_prefix: "bs_abc123", api_key: "bs_secret_once", scopes_json: ["crm.read"], status: "active" } : { items: [{ id: 1, name: "Integration key", key_prefix: "bs_abc123", scopes_json: ["crm.read"], status: "active" }], total: 1 };
    } else if (path === "/developer/webhooks") {
      body = method === "POST" ? { id: 2, name: "CRM event webhook", target_url: "https://example.com/business-suite/webhook", status: "active" } : { items: [{ id: 2, name: "CRM event webhook", target_url: "https://example.com/business-suite/webhook", status: "active" }], total: 1 };
    } else if (path.includes("/developer/webhooks/") && path.endsWith("/test")) {
      body = { id: 3, event_type: "developer.test", status: "queued" };
    } else if (path.includes("/developer/webhooks/") && path.endsWith("/replay")) {
      body = { id: 4, event_type: "developer.replay", status: "queued" };
    } else if (path === "/developer/api-logs") {
      body = { items: [{ id: 1, endpoint: "/api/v1/developer/api-keys", method: "POST", status_code: 201 }], total: 1 };
    } else if (path === "/developer/docs") {
      body = { title: "Business Suite Developer Hub", rate_limit: "placeholder", webhook_security: "HTTPS endpoints" };
    } else if (path === "/marketplace/apps") {
      body = method === "POST" ? { id: 5, name: "Internal CRM Extension", internal_only: true, status: "listed" } : { items: [{ id: 5, name: "Internal CRM Extension", internal_only: true, status: "listed" }], total: 1 };
    } else if (path.includes("/marketplace/apps/") && path.endsWith("/install")) {
      body = { id: 6, app_id: 5, status: "installed" };
    } else if (path === "/marketplace/installed") {
      body = { items: [{ id: 6, app_id: 5, status: "installed" }], total: 1 };
    } else if (path === "/admin/sandbox") {
      body = { items: [{ id: 7, name: "UAT Sandbox", status: "requested", access_url_placeholder: "Generated by deployment infrastructure" }], total: 1 };
    } else if (path === "/admin/sandbox/create") {
      body = { id: 7, name: "UAT Sandbox", status: "requested", access_url_placeholder: "Generated by deployment infrastructure" };
    } else if (path.includes("/admin/sandbox/") && path.endsWith("/refresh")) {
      body = { id: 8, status: "queued", detail_json: { production_writes_blocked: true } };
    } else if (path === "/admin/company-settings") {
      body = { id: 1, company_name: "Business Suite", base_currency: "INR", timezone: "Asia/Calcutta" };
    } else if (path === "/admin/feature-flags") {
      body = method === "PUT" ? { id: 1, feature_key: "portals", enabled: true } : { items: [{ id: 1, feature_key: "portals", enabled: true }], total: 1 };
    } else if (path === "/admin/subscription") {
      body = { id: 1, edition: "ultimate", status: "active", admin_override: true };
    } else if (path === "/admin/subscription-plans") {
      body = { items: [{ id: 1, code: "starter" }, { id: 4, code: "ultimate" }], total: 2 };
    } else if (path === "/admin/usage") {
      body = { items: [{ id: 1, metric_key: "portal_users", metric_value: 2 }], total: 1 };
    } else {
      body = { items: [], total: 0 };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectNoAccessDenied(page: Page) {
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
}
