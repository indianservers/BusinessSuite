import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

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

async function setup(page: Page, canManage = true) {
  await authenticateCrm(page);
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
  await expect(page.getByRole("button", { name: "Nisha Rao", exact: true })).toBeVisible();
  return mutations;
}

test("desktop queues, layouts, preview drawer and stage history", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await setup(page);
  await page.screenshot({ path: "../docs/qa/lead-management/workbench-desktop.png", fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "board view", exact: true }).click();
  await expect(page.locator(".lm-lane")).toHaveCount(5);
  await page.getByRole("button", { name: "compact view", exact: true }).click();
  await expect(page.locator(".lm-compact")).toBeVisible();
  await page.getByRole("button", { name: "table view", exact: true }).click();
  await page.getByRole("button", { name: "Nisha Rao", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "history", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Lead captured", exact: true })).toBeVisible();
  await page.screenshot({ path: "../docs/qa/lead-management/lead-history-desktop.png", fullPage: true, animations: "disabled" });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "My day", exact: true }).click();
  await expect(page).toHaveURL(/queue=my_day/);
  expect(errors).toEqual([]);
});

test("capture lead and save a stage change inline", async ({ page }) => {
  const mutations = await setup(page);
  await page.getByRole("button", { name: "Add lead", exact: true }).click();
  await page.getByLabel("Full name *", { exact: true }).fill("New Prospect");
  await page.getByLabel("Email", { exact: true }).fill("new@example.com");
  await page.getByLabel("Assign to employee", { exact: true }).selectOption("101");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect.poll(() => mutations.find(m => m.path === "/leads")).toBeTruthy();
  const created = mutations.find(m => m.path === "/leads")?.data as { values: { full_name: string; owner_user_id: string } };
  expect(created.values.full_name).toBe("New Prospect");
  expect(Number(created.values.owner_user_id)).toBe(101);
  await expect(page.getByRole("heading", { name: "New Prospect", exact: true })).toBeVisible();
});

test("employee assignment is available on the full lead record", async ({ page }) => {
  const mutations = await setup(page);
  await page.goto("/crm/leads/1");
  await page.getByLabel("Assigned employee", { exact: true }).selectOption("101");
  await page.getByRole("button", { name: "Assign employee", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/leads/1" && (m.data as { values?: { owner_user_id?: number } }).values?.owner_user_id === 101)).toBe(true);
});

test("inline stages and bulk preview are persisted through APIs", async ({ page }) => {
  const mutations = await setup(page);
  await page.getByLabel("Stage for Nisha Rao", { exact: true }).selectOption("Contacted");
  await expect.poll(() => mutations.some(m => m.path === "/leads/1")).toBe(true);
  await page.getByLabel("Select Nisha Rao", { exact: true }).check();
  await page.getByLabel("Bulk action", { exact: true }).selectOption("owner:101");
  await page.getByRole("button", { name: "Preview changes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review bulk changes", exact: true })).toBeVisible();
  expect(mutations.some(m => m.path === "/bulk/apply")).toBe(false);
  await page.getByRole("button", { name: "Apply to 1 leads", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/bulk/apply")).toBe(true);
});

test("Excel import requires preview then explicit import and exports a workbook", async ({ page }) => {
  const mutations = await setup(page);
  await page.getByRole("button", { name: "Import Excel", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "leads.csv", mimeType: "text/csv", buffer: Buffer.from("full_name,email\nImported Lead,import@example.com") });
  await expect(page.getByText("1 ready", { exact: true })).toBeVisible();
  expect(mutations.some(m => m.path === "/excel/import")).toBe(false);
  await page.getByRole("button", { name: "Import 1 leads", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/excel/import")).toBe(true);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Excel", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe("leads.xlsx");
});

test("qualification, outcome logging and sequence actions remain accessible", async ({ page }) => {
  const mutations = await setup(page);
  await page.getByRole("button", { name: "Nisha Rao", exact: true }).click();
  await page.getByRole("button", { name: "qualification", exact: true }).click();
  await page.getByLabel("Business need", { exact: true }).fill("Sales automation");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/leads/1")).toBe(true);
  await page.getByRole("button", { name: "activities", exact: true }).click();
  await page.getByLabel("Outcome or meeting purpose", { exact: true }).fill("Requested a demo");
  await page.getByLabel("Lead responded — stop pending sequence tasks", { exact: true }).check();
  await page.getByRole("button", { name: "Save activity & next step", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/leads/1/activity")).toBe(true);
});

test("settings support stage, sequence and automation configuration", async ({ page }) => {
  const mutations = await setup(page);
  await page.getByRole("button", { name: "Lead workflow settings", exact: true }).click();
  await page.getByLabel("New stage name", { exact: true }).fill("Demo scheduled");
  await page.getByRole("button", { name: "Add stage", exact: true }).click();
  await page.getByRole("button", { name: "automation", exact: true }).click();
  await page.getByRole("button", { name: "Add automation", exact: true }).click();
  await page.getByRole("button", { name: "Save workflow settings", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/settings")).toBe(true);
  const saved = mutations.find(m => m.path === "/settings")?.data as typeof settings;
  expect(saved.stages.some(stage => stage.name === "Demo scheduled")).toBe(true);
  expect(saved.workflows.length).toBe(1);
});

test("viewer has read-only controls", async ({ page }) => {
  await setup(page, false);
  await expect(page.getByRole("button", { name: "Add lead", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Import Excel", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Stage for Nisha Rao", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Nisha Rao", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save changes", exact: true })).toHaveCount(0);
});

test("mobile stays within viewport and detail actions are reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
  expect(width.scroll).toBeLessThanOrEqual(width.client + 1);
  await page.screenshot({ path: "../docs/qa/lead-management/workbench-mobile.png", fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Nisha Rao", exact: true }).click();
  await page.getByRole("button", { name: "activities", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save activity & next step", exact: true })).toBeVisible();
  const box = await page.getByRole("dialog").boundingBox();
  expect(box?.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: "../docs/qa/lead-management/lead-mobile.png", fullPage: true, animations: "disabled" });
});

test("loss transitions request qualification details and keep the intended stage", async ({ page }) => {
  const mutations = await setup(page);
  await page.getByLabel("Stage for Nisha Rao", { exact: true }).selectOption("Lost");
  await expect(page.getByText("Required for Lost:", { exact: false })).toBeVisible();
  await page.getByLabel("Loss reason (required when Lost)", { exact: true }).selectOption("Budget");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect.poll(() => mutations.some(m => m.path === "/leads/1" && (m.data as { values: { status?: string } }).values.status === "Lost")).toBe(true);
});

test("analytics, website capture and booking link controls are wired", async ({ page }) => {
  await setup(page);
  await page.getByRole("button", { name: "Insights", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Lead performance", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Salesperson performance", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Lead workflow settings", exact: true }).click();
  await page.getByRole("button", { name: "website", exact: true }).click();
  await page.getByRole("button", { name: "Enable enquiry form", exact: true }).click();
  await expect(page.getByLabel("Embed this HTML form on your website", { exact: true })).toHaveValue(/<form/);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Nisha Rao", exact: true }).click();
  await page.getByRole("button", { name: "activities", exact: true }).click();
  await page.getByRole("button", { name: "Create booking link", exact: true }).click();
  await expect(page.getByLabel("Share this booking link", { exact: true })).toHaveValue(/booking-token/);
});
