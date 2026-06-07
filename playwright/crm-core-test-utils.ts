import { expect, type Page } from "../frontend/node_modules/playwright/test";

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export async function authenticateCrm(page: Page) {
  const user = { id: 100, email: "admin@example.com", role: "admin", is_superuser: true, employee_id: null };
  await page.addInitScript((authUser) => {
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: {
        accessToken: "crm-token",
        refreshToken: "crm-refresh",
        user: authUser,
        isAuthenticated: true,
      },
      version: 0,
    }));
  }, user);
  await page.route("**/api/v1/crm/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method() as Method;
    const body = crmResponse(path, method);
    await route.fulfill({ status: body.statusCode || 200, contentType: "application/json", body: JSON.stringify(body.payload ?? body) });
  });
  await page.route("**/api/v1/auth/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.includes("/auth/me")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...user, role: { name: user.role } }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/api/v1/notifications/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ unread: 0 }) });
  });
}

export async function expectCrmListPage(page: Page, route: string, heading: string, text: string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  await expect(page.getByPlaceholder("Search records, owners, companies...")).toHaveCount(1);
  await expect(page.getByText(text).first()).toBeVisible();
}

function crmResponse(path: string, method: Method) {
  if (method !== "GET") {
    if (path.includes("/pipeline-stages/reorder")) return { items: [pipelineStage(1), pipelineStage(2)], total: 2 };
    if (path.includes("/forecast/snapshot")) return { id: 10, snapshotName: "Manual CRM forecast snapshot", weightedAmount: 200000 };
    if (path === "/crm/targets") return target();
    if (path.includes("/crm/targets/")) return { ...target(), targetAmount: 1500000 };
    if (path.includes("/crm/territories/1/assign")) return { item: { id: 1, territoryId: 1, userId: 100, assignmentType: "owner" }, territory: territory() };
    if (path.includes("/leads/1/convert")) {
      return { lead: { ...leadDetail(), is_converted: true, status: "Converted" }, company: account(), contact: contact(), deal: deal() };
    }
    if (path.includes("/leads/1/qualify")) return { ...leadDetail(), status: "Qualified" };
    if (path.includes("/deals/1/mark-won")) return { ...deal(), status: "Won", wonAt: "2026-06-05T00:00:00Z" };
    if (path.includes("/deals/1/move-stage")) return { ...deal(), stageId: 2, probability: 80 };
    if (path.includes("/deals/1/mark-lost")) return { ...deal(), status: "Lost", lostReason: "Budget frozen" };
    if (path.includes("/activities/1/complete")) return { ...activity(), status: "Completed", completedAt: "2026-06-05T00:00:00Z" };
    if (path.includes("/quotes/1/lines")) return { id: 10, quoteId: 1, name: "Implementation", quantity: 1, unitPrice: 50000, lineTotal: 59000, quoteTotals: { grandTotal: 59000 } };
    if (path.includes("/quotes/1/calculate")) return { ...quoteDetail(), calculation: { subtotal: 50000, discountTotal: 0, taxTotal: 9000, grandTotal: 59000 } };
    if (path.includes("/quotes/1/submit")) return { ...quoteDetail(), status: "Pending Approval", approvalStatus: "pending" };
    if (path.includes("/quotes/1/approve")) return { ...quoteDetail(), status: "Approved", approvalStatus: "approved" };
    if (path.includes("/quotes/1/send")) return { ...quoteDetail(), status: "Sent", approvalStatus: "approved", pdfUrl: "/uploads/crm/quotes/QT-001.pdf" };
    if (path.includes("/quotes/1/accept")) return { ...quoteDetail(), status: "Accepted", srmConversion: { idempotent: false, conversionLog: { status: "converted" } } };
    if (path.includes("/quotes/1/new-version")) return { quote: { ...quoteDetail(), versionNumber: 2 }, version: { id: 2, versionNumber: 1 } };
    if (path.includes("/quotes/1/convert-to-srm")) return { idempotent: true, conversionLog: { status: "converted" }, quote: quoteDetail() };
    if (path.includes("/crm/cpq/evaluate")) return { ruleCount: 1, warnings: [{ rule: "High discount approval" }], recommendations: [] };
    return { id: 99, status: "Created" };
  }
  if (path === "/crm/dashboard" || path === "/crm") {
    return { summary: { leads: 1, qualifiedLeads: 1, contacts: 1, accounts: 1, openDeals: 1, pipelineValue: 250000, overdueActivities: 1 }, nextBestAction: "Follow up hot lead" };
  }
  if (path === "/crm/leads") return list([lead()]);
  if (path === "/crm/accounts" || path === "/crm/companies") return list([account()]);
  if (path === "/crm/contacts") return list([contact()]);
  if (path === "/crm/deals") return list([deal()]);
  if (path === "/crm/pipelines") return list([pipeline()]);
  if (path === "/crm/pipelines/1") return pipeline();
  if (path === "/crm/pipeline-stages") return list([pipelineStage(1), pipelineStage(2), pipelineStage(3)]);
  if (path === "/crm/forecast" || path === "/crm/forecast/by-owner") return forecast("owner");
  if (path === "/crm/forecast/by-team") return forecast("team");
  if (path === "/crm/forecast/by-territory") return forecast("territory");
  if (path === "/crm/targets") return { items: [target()], total: 1 };
  if (path === "/crm/targets/performance") return { items: [{ ...target(), achievedAmount: 750000, weightedAmount: 900000, invoicedAmount: 600000, collectedAmount: 450000, achievementPercent: 75, invoicePercent: 60, collectionPercent: 45 }], total: 1 };
  if (path === "/crm/funnel") return { items: funnelRows(), total: funnelRows().length };
  if (path === "/crm/lost-analysis") return lostAnalysis();
  if (path === "/crm/sales-performance") return { summary: forecast("owner").summary, items: [{ ownerId: 100, owner: "Ananya Rao", dealCount: 3, wonDeals: 1, lostDeals: 1, activityCount: 12, conversionRate: 50, weightedAmount: 200000, invoicedAmount: 120000, collectedAmount: 80000 }], total: 1 };
  if (path === "/crm/territories" || path === "/crm/reports/territories") return { items: [territory()], total: 1 };
  if (path === "/crm/activities") return list([activity()]);
  if (path === "/crm/products") return list([product()]);
  if (path === "/crm/products/1") return product();
  if (path === "/crm/services") return list([service()]);
  if (path === "/crm/services/1") return service();
  if (path === "/crm/price-books") return list([priceBook()]);
  if (path === "/crm/price-books/1") return priceBook();
  if (path === "/crm/quotes") return list([quote()]);
  if (path === "/crm/quotes/1") return quoteDetail();
  if (path === "/crm/quote-approvals") return list([{ id: 1, quoteId: 1, status: "pending", reason: "Discount approval", comments: "" }]);
  if (path === "/crm/cpq-rules") return list([{ id: 1, name: "High discount approval", ruleType: "approval", active: true }]);
  if (path === "/crm/guided-selling-flows") return list([{ id: 1, name: "Implementation discovery", active: true }]);
  if (path === "/crm/calendar") return { items: [{ id: "activity-1", title: "Discovery call", start: "2026-06-05T09:00:00Z", end: "2026-06-05T10:00:00Z", type: "meeting" }], total: 1 };
  if (path === "/crm/leads/1") return leadDetail();
  if (path === "/crm/accounts/1" || path === "/crm/companies/1") return accountDetail();
  if (path === "/crm/contacts/1") return contactDetail();
  if (path === "/crm/deals/1") return dealDetail();
  if (path === "/crm/deals/501") return dealDetail();
  if (path === "/crm/timeline/lead/1") return { items: timeline(), recordType: "lead", recordId: 1 };
  if (path === "/crm/roles") return {
    items: [
      { key: "crm_admin", permissions: ["crm_pipeline_manage", "crm_forecast_manage", "crm_targets_manage", "crm_territory_manage", "crm_sales_performance_view", "crm_products_manage", "crm_price_books_manage", "crm_quotes_approve", "crm_quotes_convert_to_srm", "crm_cpq_manage"] },
      { key: "sales_executive", permissions: ["crm_pipeline_view", "crm_forecast_view", "crm_targets_view", "crm_territory_view", "crm_sales_performance_view"] },
      { key: "business_owner", permissions: ["crm_pipeline_view", "crm_forecast_view", "crm_targets_view", "crm_territory_view", "crm_sales_performance_view"] },
      { key: "non_crm_employee", permissions: [] },
    ],
  };
  return list([]);
}

function list(items: unknown[]) {
  return { items, total: items.length, page: 1, per_page: 25, pages: 1 };
}

function lead() {
  return { id: 1, full_name: "Nisha Rao", fullName: "Nisha Rao", company_name: "Acme India", companyName: "Acme India", email: "nisha@example.com", source: "Website", status: "Qualified", ownerId: 100, updatedAt: "2026-06-05T00:00:00Z", leadScore: 82, scoreLabel: "Hot" };
}

function account() {
  return { id: 1, name: "Acme India", account_name: "Acme India", accountName: "Acme India", industry: "Software", phone: "+91 90000 00000", status: "Active", account_type: "Customer", ownerId: 100, updatedAt: "2026-06-05T00:00:00Z" };
}

function contact() {
  return { id: 1, full_name: "Nisha Rao", fullName: "Nisha Rao", email: "nisha@example.com", phone: "+91 90000 00001", job_title: "Founder", lifecycle_stage: "Customer", status: "Active", ownerId: 100, updatedAt: "2026-06-05T00:00:00Z" };
}

function deal() {
  return { id: 1, name: "Acme implementation", amount: 250000, currency: "INR", probability: 80, status: "Open", stage_id: 2, stageId: 2, pipeline_id: 1, pipelineId: 1, territoryId: 1, expected_close_date: "2026-06-30", expectedCloseDate: "2026-06-30", ownerId: 100, updatedAt: "2026-06-05T00:00:00Z" };
}

function pipeline() {
  return { id: 1, name: "Enterprise Sales", description: "Default B2B pipeline", is_default: true, isDefault: true, active: true };
}

function pipelineStage(id: number) {
  const names = ["Qualification", "Proposal", "Closed Won"];
  return { id, pipeline_id: 1, pipelineId: 1, name: names[id - 1] || "Stage", probability: id === 3 ? 100 : id * 30, position: id, orderIndex: id, stageType: id === 3 ? "won" : "open", active: true, color: "#2563eb", is_won: id === 3, is_lost: false };
}

function forecast(group: string) {
  return {
    summary: { pipelineAmount: 500000, weightedAmount: 200000, committedAmount: 250000, bestCaseAmount: 400000, upsideAmount: 80000, closedWonAmount: 100000, invoicedAmount: 120000, collectedAmount: 80000, scenarios: { conservative: 160000, expected: 200000, aggressive: 400000 } },
    items: [{ key: "100", label: group === "team" ? "Team 1" : group === "territory" ? "Territory 1" : "Ananya Rao", dealCount: 2, pipelineAmount: 500000, weightedAmount: 200000, committedAmount: 250000, invoicedAmount: 120000, collectedAmount: 80000 }],
    total: 1,
  };
}

function target() {
  return { id: 1, periodType: "monthly", periodStart: "2026-06-01", periodEnd: "2026-06-30", targetOwnerType: "user", targetOwnerId: 100, targetAmount: 1000000, currency: "INR" };
}

function territory() {
  return { id: 1, name: "West India", region: "West", country: "India", productLine: "Business Suite", serviceLine: "Implementation", managerId: 100, priority: 10, isActive: true, active: true, users: [{ id: 1, userId: 100 }] };
}

function funnelRows() {
  return [
    { stage: "Lead", count: 10, amount: 1000000, conversionRate: 100, stageToStageRate: 100 },
    { stage: "Qualified", count: 6, amount: 700000, conversionRate: 60, stageToStageRate: 60 },
    { stage: "Deal Won", count: 2, amount: 250000, conversionRate: 20, stageToStageRate: 33.3 },
    { stage: "SRM Invoice Generated", count: 1, amount: 120000, conversionRate: 10, stageToStageRate: 50 },
    { stage: "Receipt Collected", count: 1, amount: 80000, conversionRate: 10, stageToStageRate: 100 },
  ];
}

function lostAnalysis() {
  return {
    summary: { lostDeals: 1, lostAmount: 150000, aiPatternDetection: "Placeholder" },
    lostReasonBreakdown: [{ reason: "Budget frozen", count: 1, amount: 150000 }],
    topCompetitors: [{ competitor: "Legacy vendor", count: 1 }],
    ownerTrends: [{ key: "Ananya Rao", lost: 1, lostAmount: 150000, winRate: 0 }],
    deals: [{ ...deal(), status: "Lost", lostReason: "Budget frozen" }],
  };
}

function activity() {
  return { id: 1, activity_type: "task", activityType: "task", subject: "Discovery call", title: "Discovery call", status: "Pending", priority: "High", due_date: "2026-06-05T09:00:00Z", dueDate: "2026-06-05T09:00:00Z", ownerId: 100, updatedAt: "2026-06-05T00:00:00Z" };
}

function product() {
  return { id: 1, name: "CRM Enterprise", productCode: "CRM-ENT", sku: "CRM-ENT", category: "Software", listPrice: 125000, costPrice: 40000, status: "Active" };
}

function service() {
  return { id: 1, name: "Implementation", serviceCode: "IMPL-STD", category: "Professional Services", billingType: "fixed", defaultRate: 75000, defaultCost: 30000, active: true };
}

function priceBook() {
  return { id: 1, name: "India Standard", currency: "INR", region: "India", customerSegment: "SMB", active: true };
}

function quote() {
  return { id: 1, quoteNumber: "QT-001", status: "Draft", approvalStatus: "not_submitted", quoteDate: "2026-06-01", validUntil: "2026-06-30", grandTotal: 59000, expectedMargin: 29000 };
}

function quoteDetail() {
  return {
    ...quote(),
    lines: [{ id: 10, quoteId: 1, name: "Implementation", quantity: 1, unitPrice: 50000, discountValue: 0, taxRate: 18, lineTotal: 59000, estimatedCost: 30000 }],
    versions: [{ id: 1, versionNumber: 1 }],
    approvals: [{ id: 1, quoteId: 1, status: "pending" }],
    srmConversionLogs: [],
  };
}

function timeline() {
  return [
    { type: "qualification", title: "Lead qualified", occurredAt: "2026-06-05T08:00:00Z", record: { id: 1 } },
    { type: "conversion", title: "Lead converted", occurredAt: "2026-06-05T09:00:00Z", record: { id: 2 } },
  ];
}

function leadDetail() {
  return { ...lead(), entity: "leads", related: { conversion: { isConverted: false } }, timeline: timeline(), customFields: [] };
}

function accountDetail() {
  return { ...account(), entity: "companies", related: { contacts: [contact()], deals: [deal()] }, timeline: timeline(), customFields: [], accountHealth: "Placeholder" };
}

function contactDetail() {
  return { ...contact(), entity: "contacts", related: { account: account(), deals: [deal()] }, timeline: timeline(), customFields: [] };
}

function dealDetail() {
  return {
    ...deal(),
    entity: "deals",
    related: {
      account: account(),
      contact: contact(),
      srm: {
        salesOrder: { id: 1, order_number: "SO-000001" },
        engagement: { id: 2, engagement_number: "ENG-000001" },
        contract: { id: 3, contract_number: "CTR-000001" },
        billingPlan: { id: 4, name: "Milestone billing" },
        pmsProject: { id: 301, project_key: "PMS-301", code: "PMS-301", name: "Acme Delivery" },
      },
      approval: { status: "approved" },
    },
    timeline: timeline(),
    customFields: [],
  };
}
