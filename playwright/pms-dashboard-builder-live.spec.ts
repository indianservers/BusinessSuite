import { test, expect } from "../frontend/node_modules/playwright/test";
const root = "http://127.0.0.1:8775/api/v1/project-management";
test("dashboard wizard, real metrics, edit, undo, save, history, export and mobile", async ({
  page,
  request,
}) => {
  const session = await (
    await request.get("http://127.0.0.1:8775/qa-session")
  ).json();
  const headers = { Authorization: `Bearer ${session.token}` };
  const suffix = Date.now();
  const ws = await (
    await request.post(root + "/workspaces", {
      headers,
      data: { name: "Dashboard QA " + suffix },
    })
  ).json();
  const project = await (
    await request.post(root + "/projects", {
      headers,
      data: {
        workspace_id: ws.id,
        name: "Delivery QA",
        project_key: "DB" + String(suffix).slice(-6),
      },
    })
  ).json();
  for (let i = 0; i < 5; i++) {
    const response = await request.post(
      `${root}/projects/${project.id}/tasks`,
      {
        headers,
        data: {
          title: `Dashboard task ${i}`,
          task_key: `DB-${suffix}-${i}`,
          status: i === 0 ? "Done" : i % 2 ? "In Progress" : "To Do",
          due_date: "2026-10-30",
          estimated_hours: 2,
        },
      },
    );
    expect(response.ok(), await response.text()).toBeTruthy();
  }
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(
    "/__suite-ui-qa.html?path=" + encodeURIComponent("/pms/dashboards"),
  );
  await page
    .getByRole("button", { name: "New dashboard", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "New dashboard" });
  await dialog
    .getByRole("textbox", { name: "Dashboard name" })
    .fill("Delivery overview " + suffix);
  await dialog
    .getByRole("combobox", { name: "Workspace", exact: true })
    .click();
  await page.getByRole("option", { name: ws.name, exact: true }).click();
  await dialog.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: /Project Overview/ }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Continue", exact: true }).click();
  await dialog.getByRole("button", { name: "Continue", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Create dashboard", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Delivery overview " + suffix,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "View records for Total Tasks" }),
  ).toContainText("5");
  await page.getByRole("button", { name: "Customize", exact: true }).click();
  await page.getByRole("button", { name: "Add widget", exact: true }).click();
  await page.getByRole("textbox", { name: "Search widgets" }).fill("notes");
  await page.getByRole("button", { name: /Rich Text \/ Notes/ }).click();
  const settings = page.getByRole("dialog", { name: "Widget settings" });
  await settings
    .getByRole("textbox", { name: "Widget title", exact: true })
    .fill("Delivery notes");
  await settings.getByRole("button", { name: "Apply & preview" }).click();
  await expect(
    page.getByRole("region", { name: "Delivery notes", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Undo dashboard change" }).click();
  await expect(
    page.getByRole("heading", { name: "Rich Text / Notes", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Redo dashboard change" }).click();
  await page
    .getByRole("button", { name: "Save dashboard", exact: true })
    .click();
  await expect(
    page.getByText("Revision 2 · Saved", { exact: true }),
  ).toBeVisible();
  const all = await (
    await request.get(root + "/dashboards", { headers })
  ).json();
  const d = all.find((v: any) => v.name === "Delivery overview " + suffix);
  expect(
    d.configuration.widgets.some((w: any) => w.title === "Delivery notes"),
  ).toBeTruthy();
  await page.goto(
    "/__suite-ui-qa.html?path=" +
      encodeURIComponent("/pms/dashboards?dashboard=" + d.id),
  );
  await expect(
    page.getByRole("heading", { name: "Delivery notes", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dashboard history" }).click();
  await expect(
    page.getByRole("dialog", { name: "Dashboard history" }),
  ).toContainText("Revision 1");
  await page.getByRole("button", { name: "Close Dashboard history" }).click();
  await page.getByRole("button", { name: "Dashboard actions" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.csv$/);
  await page
    .locator(".db-menu[open]")
    .evaluateAll((nodes) => nodes.forEach((n) => n.removeAttribute("open")));
  await page.getByRole("button", { name: "Dashboard actions" }).click();
  const pngDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PNG", exact: true }).click();
  expect((await pngDownload).suggestedFilename()).toMatch(/\.png$/);
  await page
    .locator(".db-menu[open]")
    .evaluateAll((nodes) => nodes.forEach((n) => n.removeAttribute("open")));
  await page.setViewportSize({ width: 1672, height: 1050 });
  await page.getByRole("heading", { level: 1 }).scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "../docs/ui-v2/dashboard-builder-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Total Tasks", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await expect
    .poll(async () => {
      const card = await page.locator(".db-widget").first().boundingBox();
      const grid = await page.locator(".db-canvas").boundingBox();
      return !!card && !!grid && card.width <= grid.width * 0.55;
    })
    .toBeTruthy();
  const overlaps = await page.locator(".db-widget").evaluateAll((nodes) => {
    const boxes = nodes.map((n) => n.getBoundingClientRect());
    return boxes.some((a, i) =>
      boxes.some(
        (b, j) =>
          j > i &&
          Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 &&
          Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2,
      ),
    );
  });
  expect(overlaps).toBeFalsy();
  await page.screenshot({
    path: "../docs/ui-v2/dashboard-builder-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(errors).toEqual([]);
});

test("dashboard drag, resize, conflict recovery, drilldown and history restore", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  const session = await (
    await request.get("http://127.0.0.1:8775/qa-session")
  ).json();
  const headers = { Authorization: `Bearer ${session.token}` };
  const ws = await (
    await request.post(root + "/workspaces", {
      headers,
      data: { name: "Layout QA " + Date.now() },
    })
  ).json();
  const catalog = await (
    await request.get(root + "/dashboards/catalog", { headers })
  ).json();
  const configuration = catalog.templates.find(
    (t: any) => t.id === "tasks",
  ).configuration;
  configuration.widgets = configuration.widgets.slice(0, 2);
  const d = await (
    await request.post(root + "/dashboards", {
      headers,
      data: {
        workspace_id: ws.id,
        name: "Layout interaction QA",
        configuration,
      },
    })
  ).json();
  await page.goto(
    "/__suite-ui-qa.html?path=" +
      encodeURIComponent("/pms/dashboards?dashboard=" + d.id),
  );
  await page.getByRole("button", { name: "Customize", exact: true }).click();
  const widget = page.getByRole("region", { name: "Total Tasks", exact: true });
  const handle = widget.locator(".db-drag-handle");
  const box = await handle.boundingBox();
  expect(box).toBeTruthy();
  await page.mouse.move(box!.x + 5, box!.y + 5);
  await page.mouse.down();
  await page.mouse.move(box!.x + 240, box!.y + 170, { steps: 12 });
  await page.mouse.up();
  const resizer = widget.locator(".react-resizable-handle");
  const rb = await resizer.boundingBox();
  await page.mouse.move(rb!.x + 8, rb!.y + 8);
  await page.mouse.down();
  await page.mouse.move(rb!.x + 150, rb!.y + 80, { steps: 12 });
  await page.mouse.up();
  await page.route(`**/dashboards/${d.id}`, async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Dashboard changed. Your draft is preserved.",
        }),
      });
      await page.unroute(`**/dashboards/${d.id}`);
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "Save dashboard", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("draft is preserved");
  await expect(
    page.getByRole("button", { name: "Save dashboard", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Save dashboard", exact: true })
    .click();
  await expect(
    page.getByText("Revision 2 · Saved", { exact: true }),
  ).toBeVisible();
  const updated = await (
    await request.get(root + "/dashboards/" + d.id, { headers })
  ).json();
  const first = updated.configuration.widgets[0];
  expect(
    first.w !== configuration.widgets[0].w ||
      first.h !== configuration.widgets[0].h,
  ).toBeTruthy();
  expect(
    first.x !== configuration.widgets[0].x ||
      first.y !== configuration.widgets[0].y,
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "View records for Total Tasks" })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Total Tasks", exact: true }),
  ).toContainText("No matching data");
  await page
    .getByRole("button", { name: "Close Total Tasks", exact: true })
    .click();
  await page.getByRole("button", { name: "Dashboard history" }).click();
  await page.getByRole("button", { name: "Restore this version" }).click();
  await page
    .getByRole("dialog", { name: /Restore revision 1/ })
    .getByRole("button", { name: "Confirm", exact: true })
    .click();
  await expect(
    page.getByText("Revision 3 · Saved", { exact: true }),
  ).toBeVisible();
  const restored = await (
    await request.get(root + "/dashboards/" + d.id, { headers })
  ).json();
  expect(restored.configuration).toEqual(configuration);
  await page.getByRole("button", { name: "Customize", exact: true }).click();
  await page
    .getByRole("button", { name: "Guided layout", exact: true })
    .click();
  const guide = page.getByRole("dialog", { name: "Guided dashboard layout" });
  await guide
    .getByRole("textbox", { name: "What do you want to track?" })
    .fill("Show priority in a donut chart");
  await guide
    .getByRole("button", { name: "Suggest layout", exact: true })
    .click();
  await expect(guide).toContainText("No AI provider was used");
  await guide.getByRole("button", { name: "Apply to draft" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Task Priority Distribution",
      exact: true,
    }),
  ).toBeVisible();
});
