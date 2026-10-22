import { test, expect } from "../frontend/node_modules/playwright/test";

for (const module of ["fam", "crm", "srm", "hrms"]) {
  test(`${module}: compact navigation and shared team notes/chat`, async ({ page }) => {
    const entries: any[] = [];
    const tasks: any[] = [];
    await page.addInitScript(() => {
      window.__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" };
      localStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: "test", refreshToken: "test", isAuthenticated: true, user: { id: 1, email: "owner@test.com", role: "admin", is_superuser: true } }, version: 0 }));
    });
    await page.route("**/api/v1/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: any = {};
      if (path.endsWith("/business-os/modules")) data = { enabled_modules: ["hrms", "crm", "project_management", "srm", "fam"] };
      else if (path.endsWith("/workspaces")) data = [{ id: 1, name: "Delivery", role: "Owner" }];
      else if (path.endsWith("/overview")) data = { role: "Owner", projects: [{ id: 1, name: "Launch", project_key: "LN" }], tasks };
      else if (path.endsWith("/members")) data = [{ id: 1, user_id: 1, email: "owner@test.com", role: "Owner" }];
      else if (path.endsWith("/projects/1/tasks") && route.request().method() === "POST") {
        const task = { ...route.request().postDataJSON(), id: 7, project_id: 1, position: 0, comments_count: 0 };
        tasks.push(task); data = task;
      }
      else if (path.endsWith("/entries")) {
        if (route.request().method() === "POST") entries.push({ ...route.request().postDataJSON(), id: entries.length + 1, author: "owner@test.com", created_at: "2026-10-22T10:00:00" });
        data = route.request().method() === "POST" ? { id: entries.length } : entries;
      }
      else if (path.endsWith("/realtime/config")) data = { transport: "database" };
      else if (path.endsWith("/realtime/events")) data = { cursor: 1, events: [] };
      else if (path.includes("/crm/")) data = { items: [], stages: [] };
      else if (path.includes("/employees") || path.includes("/departments") || path.includes("/recognitions") || path.includes("/certificates")) data = [];
      await route.fulfill({ json: data });
    });
    await page.goto(`/${module}`);
    await page.getByRole("button", { name: "Team workspace", exact: true }).click();
    await expect(page.getByLabel("Workspace", { exact: true })).toHaveValue("1");
    await page.getByLabel("New shared task").fill("Prepare launch");
    await page.getByRole("button", { name: "Create shared task" }).click();
    await expect(page.getByRole("button", { name: "Prepare launch To Do" })).toBeVisible();
    await page.getByLabel("Link to task").selectOption("7");
    await page.getByLabel("Message your team").fill("Ready for review");
    await page.getByRole("button", { name: "Send message", exact: true }).click();
    await expect(page.getByText("Ready for review", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Quick notes" }).click();
    await page.getByLabel("Write a quick note").fill("Meeting decisions");
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await expect(page.getByText("Meeting decisions", { exact: true })).toBeVisible();
    expect(entries.every(e => e.task_id === 7)).toBeTruthy();
    entries.push({ id: 99, kind: "note", body: "Teammate's update", task_id: 7, author: "teammate@test.com", created_at: "2026-10-22T10:01:00" });
    await expect(page.getByText("Teammate's update", { exact: true })).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Close team workspace" }).click();
    await page.getByLabel("Find a page").fill("settings");
    await expect(page.getByRole("navigation", { name: "Module navigation" })).toBeVisible();
    await page.getByLabel("Find a page").fill("");
    await expect(page.getByRole("button", { name: "Show all pages" })).toBeVisible();
    if (module === "hrms") {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByRole("button", { name: "Team workspace", exact: true }).click();
      await page.getByRole("tab", { name: "Quick notes" }).click();
      await expect(page.getByText("Meeting decisions", { exact: true })).toBeVisible();
      await page.screenshot({ path: "../.tmp/shared-workspace-results/mobile.png", fullPage: true });
    }
    if (module === "fam") await page.screenshot({ path: "../.tmp/shared-workspace-results/fam.png", fullPage: true });
  });
}
