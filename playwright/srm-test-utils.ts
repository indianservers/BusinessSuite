import { expect, type Page } from "../frontend/node_modules/playwright/test";

export type SRMRole = "admin" | "srm_admin" | "srm_sales_manager" | "srm_finance_manager" | "srm_revenue_manager" | "srm_sales_executive" | "srm_collection_executive" | "srm_business_owner" | "srm_viewer" | "employee";

const users: Record<SRMRole, { id: number; email: string; role: string; is_superuser: boolean; employee_id: number | null }> = {
  admin: { id: 100, email: "admin@example.com", role: "admin", is_superuser: true, employee_id: null },
  srm_admin: { id: 101, email: "admin@srm.example.com", role: "srm_admin", is_superuser: false, employee_id: null },
  srm_sales_manager: { id: 102, email: "manager@srm.example.com", role: "srm_sales_manager", is_superuser: false, employee_id: null },
  srm_finance_manager: { id: 103, email: "finance@srm.example.com", role: "srm_finance_manager", is_superuser: false, employee_id: null },
  srm_revenue_manager: { id: 104, email: "revenue@srm.example.com", role: "srm_revenue_manager", is_superuser: false, employee_id: null },
  srm_sales_executive: { id: 105, email: "sales@srm.example.com", role: "srm_sales_executive", is_superuser: false, employee_id: null },
  srm_collection_executive: { id: 106, email: "collections@srm.example.com", role: "srm_collection_executive", is_superuser: false, employee_id: null },
  srm_business_owner: { id: 107, email: "owner@srm.example.com", role: "srm_business_owner", is_superuser: false, employee_id: null },
  srm_viewer: { id: 108, email: "viewer@srm.example.com", role: "srm_viewer", is_superuser: false, employee_id: null },
  employee: { id: 109, email: "employee@srm.example.com", role: "employee", is_superuser: false, employee_id: 109 },
};

export const srmRoutes = [
  "/srm",
  "/srm/dashboard",
  "/srm/sales-orders",
  "/srm/contracts",
  "/srm/engagements",
  "/srm/billing-plans",
  "/srm/invoice-drafts",
  "/srm/invoices",
  "/srm/collections",
  "/srm/revenue-recognition",
  "/srm/profitability",
  "/srm/customer-360",
  "/srm/reports",
  "/srm/settings",
];

export async function authenticate(page: Page, role: SRMRole) {
  const user = users[role];
  await installApiStubs(page, user);
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "srm-token",
      refreshToken: "srm-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: {
        accessToken: "srm-token",
        refreshToken: "srm-refresh",
        user: authUser,
        isAuthenticated: true,
      },
      version: 0,
    }));
  }, user);
}

export async function installApiStubs(page: Page, user = users.srm_admin) {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let body: unknown = method === "GET" ? [] : {};

    if (path.includes("/auth/me")) {
      body = { id: user.id, email: user.email, role: { name: user.role }, is_superuser: user.is_superuser, employee_id: user.employee_id };
    } else if (path.includes("/auth/sso/providers")) {
      body = [];
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (path.startsWith("/srm")) {
      if (isForbiddenSrmMutation(user.role, method, path)) {
        await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Forbidden SRM action" }) });
        return;
      }
      body = srmResponse(path, method);
    } else if (path.startsWith("/crm/deals/501")) {
      body = crmDealWithSrmLinks();
    } else if (path.startsWith("/project-management/projects/301/tasks")) {
      body = [];
    } else if (path.startsWith("/project-management/dashboard/301")) {
      body = { project: pmsProjectWithSrmLinks(), metrics: { total_tasks: 0, completed_tasks: 0, overdue_tasks: 0, high_risks: 0 } };
    } else if (path.startsWith("/project-management/projects/301")) {
      body = pmsProjectWithSrmLinks();
    } else if (path.startsWith("/reports")) {
      body = {};
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

function isForbiddenSrmMutation(role: string, method: string, path: string) {
  if (method === "GET") return false;
  if (role === "admin" || role === "srm_admin") return false;
  if (role === "srm_finance_manager") return path.includes("/settings");
  if (role === "srm_collection_executive") return path.includes("/settings") || path.includes("/invoices/1/lines");
  if (role === "srm_sales_executive") return path.includes("/invoices/") || path.includes("/receipts/") || path.includes("/settings");
  if (role === "srm_viewer" || role === "srm_business_owner" || role === "employee") return true;
  return false;
}

export async function expectHealthySrmRoute(page: Page, route: string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(route)}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator(".vite-error-overlay, #webpack-dev-server-client-overlay")).toHaveCount(0);
  await expect(page.locator("body")).toContainText(/SRM|Sales|Revenue|Invoice|Collection|Profitability|Engagement/i, { timeout: 20_000 });
}

export async function expectDenied(page: Page, route: string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
}

function srmResponse(path: string, method: string) {
  if (method !== "GET") {
    if (path.includes("/from-crm/deals/501/create-sales-order")) return handoffPayload(false);
    if (path === "/srm/sales-orders") return { id: 1, order_number: "SO-000001", customer_id: 10, status: "draft", total_amount: 250000 };
    if (path.includes("/sales-orders/1/lines")) return { id: 1, sales_order_id: 1, description: "Implementation line", quantity: 1, unit_price: 250000, line_total: 250000 };
    if (path.includes("/sales-orders/1/submit")) return { id: 1, order_number: "SO-000001", status: "pending_approval" };
    if (path.includes("/invoices/draft-from-sales-order/1")) return invoicePayload({ source_type: "sales_order" });
    if (path.includes("/invoices/draft-from-engagement/2")) return invoicePayload({ source_type: "engagement" });
    if (path.includes("/invoices/draft-from-billing-milestone/1")) return invoicePayload({ source_type: "billing_milestone" });
    if (path.includes("/invoices/draft-from-pms-milestone/301")) return invoicePayload({ source_type: "pms_milestone" });
    if (path.includes("/invoices/draft-from-timesheets")) return { ...invoicePayload({ source_type: "timesheet" }), time_log_ids: [901] };
    if (path.includes("/invoices/manual")) return invoicePayload({ source_type: "manual" });
    if (path.includes("/invoices/1/lines")) return { id: 2, description: "Additional line", source_type: "manual", line_total: 5900 };
    if (path.includes("/invoices/1/approve")) return invoicePayload({ status: "approved" });
    if (path.includes("/invoices/1/send")) return invoicePayload({ status: "sent", sent_at: "2026-06-05T00:00:00Z" });
    if (path.includes("/receipts/1/confirm")) return { id: 1, receipt_number: "RCT-000001", customer_id: 10, status: "confirmed", amount: 100000, unallocated_amount: 100000 };
    if (path.includes("/receipts/1/allocate")) return { receipt: { id: 1, receipt_number: "RCT-000001", status: "partially_allocated", amount: 100000, unallocated_amount: 50000 }, invoice: invoicePayload({ status: "partially_paid", paid_amount: 50000, balance_amount: 100000 }), allocation: { id: 1, amount: 50000 } };
    if (path.includes("/receipts")) return { id: 1, receipt_number: "RCT-000001", customer_id: 10, status: "draft", amount: 100000, unallocated_amount: 100000 };
    if (path.includes("/collections/reminders/send")) return { id: 1, reminder_type: "email", status: "sent", message: "Payment reminder" };
    if (path.includes("/collections/1/escalate")) return { invoice: invoicePayload({ status: "overdue" }), escalation: { id: 2, reminder_type: "escalation", status: "sent" } };
    if (path.includes("/collections/1/write-off-request")) return { invoice: invoicePayload({ status: "sent" }), write_off_request: { id: 3, reminder_type: "write_off_request", status: "queued" } };
    if (path.includes("/sales-orders/1/approve")) return { id: 1, order_number: "SO-000001", status: "approved" };
    if (path.includes("/sales-orders/1/confirm")) return { sales_order: { id: 1, order_number: "SO-000001", status: "confirmed" }, billing_plan: { id: 4, name: "Milestone billing" } };
    if (path === "/srm/contracts") return { id: 3, contract_number: "CTR-000001", title: "Managed Services", status: "draft", customer_id: 10, contract_value: 250000 };
    if (path === "/srm/engagements") return { id: 2, engagement_number: "ENG-000001", name: "Delivery engagement", status: "created", customer_id: 10, sales_order_id: 1 };
    if (path === "/srm/billing-plans") return { id: 4, name: "Milestone billing", status: "draft", total_amount: 250000 };
    if (path.includes("/billing-plans/4/milestones")) return { id: 1, billing_plan_id: 4, name: "Go-live milestone", amount: 250000, status: "ready" };
    if (path.includes("/engagements/2/create-pms-project")) return { idempotent: false, engagement: { id: 2, pms_project_id: 301 }, project: pmsProjectWithSrmLinks() };
    if (path.includes("/sales-orders/1/billing-plan")) return { id: 4, name: "Milestone billing", status: "draft", total_amount: 250000 };
    if (path.includes("/settings/")) return { id: 1, key: path.split("/").pop(), value_json: { value: "saved" } };
    return { id: 1, status: "updated" };
  }
  if (path.includes("/module-info")) return { key: "srm", label: "Sales & Revenue Management", api_prefix: "/api/v1/srm" };
  if (path.includes("/by-crm-deal/501")) return handoffPayload(true);
  if (path.includes("/engagements/2/lifecycle")) {
    return {
      engagement: { id: 2, engagement_number: "ENG-000001", crm_deal_id: 501, sales_order_id: 1, pms_project_id: 301, status: "project_created" },
      sales_order: { id: 1, order_number: "SO-000001", crm_deal_id: 501, status: "confirmed" },
      contract: { id: 3, contract_number: "CTR-000001", status: "active" },
      billing_plan: { id: 4, name: "Milestone billing", status: "active" },
      invoices: [],
      pms_project: pmsProjectWithSrmLinks(),
      links: [{ linked_module: "crm", linked_entity_type: "deal", linked_entity_id: 501 }, { linked_module: "pms", linked_entity_type: "project", linked_entity_id: 301 }],
      audit: [{ action: "crm_won_handoff" }, { action: "pms_project_created" }],
    };
  }
  if (path.includes("/dashboard") || path.includes("/reports/dashboard")) {
    return {
      total_sales_orders: 3,
      pending_approvals: 1,
      confirmed_sales_orders: 1,
      active_contracts: 1,
      active_engagements: 2,
      active_billing_plans: 1,
      invoice_drafts_pending: 1,
      approved_invoices: 1,
      sent_invoices: 1,
      total_invoiced_value: 250000,
      total_collected_value: 100000,
      outstanding_value: 150000,
      overdue_value: 50000,
      collection_risk: "high",
      gross_margin: 75000,
      cash_margin: 25000,
      recent_sales_orders: [{ id: 1, order_number: "SO-000001", title: "Implementation order", customer_id: 10, status: "confirmed", total_amount: 250000 }],
      recent_invoices: [{ id: 1, invoice_number: "INV-000001", status: "sent", customer_id: 10, total_amount: 250000, paid_amount: 100000, balance_amount: 150000 }],
      collection_alerts: [{ id: 1, invoice_number: "INV-000001", status: "sent", customer_id: 10, balance_amount: 50000, overdue_days: 12 }],
      revenue_trend: [{ date: "2026-06-01", event_type: "invoice_sent", amount: 250000 }],
      profitability_summary: { gross_margin: 75000, cash_margin: 25000, margin_status: "healthy" },
      crm_pms_activity_summary: { crm_linked_sales_orders: 2, pms_linked_engagements: 1 },
      sales_order_count: 3,
      engagement_count: 2,
      invoice_total: 250000,
      collected_total: 100000,
      outstanding_total: 150000,
    };
  }
  if (path.includes("/customer-360")) {
    const hasQuery = path.includes("customer-360") || true;
    return {
      matched: hasQuery,
      customer_id: 10,
      crm_references: { crm_deal_ids: [501], crm_quote_ids: [701], crm_company_ids: [301], crm_contact_ids: [401] },
      sales_orders: [{ id: 1, order_number: "SO-000001", title: "Implementation order", customer_id: 10, status: "confirmed", total_amount: 250000 }],
      contracts: [{ id: 1, contract_number: "CTR-000001", title: "Managed Services", customer_id: 10, status: "active", contract_value: 250000 }],
      engagements: [{ id: 2, engagement_number: "ENG-000001", name: "Delivery engagement", customer_id: 10, status: "project_created", budget_amount: 250000, pms_project_id: 301 }],
      billing_plans: [{ id: 4, name: "Milestone billing", engagement_id: 2, status: "active", total_amount: 250000 }],
      invoices: [{ id: 1, invoice_number: "INV-000001", status: "sent", customer_id: 10, total_amount: 250000, paid_amount: 100000, balance_amount: 150000 }],
      receipts: [{ id: 1, receipt_number: "RCT-000001", status: "allocated", customer_id: 10, amount: 100000 }],
      outstanding_amount: 150000,
      aging: { current_amount: 0, days_1_30: 150000, total_outstanding: 150000 },
      collection_reminders: [{ id: 1, reminder_type: "email", status: "sent", message: "Payment reminder" }],
      profitability: [{ id: 1, status: "healthy", collection_status: "outstanding", gross_margin: 75000 }],
      pms_projects: [pmsProjectWithSrmLinks()],
      timeline: [{ id: 1, type: "audit", action: "crm_won_handoff", entity_id: 1 }],
      audit_trail: [{ id: 1, action: "crm_won_handoff", entity_id: 1 }],
    };
  }
  if (path === "/srm/reports") {
    return {
      sales_order_report: { count: 3, orders: [{ id: 1, order_number: "SO-000001", status: "confirmed", total_amount: 250000 }] },
      contract_report: { count: 1, contracts: [{ id: 3, contract_number: "CTR-000001", status: "active", contract_value: 250000 }] },
      invoice_register: { count: 2, total: 250000, invoices: [invoicePayload({ status: "sent" })] },
      invoice_aging: [{ customer_id: 10, status: "overdue", total_outstanding: 150000 }],
      collection_aging: [{ customer_id: 10, status: "overdue", total_outstanding: 150000 }],
      customer_outstanding: { total_outstanding: 150000, customers: [{ customer_id: 10, total_outstanding: 150000 }] },
      engagement_profitability: [{ engagement_id: 2, collection_status: "partially_paid", gross_margin: 100000, cash_margin: 25000 }],
      project_profitability: [{ engagement_id: 2, project_id: 301, gross_margin: 100000, cash_margin: 25000 }],
      customer_profitability: [{ customer_id: 10, gross_margin: 100000, cash_margin: 25000 }],
      lead_to_cash_report: { crm_won_to_sales_order: 1, sales_order_to_engagement: 1, engagement_to_invoice: 1, invoice_to_collection: 1 },
      sales_to_delivery_margin: { gross_margin_total: 100000, delivery_budget: 120000 },
      cash_margin_report: { collected_total: 100000, cash_margin_total: 25000 },
    };
  }
  if (path.includes("/reports/lead-to-cash")) {
    return { crm_won_to_sales_order: 1, sales_order_to_engagement: 1, engagement_to_invoice: 1, invoice_to_collection: 1 };
  }
  if (path.includes("/collections/customer/10")) {
    return {
      invoices: [invoicePayload()],
      receipts: [{ id: 1, receipt_number: "RCT-000001", status: "confirmed", customer_id: 10, amount: 100000, unallocated_amount: 50000 }],
      reminders: [{ id: 1, reminder_type: "email", status: "sent", invoice_id: 1 }, { id: 2, reminder_type: "escalation", status: "sent", invoice_id: 1 }, { id: 3, reminder_type: "write_off_request", status: "queued", invoice_id: 1 }],
    };
  }
  if (path.includes("/sales-orders")) {
    return [{ id: 1, order_number: "SO-000001", title: "Implementation order", customer_id: 10, status: "confirmed", total_amount: 250000, created_at: "2026-06-04T00:00:00Z" }];
  }
  if (path.includes("/contracts")) {
    return [{ id: 1, contract_number: "CTR-000001", title: "Managed Services", customer_id: 10, status: "active", contract_value: 250000 }];
  }
  if (path.includes("/engagements")) {
    return [{ id: 1, engagement_number: "ENG-000001", name: "Delivery engagement", customer_id: 10, status: "delivery_started", budget_amount: 250000 }];
  }
  if (path.includes("/billing-plans")) {
    return [{ id: 1, name: "Milestone billing", engagement_id: 1, status: "active", total_amount: 250000 }];
  }
  if (path.includes("/invoice-drafts")) {
    return [{ id: 1, source_type: "sales_order", status: "draft", customer_id: 10, total_amount: 250000 }];
  }
  if (path.includes("/invoices")) {
    if (path.includes("/invoices/1")) return invoicePayload({ lines: [{ id: 1, description: "Implementation milestone", source_type: "sales_order", line_total: 250000 }], history: [{ id: 1, to_status: "draft" }, { id: 2, to_status: "approved" }], allocations: [{ id: 1, receipt_number: "RCT-000001", amount: 100000 }] });
    return [invoicePayload()];
  }
  if (path.includes("/collections/aging")) {
    return [{ customer_id: 10, current_amount: 0, days_1_30: 150000, total_outstanding: 150000 }];
  }
  if (path.includes("/profitability")) {
    return [{
      id: 1,
      engagement_id: 1,
      status: "healthy",
      quoted_value: 250000,
      sales_order_value: 250000,
      contract_value: 250000,
      billing_plan_value: 250000,
      invoiced_amount: 150000,
      collected_amount: 50000,
      outstanding_amount: 100000,
      overdue_amount: 25000,
      delivery_budget: 120000,
      approved_timesheet_cost: 65000,
      employee_cost: 50000,
      gross_margin: 100000,
      cash_margin: 25000,
      gross_margin_percent: 40,
      cash_margin_percent: 10,
      collection_status: "partially_paid",
    }];
  }
  if (path.includes("/settings")) {
    return [
      { id: 1, key: "invoice_number_prefix", value_json: { value: "INV" } },
      { id: 2, key: "sales_order_number_prefix", value_json: { value: "SO" } },
      { id: 3, key: "contract_number_prefix", value_json: { value: "CTR" } },
      { id: 4, key: "default_payment_terms", value_json: { value: "Net 30" } },
      { id: 5, key: "default_tax_vat_settings", value_json: { value: "GST 18%" } },
      { id: 6, key: "default_billing_plan_rules", value_json: { value: "Milestone billing" } },
      { id: 7, key: "collection_reminder_templates", value_json: { value: "Reminder, overdue, escalation" } },
      { id: 8, key: "escalation_thresholds", value_json: { value: "7, 15, 30 days" } },
      { id: 9, key: "write_off_approval_required", value_json: { value: true } },
      { id: 10, key: "dashboard_visibility_preferences", value_json: { value: "Revenue, collections, profitability" } },
    ];
  }
  return [];
}

function invoicePayload(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    invoice_number: "INV-000001",
    status: "draft",
    customer_id: 10,
    source_type: "sales_order",
    source_id: 1,
    total_amount: 250000,
    paid_amount: 100000,
    balance_amount: 150000,
    created_by: 101,
    approval_status: "Pending",
    ...overrides,
  };
}

function handoffPayload(idempotent: boolean) {
  return {
    idempotent,
    sales_order: { id: 1, order_number: "SO-000001", title: "ERP rollout", crm_deal_id: 501, status: "confirmed", total_amount: 250000 },
    engagement: { id: 2, engagement_number: "ENG-000001", name: "ERP rollout delivery", crm_deal_id: 501, pms_project_id: 301, status: "project_created" },
    contract: { id: 3, contract_number: "CTR-000001", title: "Contract for ERP rollout", status: "active" },
    billing_plan: { id: 4, name: "Milestone billing", status: "active", total_amount: 250000 },
    pms_project: pmsProjectWithSrmLinks(),
  };
}

function crmDealWithSrmLinks() {
  return {
    id: 501,
    entity: "deals",
    name: "ERP rollout",
    status: "Won",
    amount: 250000,
    owner_user_id: 102,
    customFields: [],
    timeline: [{ id: 1, activity_type: "srm_handoff", title: "SRM commercial handoff created" }],
    related: {
      srm: {
        salesOrder: { id: 1, order_number: "SO-000001", title: "ERP rollout", status: "confirmed" },
        engagement: { id: 2, engagement_number: "ENG-000001", name: "ERP rollout delivery", status: "project_created" },
        contract: { id: 3, contract_number: "CTR-000001", title: "Contract for ERP rollout", status: "active" },
        billingPlan: { id: 4, name: "Milestone billing", status: "active" },
        pmsProject: { id: 301, project_key: "PMS-301", name: "ERP rollout delivery" },
      },
    },
  };
}

function pmsProjectWithSrmLinks() {
  return {
    id: 301,
    project_key: "PMS-301",
    name: "ERP rollout delivery",
    description: "Created from SRM engagement",
    status: "Active",
    priority: "High",
    health: "Green",
    progress_percent: 15,
    budget_amount: 250000,
    srm_links: {
      engagement: { id: 2, engagement_number: "ENG-000001", name: "ERP rollout delivery" },
      sales_order: { id: 1, order_number: "SO-000001", title: "ERP rollout" },
      contract: { id: 3, contract_number: "CTR-000001", title: "Contract for ERP rollout" },
      billing_plan: { id: 4, name: "Milestone billing", status: "active" },
    },
  };
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
