/** Capture registered PMS routes and their major views against the real local app.
 * node qa/capture_pms_screenshots.mjs
 * Optional: PMS_CAPTURE_MATCH to resume a subset; PMS_SCREENSHOT_URL/PMS_API_URL.
 */
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "Mockup images", "PMS Screenshots");
const origin = process.env.PMS_SCREENSHOT_URL || "http://localhost:5173";
const api = process.env.PMS_API_URL || "http://127.0.0.1:1534/api/v1";
const seed = JSON.parse(await fs.readFile(path.join(root, "backend/backups/pms_demo_manifest.json"), "utf8"));
const source = await fs.readFile(path.join(root, "frontend/src/apps/project-management/routes.tsx"), "utf8");
const routes = [...source.matchAll(/path: "(pms[^\"]*)"/g)].map(m => "/" + m[1]);
const match = process.env.PMS_CAPTURE_MATCH ? new RegExp(process.env.PMS_CAPTURE_MATCH) : null;
const manifestPath = path.join(output, "capture-manifest.json");
await fs.mkdir(output, { recursive: true });
let previous = [];
try { previous = JSON.parse(await fs.readFile(manifestPath, "utf8")).screenshots || []; } catch {}
const records = new Map(previous.map(r => [r.file, r]));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const slug = s => s.replace(/^\//, "").replace(/[:/\s]+/g, "-").replace(/[^a-zA-Z0-9_-]/g, "").toLowerCase();
const safe = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
const fixtureRoutes = /command-center|enterprise-engine|product-launch|dependency-management|resource-planning|agile-execution|project-financials|work-hub|impact|ai-planner|timeline-plus|dependency-timeline|automation-ai|software|live|teams-live|issues|releases|automation|goals|forms|templates|components|workflows|security|dependencies$|navigator|apps|dashboards|plans|backlog-grooming|sprint-lifecycle|blueprints|resource-utilization/;
const browser = await chromium.launch({ headless: true });
const authResponse = await fetch(`${api}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "admin@karyaflow.com", password: "Password@123", module: "project_management" }) });
if (!authResponse.ok) throw new Error(`PMS login failed: ${authResponse.status}`);
const auth = await authResponse.json();
const context = await browser.newContext({ viewport: { width: 1920, height: 1200 }, deviceScaleFactor: 1, colorScheme: "light", reducedMotion: "reduce" });
await context.addInitScript(({ auth, api }) => {
  window.__AI_HRMS_CONFIG__ = { apiBaseUrl: api };
  localStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: auth.access_token, refreshToken: auth.refresh_token, isAuthenticated: true, user: { id: auth.user_id, email: auth.email, role: auth.role, is_superuser: auth.is_superuser } }, version: 0 }));
  localStorage.setItem("business-suite-ui-density", "comfortable");
}, { auth, api });
const page = await context.newPage();
const isApi = url => new URL(url).pathname.startsWith("/api/v1/");
let pending = new Set(), errors = [], runtimeErrors = [], requestSerial = 0;
const requestIds = new WeakMap();
page.on("request", request => {
  if (isApi(request.url()) && ["fetch", "xhr"].includes(request.resourceType())) { const id = ++requestSerial; requestIds.set(request, id); pending.add(id); }
});
const finished = request => { const id = requestIds.get(request); if (id) pending.delete(id); };
page.on("requestfinished", finished); page.on("requestfailed", finished);
page.on("response", response => { if (isApi(response.url()) && response.status() >= 400) errors.push({ status: response.status(), url: response.url().split("?")[0] }); });
page.on("pageerror", error => runtimeErrors.push(error.message));

async function settle() {
  await page.locator("h1,h2,main").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => undefined);
  const deadline = Date.now() + 30000;
  let calmSince = 0;
  while (Date.now() < deadline) {
    if (pending.size === 0) { calmSince ||= Date.now(); if (Date.now() - calmSince > 650) break; } else calmSince = 0;
    await delay(100);
  }
  await page.evaluate(() => document.fonts.ready);
  const dismiss = page.getByRole("button", { name: "Dismiss readiness", exact: true });
  if (await dismiss.isVisible().catch(() => false)) await dismiss.click({ timeout: 500 }).catch(() => undefined);
  await delay(250);
}
async function persist() {
  const screenshots = [...records.values()].sort((a, b) => a.file.localeCompare(b.file));
  await fs.writeFile(manifestPath, JSON.stringify({ generatedAt: new Date().toISOString(), viewport: { width: 1920, height: 1200 }, baseUrl: origin, totalRegisteredRoutes: routes.length, totalScreenshots: screenshots.length, screenshots }, null, 2));
  const groups = screenshots.map(r => `<article data-text="${safe((r.title + " " + r.route).toLowerCase())}"><a href="${safe(r.file)}" target="_blank"><img loading="lazy" src="${safe(r.file)}" alt="${safe(r.title)}"></a><div><b>${safe(r.title)}</b><code>${safe(r.route)}</code><small>${safe(r.dataSource)}${r.apiErrors.length || r.runtimeErrors.length ? " · See capture manifest for diagnostics" : ""}</small></div></article>`).join("\n");
  await fs.writeFile(path.join(output, "index.html"), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PMS screenshot gallery</title><style>*{box-sizing:border-box}body{margin:0;background:#f6f7fb;color:#29334a;font:14px system-ui}header{padding:40px 5vw;background:#252c40;color:white}h1{margin:0 0 8px;font-size:30px}header p{color:#bcc4d7}input{width:min(520px,100%);padding:13px 16px;border-radius:8px;border:0;margin-top:12px}main{padding:32px 5vw;display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}article{background:white;border:1px solid #e3e7f1;border-radius:12px;overflow:hidden;box-shadow:0 4px 18px #26324a06}article img{width:100%;display:block;aspect-ratio:1.6;object-fit:cover;object-position:top}article>div{padding:17px}code,small{display:block;margin-top:6px;color:#8490a8;font-size:11px}b{font-size:14px}footer{padding:0 5vw 30px;color:#8f99ad}@media(max-width:500px){main{grid-template-columns:1fr}}</style><header><h1>KaryaFlow PMS · Screenshot Gallery</h1><p>${screenshots.length} screenshots · ${routes.length} registered routes · ${seed.total_records.toLocaleString()} connected demo records</p><input aria-label="Filter screenshots" placeholder="Find a page, route, or view…" oninput="document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.text.includes(this.value.toLowerCase()))"><p>Real local application captures. Legacy demonstration screens are labeled separately. No API responses are mocked.</p></header><main>${groups}</main><footer>Data counts: <a href="data-summary.json">data-summary.json</a> · Route and capture diagnostics: <a href="capture-manifest.json">capture-manifest.json</a></footer></html>`);
}
async function capture(file, route, title, dataSource) {
  await settle();
  const heading = await page.evaluate(() => document.querySelector("h1")?.textContent || document.querySelector("h2")?.textContent || "");
  const visibleText = (await page.locator("body").innerText()).slice(0, 60000);
  const visibleFailure = /Something went wrong|Unable to load|Failed to load|Project not found|Task not found|Access denied|Internal Server Error/i.test(visibleText);
  await page.screenshot({ path: path.join(output, file), fullPage: false, animations: "disabled" });
  records.set(file, { file, route, title, actualUrl: page.url(), heading: heading.trim(), viewport: page.viewportSize(), dataSource, apiErrors: [...new Map(errors.map(e => [e.status + e.url, e])).values()], runtimeErrors: [...new Set(runtimeErrors)], visibleFailure });
  await persist();
  console.log(`Saved ${file}${visibleFailure || errors.length || runtimeErrors.length ? " [review diagnostics]" : ""}`);
}
async function visit(route) {
  pending = new Set(); errors = []; runtimeErrors = [];
  await page.goto(origin + route, { waitUntil: "domcontentloaded", timeout: 45000 });
  await settle();
  if (new URL(page.url()).pathname.endsWith("/login") && !route.endsWith("/login")) throw new Error(`Unexpected sign-in redirect while capturing ${route}`);
  await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll("main,.ws-content").forEach(e => { e.scrollTop = 0; }); });
}
try {
  for (let i = 0; i < routes.length; i++) {
    const pattern = routes[i]; if (i + 1 < Number(process.env.PMS_CAPTURE_FROM || 1)) continue; if (match && !match.test(pattern)) continue;
    const route = pattern.replace(":projectId", seed.flagship_project_id).replace(":taskId", seed.flagship_task_id);
    await visit(route);
    const title = pattern === "/pms" ? "PMS dashboard" : pattern.replace(/^\/pms\/?/, "").replace(/\//g, " · ");
    await capture(`${String(i + 1).padStart(2, "0")}_${slug(pattern) || "dashboard"}.png`, route, title, fixtureRoutes.test(pattern) ? "Built-in demonstration screen" : "Seeded local PMS database");
  }
  const extras = [
    { route: "/pms/workspaces", group: "workspace", role: "tab", tabs: ["Board", "List", /People/] },
    { route: "/pms/reports", group: "reports", tabs: ["Distribution", "Burndown", "Velocity", "Flow", "Cycle Time", "Time in Status", "Health", "Team"] },
    { route: "/pms/enterprise-engine", group: "enterprise", tabs: ["Advanced Plans", "Issue Navigator", "Goals", "Backlog & Sprints", "Workflows", "Automation", "Dependencies", "Releases", "Reports", "Business Ops", "Collaboration", "Enterprise Admin", "Agile Software", "UX Power Tools"] },
    { route: "/pms/command-center", group: "command-center", tabs: ["Summary", "Board", "Timeline", "List", "Calendar", "Teams", "Releases", "Dependencies", "Goals", "Reports", "Automation", "Forms", "Apps"] },
    { route: `/pms/projects/${seed.flagship_project_id}/tasks/${seed.flagship_task_id}`, group: "task-detail", tabs: ["Comments", "Activity", "Time Logs", "Files", "Linked Tasks", "Development", "History"] },
    { route: "/pms/product-launch", group: "product-launch", tabs: ["Summary", "List", "Board", "Calendar", "Timeline", "Reports", "Releases", "Pages"] },
    { route: "/pms/automation-ai", group: "automation", tabs: ["Rules", "Audit log", "Templates", "Usage"] },
    { route: "/pms/work-hub", group: "work-hub", tabs: ["Summary", "Board", "List", "Calendar", "Timeline", "Forms", "Pages", "Issues", "Reports", "Shortcuts", "Apps"] },
  ];
  for (const extra of extras) {
    if (match && !match.test(extra.route)) continue;
    await visit(extra.route);
    if (extra.group === "command-center") {
      const closeGoals = page.getByRole("button", { name: "View all", exact: true });
      if (await closeGoals.isVisible().catch(() => false)) {
        await capture("dialog_command-center-goals.png", extra.route, "Command center · goals overview", "Built-in demonstration screen");
        await closeGoals.click();
      }
    }
    for (const tab of extra.tabs) {
      if (extra.group === "command-center") {
        const closeGoals = page.getByRole("button", { name: "View all", exact: true });
        if (await closeGoals.isVisible().catch(() => false)) await closeGoals.click();
      }
      const target = page.getByRole(extra.role || "button", { name: tab, exact: typeof tab === "string" }).first();
      if (!(await target.isVisible().catch(() => false))) { console.log(`No visible tab: ${extra.group} ${String(tab)}`); continue; }
      await target.click();
      errors = []; runtimeErrors = [];
      const label = typeof tab === "string" ? tab : "People";
      await capture(`view_${extra.group}_${slug(label)}.png`, extra.route, `${extra.group} · ${label}`, fixtureRoutes.test(extra.route) ? "Built-in demonstration screen" : "Seeded local PMS database");
    }
  }
  if (!match || match.test("/pms/workspaces")) {
    await visit("/pms/workspaces");
    await page.getByRole("button", { name: "Invite people", exact: true }).click();
    await capture("dialog_workspace-invitation.png", "/pms/workspaces", "Workspace · invitation dialog", "Seeded local PMS database");
    await page.getByRole("button", { name: "Close dialog", exact: true }).click();
    await page.getByRole("button", { name: "New task", exact: true }).click();
    await capture("dialog_new-task.png", "/pms/workspaces", "Workspace · new task dialog", "Seeded local PMS database");
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByTestId(`task-card-${seed.flagship_task_id}`).locator(".ws-card-title").click();
    await capture("dialog_workspace-task-conversation.png", "/pms/workspaces", "Workspace · task conversation", "Seeded local PMS database");
    await page.getByRole("button", { name: "Close task", exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await capture("mobile_workspace-board.png", "/pms/workspaces", "Mobile · workspace board", "Seeded local PMS database");
    await page.getByRole("tab", { name: /People/ }).click();
    await capture("mobile_workspace-people.png", "/pms/workspaces", "Mobile · people", "Seeded local PMS database");
    await page.setViewportSize({ width: 1920, height: 1200 });
  }
  if (!match || match.test("/pms/login")) {
    const guest = await browser.newContext({ viewport: { width: 1920, height: 1200 }, colorScheme: "light" });
    const loginPage = await guest.newPage();
    await loginPage.addInitScript(api => { window.__AI_HRMS_CONFIG__ = { apiBaseUrl: api }; }, api);
    await loginPage.goto(origin + "/pms/login", { waitUntil: "domcontentloaded" });
    await loginPage.getByRole("button", { name: "Sign in", exact: true }).waitFor();
    await loginPage.screenshot({ path: path.join(output, "auth_pms-login.png"), animations: "disabled" });
    records.set("auth_pms-login.png", { file:"auth_pms-login.png",route:"/pms/login",title:"PMS · sign in",heading:"Sign in",dataSource:"Application sign-in page",apiErrors:[],runtimeErrors:[],visibleFailure:false });
    await guest.close();
  }
  await persist();
  console.log(JSON.stringify({ screenshots: records.size, routes: routes.length, output, diagnostics: [...records.values()].filter(r => r.visibleFailure || r.apiErrors.length || r.runtimeErrors.length).map(r => ({ file:r.file, apiErrors:r.apiErrors, runtimeErrors:r.runtimeErrors, visibleFailure:r.visibleFailure })) }, null, 2));
} finally {
  await context.close(); await browser.close();
}
