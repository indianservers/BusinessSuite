import { test, expect } from "../frontend/node_modules/playwright/test";

test.skip(({ baseURL }) => baseURL !== "http://127.0.0.1:5182", "Requires disposable PostgreSQL QA servers.");
test("committed task edits propagate between API instances and browser sessions", async ({ page, browser, request }) => {
  test.setTimeout(90_000);
  const first = "http://127.0.0.1:8766/api/v1";
  const second = "http://127.0.0.1:8767/api/v1";
  // This spec is opt-in: the normal suite does not require a second API service.
  test.skip(process.env.SERVERLESS_COLLABORATION_QA !== "1", "Start the second QA instance to exercise cross-instance delivery.");
  const login = await request.post(`${first}/auth/login`, { data: { email: "owner@example.com", password: "WorkspaceQA@123" } });
  expect(login.ok()).toBeTruthy();
  const auth = await login.json();
  const context = await browser.newContext();
  const peer = await context.newPage();
  for (const [tab, api] of [[page, first], [peer, second]] as const) {
    await tab.addInitScript(({ auth, api }) => {
      window.__AI_HRMS_CONFIG__ = { apiBaseUrl: api };
      localStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: auth.access_token, refreshToken: auth.refresh_token,
        isAuthenticated: true, user: { id: auth.user_id, email: auth.email, role: auth.role, is_superuser: auth.is_superuser } }, version: 0 }));
    }, { auth, api });
    await tab.goto("/pms/workspaces");
    await tab.getByLabel("Workspace", { exact: true }).selectOption({ label: "Product studio · Owner" });
  }
  const headers = { Authorization: `Bearer ${auth.access_token}` };
  const feed = await request.get(`${second}/project-management/realtime/events`, { headers });
  expect(feed.ok()).toBeTruthy();
  const cursor = (await feed.json()).cursor;
  const overview = await (await request.get(`${first}/project-management/workspaces/1/overview`, { headers })).json();
  const task = overview.tasks.find((t: any) => t.title === "Shape the launch story");
  const title = `Shared edit ${Date.now()}`;
  try {
    const changed = await request.patch(`${first}/project-management/tasks/${task.id}`, { headers, data: { title } });
    expect(changed.status(), await changed.text()).toBe(200);
    await expect.poll(async () => {
      const response = await request.get(`${second}/project-management/realtime/events?cursor=${cursor}`, { headers });
      return (await response.json()).events.some((event: any) => event.taskId === task.id);
    }).toBeTruthy();
    await expect(peer.getByRole("button", { name: title, exact: true })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: title, exact: true })).toBeVisible({ timeout: 20_000 });
  } finally {
    await request.patch(`${first}/project-management/tasks/${task.id}`, { headers, data: { title: task.title } });
    await context.close();
  }
});
