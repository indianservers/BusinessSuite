import { expect, test } from "../frontend/node_modules/playwright/test";

test("task menus, hover previews, calendar quick view, and double-click use real APIs", async ({
  page,
  request,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const base = "http://127.0.0.1:8775/api/v1/project-management";
  const session = await (
    await request.get("http://127.0.0.1:8775/qa-session")
  ).json();
  const headers = { Authorization: `Bearer ${session.token}` };
  const suffix = String(Date.now());
  const name = `Interaction project ${suffix}`;
  const title = `Interaction task ${suffix}`;
  const workspace = await request.post(`${base}/workspaces`, {
    headers,
    data: { name: `Interactions ${suffix}` },
  });
  expect(workspace.ok()).toBeTruthy();
  const wid = (await workspace.json()).id;
  const project = await request.post(`${base}/projects`, {
    headers,
    data: { name, project_key: `I${suffix.slice(-7)}`, workspace_id: wid },
  });
  expect(project.ok()).toBeTruthy();
  const pid = (await project.json()).id;
  const task = await request.post(`${base}/projects/${pid}/tasks`, {
    headers,
    data: {
      title,
      task_key: `I-${suffix.slice(-7)}`,
      description: "Useful preview context without opening the task",
      due_date: new Date().toISOString().slice(0, 10),
      priority: "Medium",
    },
  });
  expect(task.ok()).toBeTruthy();
  const tid = (await task.json()).id;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const goto = (path: string) =>
    page.goto(`/__commercial-browser-qa.html?path=${encodeURIComponent(path)}`);
  await goto(`/pms?workspace=${wid}`);
  let row = page.locator(".ws-task-table tbody tr").filter({ hasText: title });
  await expect(row).toBeVisible();
  await row.locator("td").nth(1).hover();
  await expect(page.locator(".pms-record-preview")).toContainText(
    "Useful preview context",
  );
  await row.click({ button: "right" });
  await expect(
    page.getByRole("menuitem", { name: "Open task", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("menuitem", { name: "Mark complete", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`${base}/tasks/${tid}`, { headers })).json())
          .status,
    )
    .toBe("Done");
  await expect(row.getByLabel(`Status for ${title}`)).toContainText("Done");
  await row
    .getByRole("button", { name: `Task actions for ${title}`, exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Change priority", exact: true })
    .hover();
  await page.getByRole("menuitem", { name: "Urgent", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`${base}/tasks/${tid}`, { headers })).json())
          .priority,
    )
    .toBe("Urgent");
  await row.focus();
  await page.keyboard.press("Shift+F10");
  await expect(
    page.getByRole("menuitem", { name: "Copy link", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await row.click({ button: "right" });
  await page.getByRole("menuitem", { name: "Copy link", exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toMatch(new RegExp(`/pms/tasks/${tid}$`));
  await row.locator("td").nth(1).dblclick();
  await expect(page.locator(".ws-drawer")).toBeVisible();
  await page
    .locator(".ws-drawer")
    .getByRole("button", { name: `Task actions for ${title}`, exact: true })
    .click();
  await expect(
    page.getByRole("menuitem", { name: "Duplicate task", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Close task", exact: true }).click();
  await page.getByRole("tab", { name: "Board", exact: true }).click();
  const card = page.getByTestId(`task-card-${tid}`);
  await expect(
    card.getByRole("button", { name: `Drag ${title}`, exact: true }),
  ).toBeEnabled();
  await card
    .getByRole("button", { name: `Task actions for ${title}`, exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Duplicate task", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: `Copy of ${title}`, exact: true }),
  ).toBeVisible();
  await card.click({ button: "right" });
  await page
    .getByRole("menuitem", { name: "Move to trash…", exact: true })
    .click();
  const confirmation = page.getByRole("dialog", {
    name: "Move task to trash?",
    exact: true,
  });
  await confirmation
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  expect(
    (await request.get(`${base}/tasks/${tid}`, { headers })).ok(),
  ).toBeTruthy();
  // Calendar single click previews; double click opens, without creating a task in the date cell.
  await page.getByRole("tab", { name: "Calendar", exact: true }).click();
  const chip = page
    .locator(".wc-task")
    .filter({ hasText: title })
    .filter({ hasNotText: "Copy of" })
    .first();
  await chip.click();
  await expect(
    page.getByRole("dialog", { name: `Task preview: ${title}`, exact: true }),
  ).toBeVisible();
  await expect(page.locator(".ws-drawer")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Close task preview", exact: true })
    .click();
  await chip.dblclick();
  await expect(page.locator(".ws-drawer")).toBeVisible();
  await page.getByRole("button", { name: "Close task", exact: true }).click();
  // The standalone list and details expose the same menu, with permission metadata from the server.
  await goto(`/pms/tasks?project=${pid}`);
  row = page
    .locator("tbody tr")
    .filter({ hasText: title })
    .filter({ hasNotText: "Copy of" })
    .first();
  await expect(row).toBeVisible();
  await row.click({ button: "right" });
  await expect(
    page.getByRole("menuitem", { name: "Change status", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await row.getByText(name, { exact: true }).dblclick();
  await expect(
    page.getByRole("button", {
      name: `Task actions for ${title}`,
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: `Task actions for ${title}`, exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Move to trash…", exact: true })
    .click();
  await page
    .getByRole("dialog", { name: "Move task to trash?", exact: true })
    .getByRole("button", { name: "Move to trash", exact: true })
    .click();
  await expect
    .poll(async () =>
      (await request.get(`${base}/tasks/${tid}`, { headers })).status(),
    )
    .toBe(404);
  expect(
    (
      await request.post(`${base}/trash/tasks/${tid}/restore`, { headers })
    ).ok(),
  ).toBeTruthy();
  await goto("/pms/projects");
  const projectCard = page.getByTestId(`project-card-${pid}`);
  await projectCard.click({ button: "right" });
  await expect(
    page.getByRole("menuitem", { name: "Open board", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("menuitem", { name: "Copy project ID", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe(`I${suffix.slice(-7)}`);
  await page.setViewportSize({ width: 375, height: 812 });
  await projectCard
    .getByRole("button", { name: `Project actions for ${name}`, exact: true })
    .click();
  await expect(
    page.getByRole("menuitem", { name: "Open project", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
  await page.screenshot({
    path: "docs/qa/connected-commercial-2026-10-24/record-actions-mobile.png",
    fullPage: false,
  });
  expect(errors).toEqual([]);
});

test("guest menus omit writes and inline fields retain their native context behavior", async ({
  page,
  request,
}) => {
  const base = "http://127.0.0.1:8775/api/v1/project-management";
  const session = await (
    await request.get("http://127.0.0.1:8775/qa-session")
  ).json();
  const guest = await (
    await request.get("http://127.0.0.1:8775/qa-session?guest=true")
  ).json();
  const headers = { Authorization: `Bearer ${session.token}` };
  const gh = { Authorization: `Bearer ${guest.token}` };
  const suffix = String(Date.now()).slice(-8);
  const wid = (
    await (
      await request.post(`${base}/workspaces`, {
        headers,
        data: { name: `Read only ${suffix}` },
      })
    ).json()
  ).id;
  const pid = (
    await (
      await request.post(`${base}/projects`, {
        headers,
        data: {
          name: "Guest project",
          project_key: `G${suffix}`,
          workspace_id: wid,
        },
      })
    ).json()
  ).id;
  const tid = (
    await (
      await request.post(`${base}/projects/${pid}/tasks`, {
        headers,
        data: { title: "Guest task", task_key: `G-${suffix}` },
      })
    ).json()
  ).id;
  const invitation = await (
    await request.post(`${base}/workspaces/${wid}/invitations`, {
      headers,
      data: { email: guest.user.email, role: "Guest" },
    })
  ).json();
  expect(
    (
      await request.post(`${base}/workspace-invitations/accept`, {
        headers: gh,
        data: { token: invitation.token },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto(
    `/__commercial-browser-qa.html?guest=1&path=${encodeURIComponent(`/pms?workspace=${wid}`)}`,
  );
  const row = page
    .locator(".ws-task-table tbody tr")
    .filter({ hasText: "Guest task" });
  await row.click({ button: "right" });
  await expect(
    page.getByRole("menuitem", { name: "Open task", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("menuitem", { name: "Mark complete", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("menuitem", { name: "Move to trash…", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await row.locator(".ws-list-title").click();
  const description = page.getByLabel("Task description", { exact: true });
  await description.click({ button: "right", force: true });
  await expect(page.locator("[data-radix-menu-content]")).toHaveCount(0);
  expect(
    (
      await request.patch(`${base}/tasks/${tid}`, {
        headers: gh,
        data: { status: "Done" },
      })
    ).status(),
  ).toBe(403);
});
