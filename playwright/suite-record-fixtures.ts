import {expect,type Page} from "../frontend/node_modules/playwright/test";
import {authenticateCrm} from "./crm-core-test-utils";
import {authenticate} from "./srm-test-utils";
const stages = [
  { name: "New", required: [], allowedNext: ["Contacted", "Qualified", "Lost"] },
  { name: "Contacted", required: [], allowedNext: ["Qualified", "Lost"] },
  { name: "Qualified", required: [], allowedNext: ["Lost"] },
  { name: "Converted", required: [], allowedNext: [] },
  { name: "Lost", required: ["lossReason"], allowedNext: ["New"] },
];
const settings = { stages, slaHours: 24, staleDays: 7, preventDuplicates: true,
  assignment: { mode: "manual", ownerIds: [], rules: [] },
  sequences: [{ name: "Standard follow-up", steps: [{ day: 0, type: "call", title: "Introduce yourself" }] }], workflows: [] };
const initialLead = { id: 1, full_name: "Nisha Rao", email: "nisha@example.com", phone: "9876543210", phone_country_code: "+91", company_name: "Northstar Labs", source: "Referral", status: "New", owner_user_id: 100, estimated_value: 150000, lead_score: 72, lead_score_mode: "automatic", next_follow_up_at: "2026-10-24T10:00:00Z", created_at: "2026-10-12T10:00:00Z", version: 1,
  details: {}, signals: { overdue: true, slaBreached: true, stale: true, active: true, slaDeadline: "2026-10-13T10:00:00Z", ageDays: 13, nextAction: "Contact now: first-response deadline missed", priority: 170, followUpLabel: "Overdue" },
  timeline: [{ id: 1, title: "Lead captured", event_type: "created", actor_user_id: 100, occurred_at: "2026-10-12T10:00:00Z" }], activities: [], scoreReasons: [{ name: "Email available", matched: true, points: 20 }] };

export async function setupLeads(page: Page, canManage = true) {
  await authenticateCrm(page);await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  await page.route("**/api/v1/record-360/lead/1**",r=>r.fulfill({json:/\/(work|events)$/.test(new URL(r.request().url()).pathname)?{items:[],total:0,page:1,per_page:20,sections:{}}:{id:1,kind:"lead",name:"Nisha Rao",status:"New",fields:{email:"nisha@example.com",phone:"9876543210"},projects:[],allowed_actions:[],sections:{}}}));
  let lead = structuredClone(initialLead);
  let captured: typeof initialLead | undefined;
  let capture = { enabled: false, path: "", ownerId: 100 };
  const mutations: { path: string; data: unknown }[] = [];
  await page.route("**/api/v1/crm/lead-management/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.split("/lead-management")[1];
    const method = request.method();
    let body: unknown;
    if (method !== "GET" && !request.headers()["content-type"]?.includes("multipart")) mutations.push({ path, data: request.postDataJSON() });
    if (path === "/settings") body = method === "GET" ? { settings, owners: [{ id: 100, name: "admin@example.com" }, { id: 101, name: "Priya Shah (EMP-101)", employeeId: 501, employeeCode: "EMP-101", kind: "employee" }], unavailableEmployees: [{ employeeId: 502, employeeCode: "EMP-102", name: "Unlinked Employee", reason: "Needs an active login account" }], canManage, canAdmin: canManage, userId: 100 } : { settings: request.postDataJSON() };
    else if (path === "/leads" && method === "GET") body = { items: [lead], total: 1, page: 1, perPage: 40, truncated: false, limit: 5000, summary: { total: 1, active: 1, overdue: 1, slaBreached: 1, stale: 1 }, byStage: { [lead.status]: 1 }, bySource: { Referral: 1 }, convertedBySource: {}, lostReasons: {} };
    else if (path === "/leads" && method === "POST") { const data = request.postDataJSON(); captured = { ...lead, id: 2, ...data.values }; body = captured; }
    else if (path === "/leads/1" && method === "PATCH") { const data = request.postDataJSON(); lead = { ...lead, ...data.values, details: { ...lead.details, ...data.details }, version: lead.version + 1 }; body = lead; }
    else if (path === "/leads/1") body = lead;
    else if (path === "/leads/2") body = captured;
    else if (path === "/leads/1/team") body = { members: [{ id: 100, name: "Admin" }, { id: 101, name: "Priya Shah (EMP-101)" }] };
    else if (path === "/leads/1/team-notes") { const data = request.postDataJSON(); lead.timeline.unshift({ id: 2, title: "Team update", event_type: "team_note", actor_user_id: 100, occurred_at: new Date().toISOString(), description: data.body, metadata_json: { authorName: "Admin", mentionIds: data.mentionIds } } as any); lead.version++; body = { saved: true }; }
    else if (path === "/leads/1/follow-up") { lead.next_follow_up_at = request.postDataJSON().dueAt; lead.version++; body = lead; }
    else if (path === "/leads/1/activity") body = { saved: true };
    else if (path === "/leads/1/sequence") body = { sequence: { name: "Standard follow-up", active: true } };
    else if (path === "/capture-settings") { if (method === "PUT") capture = { ...request.postDataJSON(), path: "/api/v1/crm/lead-management/capture/1/public-token" }; body = capture; }
    else if (path === "/leads/1/booking-link") body = { path: "/api/v1/crm/lead-management/booking/1/1/booking-token", expires: "2026-11-25T09:00:00Z" };
    else if (path === "/analytics") body = { scope: "All permitted leads; independent of list filters", leadCount: 1, truncated: false, measurementNote: "Uses recorded interactions", stageHistory: [{ stage: "New", leadsEverInStage: 1, averageHoursBeforeExit: null, timedExits: 0 }], byOwner: [{ key: "100", leads: 1, converted: 0, qualified: 0, conversionRate: 0, averageFirstResponseMinutes: null, responseSampleSize: 0 }], bySource: [] };
    else if (path === "/excel/preview") body = { rows: [{ full_name: "Imported Lead", email: "import@example.com" }], validRows: [{ row: 2, values: { full_name: "Imported Lead", email: "import@example.com" } }], errors: [], skipped: [], ready: 1, total: 1 };
    else if (path === "/excel/import") body = { created: 1, skipped: [] };
    else if (path === "/bulk/preview") body = { count: 1, items: [{ id: 1, name: lead.full_name, stage: lead.status }] };
    else if (path === "/bulk/apply") body = { updated: 1 };
    else if (path === "/excel/export" || path === "/excel/template") { await route.fulfill({ contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", body: Buffer.from("workbook-mock"), headers: { "Content-Disposition": "attachment; filename=leads.xlsx" } }); return; }
    else body = {};
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/crm/leads");
  await expect(page.getByRole("heading", { name: /Lead workbench/ })).toBeVisible();
  await page.getByRole("tab",{name:"Cards",exact:true}).click();
  await expect(page.getByRole("button", { name: "Nisha Rao", exact: true })).toBeVisible();
  return mutations;
}

export async function setupProjects(page: any) {
  await authenticate(page, "admin");
  const rows = [
    {
      id: 701,
      name: "Website delivery",
      project_key: "WEB",
      status: "Active",
      priority: "High",
      health: "Good",
      due_date: "2020-01-01",
      owner_user_id: 100,
      owner_name: "Portfolio owner",
      client_name: "Acme",
      team: [{ id: 100, name: "Portfolio owner", role: "Manager" }, {id:101,name:"Delivery lead",role:"Member"}],
      workspace_id: 1,
      task_count: 4,
      completed_task_count: 1,
      calculated_progress: 25,
      overdue_task_count: 1,
      can_edit_project: true,
      can_manage_tasks: true,
    },
    {
      id: 702,
      name: "Completed engagement",
      project_key: "DONE",
      workspace_id: 2,
      status: "Completed",
      priority: "Medium",
      health: "Good",
      task_count: 2,
      completed_task_count: 2,
      calculated_progress: 100,
      can_edit_project: false,
    },
  ].map((p) => ({
    ...p,
    progress_percent: 0,
    is_archived: false,
    created_at: "2026-01-01",
    updated_at: "2026-11-01",
  }));
  await page.route("**/api/v1/project-management/**", async (route: any) => {
    const path = new URL(route.request().url()).pathname;
    let body: any = [];
    if (path.endsWith("/projects")) body = rows;
    else if (path.endsWith("/custom-fields")) body = { fields: [] };
    else if (path.endsWith("/custom-fields/records")) body = { records: {} };
    else if (path.endsWith("/workspaces"))
      body = [{ id: 1, name: "Main workspace", role: "Admin" }];
    else if (route.request().method() === "PATCH") {
      const p = rows.find((p) => path.endsWith("/" + p.id));
      Object.assign(p!, route.request().postDataJSON());
      body = p;
    }
    await route.fulfill({ json: body });
  });
  await page.route("**/api/v1/pipeline-workspaces/**", async (route: any) =>
    route.fulfill({
      json:
        route.request().method() === "GET"
          ? { preferences: { module_filters: {} }, views: [], can_share: true }
          : {},
    }),
  );
  await page.route("**/api/v1/access/settings/defaults/effective", (route) =>
    route.fulfill({
      json: { values: {}, modules: {}, companyId: 1, branchId: null },
    }),
  );
  await page.route("**/api/v1/access/setup", (route) =>
    route.fulfill({ json: { companyId: 1, ready: true, items: [] } }),
  );
  await page.goto("/pms/projects");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(2);
}
const deal = {id: 1, name: "Enterprise renewal", company_id: 1, contact_id: 1, owner_user_id: 100, pipeline_id: 1, stage_id: 1, amount: 25000, currency: "INR", probability: 50, priority: "High", status: "Open", version: 1, expected_close_date: "2026-11-25", planning: {qualification: {business_need: "Renewal planning"}}, catalog_items: []};

export async function setupDeals(page: Page) {
  await authenticateCrm(page);await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  await page.route("**/api/v1/crm/deal-workspace/**", async route => {
    const url = new URL(route.request().url()), path = url.pathname;
    let payload: any = {items: [], total: 0, pages: 1};
    if (path.endsWith("/record")) payload = {...deal, related: {account: {id: 1, name: "Acme"}, contact: {id: 1, full_name: "John"}, notes: [{id: 1, body: "Customer requested a renewal proposal."}], tasks: [{id: 1, title: "Prepare renewal", status: "To Do"}], files: [], contacts: [], quotations: [{id: 1, quote_number: "QT-001", status: "Draft", grand_total: 25000, currency: "INR"}], products: []}};
    if (path.endsWith("/query")) payload = {items: [{...deal, health: {score: 60, reasons: ["No next action scheduled"]}}], total: 1, page: 1, pages: 1, can_manage: true, can_assign: true};
    if (path.endsWith("/summary")) payload = {counts: {open: 1, closing_month: 1, won_month: 0, lost_month: 0, overdue: 0, without_activity: 1}, currencies: [{currency: "INR", pipeline: 25000, weighted: 12500}, {currency: "USD", pipeline: 100, weighted: 50}], stages: [{stage_id: 1, currency: "INR", count: 1, amount: 25000}], forecast: [{month: "2026-11", currency: "INR", count: 1, amount: 25000, weighted: 12500}], breakdowns: {owner: [{id: 100, currency: "INR", amount: 25000, weighted: 12500, count: 1}]}, definitions: {pipeline: "Open deals separated by currency"}};
    if (path.endsWith("/assignees")) payload = {items: [{id: 100, name: "Sales Admin", userId: 100}], total: 1, pages: 1};
    if (path.endsWith("/insights")) payload = {score: 60, level: "Needs Attention", age_days: 12, stage_age_days: 3, qualification_score: 29, reasons: ["No next action scheduled"], stage_name: "Qualification", pipeline_name: "Sales", owner_name: "Sales Admin"};
    if (path.endsWith("/collaborators")) payload = {items: [], can_assign: true};
    if (path.endsWith("/events")) payload = {items: [{type: "stage_change", title: "Stage changed to Qualification", occurredAt: "2026-11-01T08:00:00Z", record: {description: "Moved from Discovery", actor_user_id: 100}}], total: 1, pages: 1};
    if (path.endsWith("/pipelines")) payload = {items: [{id: 1, name: "Enterprise Sales"}], total: 1, pages: 1};
    if (path.endsWith("/pipeline-stages")) payload = {items: [{id: 1, name: "Qualification", pipeline_id: 1, probability: 20}, {id: 2, name: "Proposal", pipeline_id: 1, probability: 60}, {id: 3, name: "Closed Won", pipeline_id: 1, probability: 100, is_won: true}], total: 3, pages: 1};
    await route.fulfill({json: payload});
  });
  await page.route("**/api/v1/crm/deals/1", async route => route.fulfill({json: {...deal, related: {account: {id: 1, name: "Acme"}, contact: {id: 1, full_name: "John"}, notes: [{id: 1, body: "Customer requested a renewal proposal."}], tasks: [{id: 1, title: "Prepare renewal", status: "To Do"}], files: [], contacts: [], quotations: [{id: 1, quote_number: "QT-001", status: "Draft", grand_total: 25000, currency: "INR"}], products: []}, timeline: []}}));
}
