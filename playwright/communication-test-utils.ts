import { expect, type Page } from "../frontend/node_modules/playwright/test";

type Role = "crm_org_admin" | "crm_marketing_user" | "crm_sales_manager" | "crm_sales_executive" | "crm_viewer" | "employee";

export async function authenticateCommunication(page: Page, role: Role = "crm_org_admin") {
  await installCommunicationApiStubs(page, role);
  const user = { id: role === "employee" ? 301 : 101, email: `${role}@example.com`, role, is_superuser: role === "crm_org_admin", employee_id: null };
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "communication-token",
      refreshToken: "communication-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: { accessToken: "communication-token", refreshToken: "communication-refresh", user: authUser, isAuthenticated: true },
      version: 0,
    }));
  }, user);
}

export async function installCommunicationApiStubs(page: Page, role: Role = "crm_org_admin") {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let status = 200;
    let body: unknown = {};
    if (path.includes("/auth/me")) {
      body = { id: 101, email: `${role}@example.com`, role: { name: role }, is_superuser: role === "crm_org_admin" };
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (path === "/communication/module-info") {
      body = { module: "communication", title: "Communication Hub" };
    } else if (path === "/communication/email-templates") {
      body = method === "GET" ? { items: [{ id: 1, name: "Welcome Lead", subject: "Hello {{name}}", module_name: "lead", active: true }], total: 1 } : { id: 2, name: "Welcome Lead", subject: "Hello {{name}}", module_name: "lead", active: true };
    } else if (path === "/communication/emails/send") {
      body = { id: 10, related_record_type: "lead", related_record_id: 1, to_email: "lead@example.com", subject: "Follow up", status: "blocked", error_message: "No configured communication email provider" };
    } else if (path === "/communication/emails/draft") {
      body = { id: 11, related_record_type: "lead", related_record_id: 1, to_email: "lead@example.com", subject: "Draft", status: "draft" };
    } else if (path.startsWith("/communication/timeline/")) {
      body = { items: [{ id: 1, record_type: "lead", record_id: 1, channel: "email", event_type: "blocked", subject: "Follow up", summary: "No configured communication email provider" }], total: 1 };
    } else if (path === "/communication/webforms") {
      body = method === "GET" ? { items: [{ id: 1, name: "Lead Capture", public_slug: "lead-capture-phase-6", target_module: "lead", active: true }], total: 1 } : { id: 2, name: "Lead Capture", public_slug: "lead-capture-phase-6", target_module: "lead", active: true };
    } else if (path.startsWith("/public/webforms/") && path.endsWith("/submit")) {
      body = { status: "accepted", created_record_type: "lead", created_record_id: 88, duplicate_detected: false };
    } else if (path.startsWith("/public/webforms/")) {
      body = { id: 1, name: "Lead Capture", public_slug: "lead-capture-phase-6", target_module: "lead" };
    } else if (path === "/communication/auto-response-rules") {
      body = method === "GET" ? { items: [{ id: 1, name: "Reply", active: true }], total: 1 } : { id: 2, name: "Reply", active: true };
    } else if (path === "/communication/campaigns") {
      body = method === "GET" ? { items: [{ id: 1, name: "Nurture Campaign", type: "email", status: "draft" }], total: 1 } : { id: 2, name: "Nurture Campaign", type: "email", status: "draft" };
    } else if (path === "/communication/campaigns/1/preview") {
      body = { recipients: [{ record_type: "lead", record_id: 1, email: "lead@example.com", blocked: false }], total: 1, blocked_count: 0, rate_limit: 50 };
    } else if (path === "/communication/campaigns/1/send") {
      body = { id: 1, name: "Nurture Campaign", status: "completed", sent_count: 0, blocked_count: 1 };
    } else if (path === "/communication/consents") {
      body = { items: [{ id: 1, email: "blocked@example.com", consent_type: "email", status: "opted_out" }], total: 1 };
    } else if (path === "/communication/opt-out") {
      body = { id: 2, email: "blocked@example.com", channel: "email" };
    } else if (path === "/communication/whatsapp-templates") {
      body = method === "GET" ? { items: [{ id: 1, name: "Reminder", template_key: "crm_reminder", provider_status: "placeholder_only" }], total: 1 } : { id: 2, name: "Reminder", provider_status: "placeholder_only" };
    } else if (path === "/communication/delivery-logs") {
      body = { items: [{ id: 1, channel: "email", provider: "none", status: "blocked", error_message: "No configured communication email provider" }], total: 1 };
    } else if (path.startsWith("/crm/leads/1")) {
      body = { id: 1, full_name: "Nisha Rao", email: "nisha@example.com", phone: "9999999999", status: "Qualified", source: "Website", timeline: [], related: {}, customFields: [] };
    } else if (path.startsWith("/crm/")) {
      body = { items: [], total: 0 };
    } else if (role === "employee" && path.startsWith("/communication")) {
      status = 403;
      body = { detail: "Forbidden" };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}

export async function expectCommunicationRoute(page: Page, route: string, text: string | RegExp) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator("body")).toContainText(text);
}

