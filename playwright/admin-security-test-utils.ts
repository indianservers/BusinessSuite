import { expect, type Page } from "../frontend/node_modules/playwright/test";

type Role = "crm_org_admin" | "ceo" | "employee";

export async function authenticateAdminSecurity(page: Page, role: Role = "crm_org_admin") {
  await installAdminSecurityApiStubs(page, role);
  const user = { id: 801, email: `${role}@example.com`, role, is_superuser: role === "crm_org_admin", employee_id: null };
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "phase8-token",
      refreshToken: "phase8-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: { accessToken: "phase8-token", refreshToken: "phase8-refresh", user: authUser, isAuthenticated: true },
      version: 0,
    }));
  }, user);
}

export async function installAdminSecurityApiStubs(page: Page, role: Role = "crm_org_admin") {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let status = 200;
    let body: unknown = { items: [], total: 0 };
    const restricted = role === "employee" && path.startsWith("/admin");

    if (path.includes("/auth/me")) {
      body = { id: 801, email: `${role}@example.com`, role: { name: role }, is_superuser: role === "crm_org_admin" };
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (restricted) {
      status = 403;
      body = { detail: "Forbidden" };
    } else if (path === "/admin/security") {
      body = { profiles: 2, roles: 3, field_rules: 1, audit_logs: 5, duplicate_rules: 1 };
    } else if (path === "/admin/profiles") {
      body = method === "POST" ? { id: 9, name: "Sales Profile", active: true } : { items: [{ id: 1, name: "CRM Admin", active: true }], total: 1 };
    } else if (path.includes("/admin/profiles/") && path.endsWith("/permissions")) {
      body = { items: [{ permission: "admin_security_view" }], total: 1 };
    } else if (path === "/admin/roles") {
      body = method === "POST" ? { id: 2, name: "Regional Sales Manager", active: true } : { items: [{ id: 2, name: "Sales Manager", active: true }], total: 1 };
    } else if (path === "/admin/roles/hierarchy") {
      body = { id: 1, parent_role_id: 1, child_role_id: 2 };
    } else if (path === "/admin/field-security") {
      body = method === "POST" ? { id: 1, module_name: "leads", field_name: "annual_revenue", can_edit: false, mask_value: true } : { items: [{ id: 1, module_name: "leads", field_name: "annual_revenue", can_view: true, can_edit: false, mask_value: true }], total: 1 };
    } else if (path === "/admin/security/validate-field-update") {
      status = 422;
      body = { detail: "Field annual_revenue is read-only for this profile" };
    } else if (path === "/admin/record-sharing-rules") {
      body = method === "POST" ? { id: 1, rule_name: "Share enterprise deals", access_level: "read" } : { items: [{ id: 1, rule_name: "Share enterprise deals", access_level: "read" }], total: 1 };
    } else if (path === "/admin/records/share" || path === "/admin/records/unshare") {
      body = { id: 1, module_name: "deals", access_level: "read" };
    } else if (path === "/admin/data-sharing-rules") {
      body = method === "POST" ? { id: 1, name: "Branch data policy", access_level: "read" } : { items: [{ id: 1, name: "Branch data policy", access_level: "read" }], total: 1 };
    } else if (path === "/admin/ip-restrictions") {
      body = method === "POST" ? { id: 1, cidr: "203.0.113.0/24", action: "allow" } : { items: [{ id: 1, cidr: "203.0.113.0/24", action: "allow" }], total: 1 };
    } else if (path === "/admin/audit-logs") {
      body = { items: [{ id: 1, action: "profile_created", module_name: "admin", entity_type: "profile" }], total: 1 };
    } else if (path === "/admin/imports/upload") {
      body = { id: 77, module_name: "leads", filename: "phase8-leads.csv", status: "uploaded" };
    } else if (path === "/admin/imports/77/map-fields") {
      body = { id: 77, status: "mapped" };
    } else if (path === "/admin/imports/77/run") {
      body = { id: 77, status: "completed" };
    } else if (path === "/admin/imports/77/errors") {
      body = { items: [{ id: 1, row_number: 2, status: "failed", error_message: "Duplicate email" }], total: 1 };
    } else if (path === "/admin/duplicate-rules") {
      body = method === "POST" ? { id: 1, name: "Lead email duplicate", module_name: "leads" } : { items: [{ id: 1, name: "Lead email duplicate", module_name: "leads" }], total: 1 };
    } else if (path === "/admin/duplicates/scan") {
      body = { candidates_created: 1 };
    } else if (path === "/admin/duplicates/candidates") {
      body = { items: [{ id: 1, module_name: "leads", status: "open" }], total: 1 };
    } else if (path === "/admin/duplicates/merge") {
      body = { id: 1, module_name: "leads", winner_record_id: 1 };
    } else if (path === "/admin/export-controls") {
      body = method === "POST" ? { id: 1, module_name: "deals", require_approval: true, watermark: true } : { items: [{ id: 1, module_name: "deals", require_approval: true, watermark: true }], total: 1 };
    } else if (path === "/admin/backups") {
      body = { items: [{ id: 1, scope: "crm", status: "requested" }], total: 1 };
    } else if (path === "/admin/backups/request") {
      body = { id: 1, scope: "crm", status: "requested" };
    } else if (path === "/admin/compliance") {
      body = method === "POST" ? { id: 1, setting_key: "consent_required", active: true } : { items: [{ id: 1, setting_key: "consent_required", active: true }], total: 1 };
    } else if (path === "/admin/data-retention") {
      body = method === "POST" ? { id: 1, module_name: "leads", retention_days: 2555, active: true } : { items: [{ id: 1, module_name: "leads", retention_days: 2555, active: true }], total: 1 };
    }

    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectAdminSecurityShell(page: Page) {
  await expect(page.getByText("Enterprise Security and Data Governance")).toBeVisible();
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
}
