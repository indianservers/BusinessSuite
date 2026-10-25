import { expect, test } from "../frontend/node_modules/playwright/test";
const apiRoot = "http://127.0.0.1:8775/api/v1/project-management";
test("premium workspace status, rollback, search, tags and responsive navigation work with real data", async ({
  page,
  request,
}) => {
  const s = await (
    await request.get("http://127.0.0.1:8775/qa-session")
  ).json();
  const headers = { Authorization: `Bearer ${s.token}` };
  const suffix = String(Date.now());
  const workspace = await (
    await request.post(`${apiRoot}/workspaces`, {
      headers,
      data: { name: `Premium QA ${suffix}` },
    })
  ).json();
  const project = await (
    await request.post(`${apiRoot}/projects`, {
      headers,
      data: {
        workspace_id: workspace.id,
        name: "Premium UI project",
        project_key: "V" + suffix.slice(-7),
      },
    })
  ).json();
  const task = await (
    await request.post(`${apiRoot}/projects/${project.id}/tasks`, {
      headers,
      data: {
        title: `Premium task ${suffix}`,
        task_key: "V-" + suffix,
        status: "To Do",
        description: "Review the launch details with the team.",
      },
    })
  ).json();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(
    `/__suite-ui-qa.html?path=${encodeURIComponent(`/pms?workspace=${workspace.id}`)}`,
  );
  const status = page.getByRole("combobox", {
    name: `Status for ${task.title}`,
    exact: true,
  });
  await status.click();
  await page.getByRole("option", { name: "Done", exact: true }).click();
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiRoot}/tasks/${task.id}`, { headers })
          ).json()
        ).status,
    )
    .toBe("Done");
  await expect(status).toContainText("Done");
  await page.route("**/api/v1/project-management/tasks/*", (route) =>
    route.request().method() === "PATCH"
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Synthetic save failure" }),
        })
      : route.continue(),
  );
  await status.click();
  await page.getByRole("option", { name: "In Progress", exact: true }).click();
  await expect(page.getByRole("alert").first()).toContainText(
    "Synthetic save failure",
  );
  await expect(status).toContainText("Done");
  await page.unroute("**/api/v1/project-management/tasks/*");
  await page.keyboard.press("Control+k");
  const search = page.getByRole("dialog", { name: "Search Business Suite" });
  await expect(search).toBeVisible();
  await search.getByPlaceholder("Search anything...").fill(task.title);
  await expect(
    search.getByRole("button").filter({ hasText: task.title }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(search).not.toBeVisible();
  await page
    .getByRole("button", { name: "Dismiss error", exact: true })
    .click();
  await page.getByRole("button", { name: "New", exact: true }).click();
  await page.getByRole("menuitem", { name: /^Task/ }).click();
  const dialog = page.getByRole("dialog", { name: "Create New Task" });
  await dialog
    .getByPlaceholder("What needs to be done?")
    .fill(`Tags task ${suffix}`);
  const tagInput = dialog.getByLabel("Tags", { exact: true });
  await tagInput.fill("design, review, DESIGN,");
  await expect(
    dialog.getByRole("button", { name: "Remove tag design", exact: true }),
  ).toHaveCount(1);
  await tagInput.fill("launch");
  await dialog
    .getByRole("button", { name: "Create task", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  const saved = await (
    await request.get(
      `${apiRoot}/tasks?search=${encodeURIComponent(`Tags task ${suffix}`)}`,
      { headers },
    )
  ).json();
  expect(saved.items.length).toBe(1);
  const tags = await (
    await request.get(`${apiRoot}/tasks/${saved.items[0].id}/tags`, { headers })
  ).json();
  expect(tags.map((t: { name: string }) => t.name).sort()).toEqual([
    "design",
    "launch",
    "review",
  ]);
  await page.screenshot({ path: "docs/ui-v2/workspace-final-desktop.png" });
  await page
    .getByRole("button", { name: "Collapse sidebar", exact: true })
    .click();
  await expect(page.locator(".ws-sidebar")).toHaveCSS("width", "72px");
  await page
    .getByRole("button", { name: "Expand sidebar", exact: true })
    .click();
  await page.setViewportSize({ width: 375, height: 812 });
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await expect(
    page.getByRole("navigation", { name: "Suite navigation" }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Suite navigation" })
    .getByRole("button", { name: "People", exact: true })
    .click();
  await expect(page.locator(".ws-people-grid")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
  await page.screenshot({ path: "docs/ui-v2/people-mobile.png" });
  expect(errors).toEqual([]);
});

test('unavailable projects show a recoverable state and new purchase bills do not fetch example records', async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/__suite-ui-qa.html?path='+encodeURIComponent('/pms/projects/999999'));
 await expect(page.getByRole('heading',{name:'Project unavailable',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Retry',exact:true})).toBeVisible();
 const requested:string[]=[];page.on('request',r=>{if(r.method()==='GET'&&r.url().includes('/api/v1/fam/purchase-bills/'))requested.push(r.url());});
 await page.goto('/__suite-ui-qa.html?path='+encodeURIComponent('/fam/purchase-bills/new'));
 await expect(page.getByRole('heading',{name:'New Purchase Bill',exact:true})).toBeVisible();
 await expect(page.getByLabel('vendor id',{exact:true})).toHaveValue('');
 await expect(page.getByText('Unable to load purchase bill.',{exact:true})).toHaveCount(0);
 expect(requested).toEqual([]);expect(errors).toEqual([]);
});
