import { test, expect, type Page } from "../frontend/node_modules/playwright/test";

async function login(page: Page, path: string) {
  await page.addInitScript(() => { (window as any).__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" }; });
  if (process.env.REFRESH_PREVIEW) {
    const response = await page.request.post("http://127.0.0.1:1551/api/v1/auth/login", {
      data: { email: "admin@suiteqa.example.com", password: "SuiteQA@12345" },
    });
    expect(response.ok()).toBeTruthy();
    const tokens = await response.json();
    const profile = await page.request.get("http://127.0.0.1:1551/api/v1/auth/me", { headers: { Authorization: `Bearer ${tokens.access_token}` } });
    const rawUser = await profile.json();
    const user = { ...rawUser, role: typeof rawUser.role === "string" ? rawUser.role : rawUser.role?.name || "admin" };
    await page.addInitScript(({ tokens, user }) => {
      const state = JSON.stringify({ state: { accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user, isAuthenticated: true }, version: 0 });
      sessionStorage.setItem("hrms-auth", state);
      localStorage.setItem("hrms-auth", state);
    }, { tokens, user });
    await page.goto(path);
    return;
  }
  await page.goto(`/login?next=${encodeURIComponent(path)}`);
  await page.getByLabel("Email address", { exact: true }).fill("admin@suiteqa.example.com");
  await page.getByLabel("Password", { exact: true }).fill("SuiteQA@12345");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(path.replaceAll("/", "\\/")));
}

test("Intern Applications refresh updates rows and keeps the search", async ({ page }) => {
  let version = 1, reads = 0;
  await page.route("**/interns-hub/admin/application-intake**", async route => {
    reads++;
    if (version === 2) await new Promise(resolve => setTimeout(resolve, 700));
    await route.fulfill({ json: { items: [{ id: 91, full_name: version === 1 ? "Candidate One" : "Candidate Two",
      reference: "APP-REFRESH-TEST", email: "candidate@example.com", status: "Pending", details: {}, documents: [], created_at: "2026-10-27T10:00:00Z" }],
      total: 1, page: 1, counts: { Pending: 1 }, reviewable_total: 1 } });
  });
  await login(page, "/hrms/interns/applications");
  await expect(page.getByText("Candidate One", { exact: true }).first()).toBeVisible();
  await page.getByLabel("Search signups").fill("Candidate");
  await page.waitForTimeout(350);
  const before = reads; version = 2;
  await page.getByRole("button", { name: "Refresh page data", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refreshing page data", exact: true })).toBeDisabled();
  await expect(page.getByText("Candidate Two", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh page data", exact: true })).toBeEnabled();
  await expect(page.getByLabel("Search signups")).toHaveValue("Candidate");
  expect(reads).toBeGreaterThan(before);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `.tmp/page-refresh-interns-${test.info().project.name}.png`, fullPage: true });
});

test("PMS custom loader refreshes projects without clearing the filter", async ({ page }) => {
  let version = 1, reads = 0;
  await page.route(/\/api\/v1\/project-management\/projects(?:\?.*)?$/, route => {
    reads++;
    return route.fulfill({ json: [{ id: 501, name: version === 1 ? "Alpha One" : "Alpha Two", project_key: "ALPHA",
      status: "Active", health: "On Track", progress_percent: 25, budget: 0, can_edit_project: false }] });
  });
  await login(page, "/pms/projects");
  await expect(page.getByRole("button", { name: "Alpha One", exact: true })).toBeVisible();
  await page.getByPlaceholder("Search projects", { exact: true }).fill("Alpha");
  const before = reads; version = 2;
  await page.getByRole("button", { name: "Refresh page data", exact: true }).click();
  await expect(page.getByRole("button", { name: "Alpha Two", exact: true })).toBeVisible();
  await expect(page.getByPlaceholder("Search projects", { exact: true })).toHaveValue("Alpha");
  expect(reads).toBeGreaterThan(before);
});

for (const [label, path, prefix] of [
  ["CRM", "/crm/accounts", "/api/v1/crm/"],
  ["Sales", "/srm/sales-orders", "/api/v1/srm/sales-orders"],
  ["Finance", "/fam/ledgers", "/api/v1/fam/ledgers"],
]) test(`${label} refresh sends new GET requests without mutations`, async ({ page }) => {
  let reads = 0, writes = 0;
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith(prefix)) {
      if (request.method() === "GET") reads++; else writes++;
    }
  });
  await login(page, path);
  const button = page.getByRole("button", { name: "Refresh page data", exact: true });
  await expect(button).toBeVisible();
  await page.waitForTimeout(500);
  const before = reads, previousWrites = writes;
  await button.click();
  await expect(button).toBeEnabled();
  expect(reads).toBeGreaterThan(before);
  expect(writes).toBe(previousWrites);
});

test("refresh coverage is searchable and creation pages have no refresh", async ({ page }) => {
  await login(page, "/hrms/interns/applications");
  await page.getByRole("button", { name: "Pages with refresh", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Pages with refresh", exact: true })).toBeVisible();
  await page.getByLabel("Search refreshable pages").fill("interns/applications");
  await expect(page.getByRole("link", { name: "Interns / Applications", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.goto("/pms/projects/new");
  await expect(page.getByRole("heading", { name: /project/i }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh page data", exact: true })).toHaveCount(0);
});

test("workspace refresh keeps the selected workspace and task search", async ({ page }) => {
  let version = 1;
  await page.route(/\/api\/v1\/project-management\/workspaces(?:\?.*)?$/, route => route.fulfill({ json: [{ id: 901, name: "QA Workspace", role: "Owner" }] }));
  await page.route("**/project-management/workspaces/901/members", route => route.fulfill({ json: [] }));
  await page.route("**/project-management/workspaces/901/invitations", route => route.fulfill({ json: [] }));
  await page.route("**/project-management/workspaces/901/overview", route => route.fulfill({ json: {
    role: "Owner", projects: [{ id: 501, name: "QA Project", project_key: "QA" }],
    tasks: [{ id: 51, project_id: 501, task_key: "QA-51", title: version === 1 ? "Beta One" : "Beta Two", status: "To Do", priority: "Medium", position: 1, comments_count: 0 }],
  } }));
  await login(page, "/pms/workspaces");
  await expect(page.getByRole("button", { name: "QA-51 Beta One", exact: true })).toBeVisible();
  await page.getByLabel("Search workspace", { exact: true }).fill("Beta");
  version = 2;
  await page.getByRole("button", { name: "Refresh page data", exact: true }).click();
  await expect(page.getByRole("button", { name: "QA-51 Beta Two", exact: true })).toBeVisible();
  await expect(page.getByLabel("Search workspace", { exact: true })).toHaveValue("Beta");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("failed refresh reports an error and allows another attempt", async ({ page }) => {
  let fail = false;
  await page.route("**/interns-hub/admin/application-intake**", route => fail
    ? route.fulfill({ status: 503, json: { detail: "Synthetic refresh failure" } })
    : route.fulfill({ json: { items: [], total: 0, counts: {}, reviewable_total: 0 } }));
  await login(page, "/hrms/interns/applications");
  const button = page.getByRole("button", { name: "Refresh page data", exact: true });
  await expect(button).toBeVisible();
  fail = true;
  await button.click();
  await expect(page.getByText("Refresh incomplete", { exact: true })).toBeVisible();
  await expect(button).toBeEnabled();
  fail = false;
  await button.click();
  await expect(button).toHaveAttribute("title", /Last refreshed/);
});
