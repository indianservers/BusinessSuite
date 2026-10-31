// Run only against the disposable QA backend on 1558 and Vite on 5190.
const fs = require("node:fs");
const assert = require("node:assert/strict");
const { chromium, expect: raw } = require("../frontend/node_modules/playwright/test");
const expect = raw.configure({ timeout: 30000 });
const backend = "http://127.0.0.1:1558/api/v1";
(async () => {
  const loginResponse = await fetch(backend + "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "admin@suiteqa.example.com", password: "SuiteQA@12345" }) });
  assert.ok(loginResponse.ok);
  const login = await loginResponse.json();
  const headers = { Authorization: "Bearer " + login.access_token, "Content-Type": "application/json" };
  async function api(path, method = "GET", body) { const r = await fetch(backend + path, { method, headers, body: body ? JSON.stringify(body) : undefined }); const result = await r.json(); assert.ok(r.ok, `${path}: ${r.status} ${JSON.stringify(result)}`); return result; }
  const access = await api("/access/me");
  const projects = await api("/project-management/task-studio/projects");
  const project = Array.isArray(projects) ? projects[0] : projects.projects[0];
  const opts = await api(`/project-management/task-studio/options?project_id=${project.id}`);
  const statuses = ["To Do", "In Progress", "In Review", "Done"];
  const existing = await api("/project-management/tasks?search=MW-QA&pageSize=100");
  for (let i = 0; i < (existing.total ? 0 : 12); i++) {
    await api(`/project-management/task-studio/projects/${project.id}/tasks`, "POST", { task: { title: ["3d test in Android Math App", "Design experiment lab UI", "Build molecule 3D viewer", "Fix login issue in HRMS", "API integration", "Create assets for wave lab", "Intern batch onboarding"][i % 7] + (i > 6 ? ` ${i}` : ""), task_key: `MW-QA-${i}`, status: statuses[i % 4], priority: i % 3 ? "Medium" : "High", due_date: `2026-11-${String(i + 1).padStart(2, "0")}` }, assignment: { people: i === 10 ? [] : [login.user_id], teams: i === 2 ? [opts.teams[0].id] : [], batches: i === 6 ? [opts.batches[0].id] : [], group_responsibility: true } });
  }
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1672, height: 1050 } });
    await context.addInitScript(({ login, access }) => sessionStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: login.access_token, refreshToken: login.refresh_token, isAuthenticated: true, user: { id: login.user_id, email: login.email, role: "admin", is_superuser: true, access } }, version: 0 })), { login, access });
    const page = await context.newPage(); const errors = [];
    page.on("pageerror", e => { errors.push(e.message); console.error("PAGE", e.message); });
    page.on("response", async r => { if (r.status() >= 400 && r.url().includes("/api/")) console.error("HTTP", r.status(), r.url(), (await r.text()).slice(0, 500)); });
    await page.goto("http://127.0.0.1:5190/pms/my-work?workView=all&sortBy=title&sortOrder=asc");
    
    await expect(page.locator(".mw-table-wrap tbody tr")).toHaveCount(10).catch(async e => { fs.mkdirSync("docs/qa/my-work", { recursive: true }); await page.screenshot({ path: "docs/qa/my-work/failure.png" }); console.error("BODY", (await page.locator("body").innerText()).slice(-5000)); throw e; });
    assert.equal(await page.locator(".mw-stat").first().innerText().then(s => s.match(/12/)?.[0]), "12");
    await page.getByRole("button", { name: "Assign 3d test in Android Math App", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Assign Task" })).toBeVisible();
    await expect(dialog.locator(".mw-person")).toHaveCount(3);
    await dialog.locator(".mw-person").filter({ hasText: "Sneha Patel" }).getByRole("checkbox").check();
    await dialog.getByRole("tab", { name: "Teams", exact: true }).click();
    await dialog.locator(".mw-group > .mw-person input").first().check();
    await dialog.getByRole("tab", { name: "Intern Batches" }).click();
    await dialog.locator(".mw-group > .mw-person input").first().check();
    fs.mkdirSync("docs/qa/my-work", { recursive: true });
    await page.screenshot({ path: "docs/qa/my-work/desktop-assignment.png", fullPage: true });
    await dialog.getByRole("button", { name: "Assign Task", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await page.reload();
    await page.getByRole("button", { name: "Assign 3d test in Android Math App", exact: true }).click();
    await expect(page.getByRole("dialog").getByText(/Selected: 2 people/)).toBeVisible();
    await page.getByRole("dialog").getByRole("button", { name: "Close assignment" }).click();
    for (const name of ["Team Tasks", "Intern Batches", "Unassigned", "Approvals", "Completed", "My Tasks", "All Tasks"]) { await page.getByRole("navigation", { name: "Task scope" }).getByRole("button", { name, exact: true }).click(); await expect(page.locator(".mw-results")).toHaveAttribute("aria-busy", "false"); }
    await page.getByRole("button", { name: "Board View", exact: true }).click();
    await expect(page.locator(".mw-board")).toBeVisible();
    await page.getByRole("button", { name: "My Calendar", exact: true }).click();
    await expect(page.locator(".mw-calendar")).toBeVisible();
    await page.getByRole("button", { name: "Recent Activity", exact: true }).click();
    await expect(page.locator(".mw-activity article").first()).toBeVisible();
    await page.getByRole("button", { name: "Task List", exact: true }).click();
    await expect(page.getByRole("button", { name: "Task List", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByLabel("Search tasks", { exact: true }).fill("API integration");
    await expect(page.locator(".mw-table-wrap tbody tr")).toHaveCount(2).catch(async e => { console.error("SEARCH", page.url(), (await page.locator(".mw-page").innerText()).slice(0, 4000)); throw e; });
    await page.getByLabel("Search tasks", { exact: true }).fill("");
    await expect(page.locator(".mw-table-wrap tbody tr")).toHaveCount(10);
    await page.getByLabel("Select all editable tasks on this page").check();
    await page.getByRole("button", { name: "Assign people / groups", exact: true }).click();
    await expect(page.getByRole("dialog").getByText(/10 selected tasks/)).toBeVisible();
    await page.getByRole("dialog").getByRole("button", { name: "Close assignment" }).click();
    await page.getByRole("button", { name: "Clear selection", exact: true }).click();
    await page.getByRole("link", { name: "Add Task", exact: true }).click();
    await expect(page).toHaveURL(/\/pms\/tasks\/new/);
    await expect(page.getByRole("heading", { name: "Create Task", exact: true })).toBeVisible();
    await page.getByLabel("Project", { exact: true }).selectOption(String(project.id));
    await page.getByLabel("Task Title", { exact: true }).fill("Browser-created task " + Date.now());
    await page.getByLabel("Due date", { exact: true }).fill("2026-11-15");
    await page.getByRole("button", { name: "Create Task", exact: true }).first().click();
    await expect(page.getByRole("heading", { name: "Task Details", exact: true })).toBeVisible();
    const created = await api("/project-management/tasks?search=Browser-created");
    assert.ok(created.total >= 1);
    for (const task of created.items) await api(`/project-management/tasks/${task.id}`, "DELETE");
    await page.goto("http://127.0.0.1:5190/pms/my-work?workView=all&sortBy=title&sortOrder=asc");
    await expect(page.locator(".mw-table-wrap tbody tr")).toHaveCount(10);
    await page.screenshot({ path: "docs/qa/my-work/desktop.png", fullPage: true });
    await page.setViewportSize({ width: 820, height: 1180 });
    await expect.poll(() => page.locator(".mw-page").evaluate(el => el.getBoundingClientRect().left)).toBeLessThan(50);
    await page.screenshot({ path: "docs/qa/my-work/tablet.png", fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.locator(".mw-page").evaluate(el => el.getBoundingClientRect().left)).toBeLessThan(50);
    await expect(page.locator(".mw-mobile-cards")).toBeVisible();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: "docs/qa/my-work/mobile.png", fullPage: true });
    await page.locator(".mw-mobile-cards .mw-avatars").first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    assert.equal(await page.getByRole("dialog").evaluate(el => Math.round(el.getBoundingClientRect().width)), 390);
    await page.screenshot({ path: "docs/qa/my-work/mobile-assignment.png", fullPage: true });
    assert.deepEqual(errors, []);
    console.log("PASS: real API assignment persistence, all tabs, layouts, search, bulk panel, full-page creation, responsive layouts; no page errors");
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
