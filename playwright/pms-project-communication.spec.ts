import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

async function setup(page: Page, options: { archived?: boolean; missing?: boolean; failSend?: boolean } = {}) {
  await authenticate(page, "admin");
  const project = { id: 301, workspace_id: 7, name: "Website Redesign", project_key: "WEB", status: "In Progress", health: "On Track", progress_percent: 72, can_edit_project: true, can_manage_members: true };
  const messages = [{ id: 1, author_id: 101, body: "The homepage design is ready for review.", created_at: "2026-11-07T10:30:00Z", deleted_at: null, attachments: [] }];
  const sent: any[] = [];
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api\/v1/, "");
    const method = route.request().method();
    let body: unknown;
    if (path === "/access/settings/defaults/effective") body = { values: {}, modules: {}, companyId: 1, branchId: null };
    else if (path === "/access/setup") body = { companyId: 1, ready: true, items: [] };
    else if (path === "/project-management/projects/301") body = project;
    else if (path === "/project-management/projects") body = [project];
    else if (path === "/project-management/projects/301/field-values") body = { fields: [], can_edit: true };
    else if (path === "/project-management/projects/301/activity" || path === "/project-management/files") body = [];
    else if (path === "/project-management/dashboard/301") body = { project, status_counts: {}, metrics: {} };
    else if (path === "/project-management/projects/301/tasks") body = [{ id: 11, task_key: "WEB-11", title: "Review homepage design", status: "In Progress", due_date: "2026-11-09" }];
    else if (path === "/project-management/projects/301/members" || path === "/project-management/projects/301/milestones") body = [];
    else if (path === "/collaboration/contexts/lookup") body = { conversation_id: options.missing ? null : 12 };
    else if (path === "/collaboration/context-conversations") body = { conversation_id: 12 };
    else if (path.endsWith("/chat/conversations")) body = { can_send: true, conversations: [{ id: 12, joined: true, archived: !!options.archived, participants: [{ id: 100, email: "admin@example.com" }, { id: 101, email: "priya.sharma@example.com" }] }] };
    else if (path.endsWith("/conversations/12/attachments")) body = { id: 55, name: "brief.txt", size: 5, mime: "text/plain" };
    else if (path.endsWith("/conversations/12/attachments/55")) {
      if (method === "GET") { await route.fulfill({ body: "brief", contentType: "text/plain" }); return; }
      body = {};
    }
    else if (path.endsWith("/conversations/12/messages")) {
      if (method === "POST") {
        const payload = route.request().postDataJSON(); sent.push(payload);
        if (options.failSend && sent.length === 1) { await route.fulfill({ status: 400, json: { detail: "Please retry" } }); return; }
        messages.push({ id: messages.length + 1, author_id: 100, body: payload.body, created_at: "2026-11-07T10:45:00Z", deleted_at: null, attachments: [] });
      }
      body = { messages, before: null, read_through: messages.length };
    } else if (path.endsWith("/read")) body = { unread: 0 };
    else if (path === "/collaboration/events") body = { cursor: 1, changed: false };
    else { await route.fallback(); return; }
    await route.fulfill({ json: body });
  });
  await page.goto("/pms/projects/301/communication");
  return sent;
}

test("project conversation sends messages, retries safely, shares tasks and works on mobile", async ({ page }) => {
  const sent = await setup(page, { failSend: true });
  await expect(page.getByRole("heading", { name: "Team communication", exact: true })).toBeVisible();
  await expect(page.getByText("Project actions", { exact: true })).toHaveCount(0);
  await expect(page.getByText("The homepage design is ready for review.")).toBeVisible();
  await page.getByRole("textbox", { name: "Message", exact: true }).fill("Thanks, reviewing now.");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Please retry" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue("Thanks, reviewing now.");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator(".pc-bubble--mine")).toContainText("Thanks, reviewing now.");
  expect(sent[0].client_id).toBe(sent[1].client_id);
  await page.getByRole("button", { name: "Send reminder", exact: true }).click();
  await page.locator(".pc-task-picker").getByRole("button", { name: /Review homepage design/ }).click();
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(/Reminder: Review homepage design/);
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.screenshot({ path: "docs/qa/pms-communication-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Conversations", exact: true })).toBeVisible();
  await page.locator(".pc-conversation").click();
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "docs/qa/pms-communication-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "Back to conversations" }).click();
  await expect(page.getByRole("heading", { name: "Conversations", exact: true })).toBeVisible();
});

test("archived project conversations remain read only", async ({ page }) => {
  await setup(page, { archived: true });
  await expect(page.getByText("Archived · Read only")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Attach file", exact: true })).toBeDisabled();
});

test("opening an empty communication tab does not create a conversation automatically", async ({ page }) => {
  await setup(page, { missing: true });
  await expect(page.getByRole("button", { name: "Start conversation", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Start conversation", exact: true }).click();
  await expect(page.getByText("The homepage design is ready for review.")).toBeVisible();
});

test("uploads are removable and sent as real attachment IDs", async ({ page }) => {
  const sent = await setup(page);
  const file = { name: "brief.txt", mimeType: "text/plain", buffer: Buffer.from("brief") };
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toBeEnabled();
  await page.getByLabel("Attach a file", { exact: true }).setInputFiles(file);
  await expect(page.locator(".pc-uploads")).toContainText("brief.txt");
  await page.getByRole("button", { name: "Remove brief.txt", exact: true }).click();
  await expect(page.locator(".pc-uploads")).toHaveCount(0);
  await page.getByLabel("Attach a file", { exact: true }).setInputFiles(file);
  await expect(page.getByRole("button", { name: "Send message", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator(".pc-uploads")).toHaveCount(0);
  expect(sent[0].attachment_ids).toEqual([55]);
});

test("original project details retain their actions and dashboard", async ({ page }) => {
  await setup(page);
  await page.getByRole("link", { name: "Back to project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Website Redesign", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open board", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Project at a glance", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Project communication", exact: true })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Project views", exact: true }).getByRole("link")).toHaveCount(8);
});

test("capture separate communication and restored project details", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1100 });
  await setup(page);
  await expect(page.getByText("The homepage design is ready for review.")).toBeVisible();
  await page.getByRole("heading", { name: "Team communication", exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: "docs/qa/pms-team-communication-separate.png", fullPage: true });
  await page.getByRole("link", { name: "Back to project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Project at a glance", exact: true })).toBeVisible();
  await page.getByText("Project actions", { exact: true }).click();
  await expect(page.getByRole("link", { name: "Edit project", exact: true })).toBeVisible();
  await page.getByRole("heading", { name: "Website Redesign", exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: "docs/qa/pms-project-details-restored.png", fullPage: true });
});

test("Collaboration sidebar opens the separate Team Communication page", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1300 });
  await setup(page);
  await page.getByRole("button", { name: /^Collaboration/ }).click();
  await page.getByRole("link", { name: "Team Communication", exact: true }).click();
  await expect(page).toHaveURL(/\/pms\/team-communication$/);
  await expect(page.getByLabel("Project conversation", { exact: true })).toHaveValue("301");
  await expect(page.getByRole("heading", { name: "Team communication", exact: true })).toBeVisible();
  await expect(page.getByText("The homepage design is ready for review.")).toBeVisible();
  await expect(page.getByText("Project actions", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Team Communication", exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("link", { name: "Team Communication", exact: true })).toBeVisible();
  await page.getByRole("heading", { name: "Team communication", exact: true }).scrollIntoViewIfNeeded();
  await page.mouse.move(1500, 110);
  await page.screenshot({ path: "docs/qa/pms-team-communication-sidebar.png", fullPage: true });
});
