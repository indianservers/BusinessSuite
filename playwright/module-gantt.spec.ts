import { test, expect, type Route } from "../frontend/node_modules/playwright/test";
import { authenticateCommunication } from "./communication-test-utils";
const respond = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

for (const [module, source, path, endpoint, startField, endField] of [
  ["crm", "calendar", "/crm/gantt", "/crm/calendar", "start", "end"],
  ["srm", "sales-orders", "/srm/gantt", "/srm/sales-orders", "expected_start_date", "expected_end_date"],
  ["inventory", "purchase-orders", "/srm/inventory/gantt", "/srm/procurement/purchase-orders", "order_date", "expected_date"],
  ["hrms", "leave", "/hrms/leave/gantt", "/leave/requests", "from_date", "to_date"],
  ["fam", "financial-years", "/fam/gantt", "/fam/financial-years", "start_date", "end_date"],
] as const) {
  test(`${module} drag, both resize handles, dependencies, reload and failed-save rollback`, async ({ page }) => {
    await authenticateCommunication(page);
    const title1 = module === "hrms" ? "Leave - Schedule 1" : "Schedule 1";
    const keys = module === "crm" ? ["tasks:1", "tasks:2"] : ["1", "2"];
    const records = keys.map((id, i) => ({ id, title: `Schedule ${i+1}`, name: `Schedule ${i+1}`, po_number: `Schedule ${i+1}`, reason: `Schedule ${i+1}`, status: "Pending", [startField]: `2026-10-${10+i*10}`, [endField]: `2026-10-${12+i*10}` }));
    let revision = 0; let failNext = false; let readOnly = false;
    let links: Array<{ id: string; source_id: string; target_id: string; type: string; lag: number }> = [];
    const writes: Array<Record<string, unknown>> = [];
    await page.route(`**/api/v1${endpoint}*`, route => respond(route, module === "srm" || module === "hrms" ? records : { items: records }));
    await page.route(`**/api/v1/scheduling/${module}/${source}**`, async route => {
      const request = route.request(); const url = new URL(request.url());
      if (request.method() === "GET") return respond(route, { revision, records: Object.fromEntries(records.map(record => [record.id, { can_edit: !readOnly, start: record[startField], end: record[endField] }])), dependencies: links });
      if (request.method() === "PATCH") {
        const body = request.postDataJSON(); writes.push(body);
        if (failNext) { failNext = false; return respond(route, { detail: "Record dates changed. Refresh and retry." }, 409); }
        const id = decodeURIComponent(url.pathname.split("/").pop()!); const record = records.find(record => record.id === id)!;
        record[startField] = body.start; record[endField] = body.end; revision++;
        return respond(route, { revision, start: body.start, end: body.end });
      }
      if (request.method() === "POST") { links = [...links, { id: "dep-1", ...request.postDataJSON() }]; revision++; return respond(route, { revision, dependency: links[0] }, 201); }
      links = []; revision++; return respond(route, { revision });
    });
    const setRange = async () => { await page.getByLabel("From", { exact: true }).fill("2026-10-01"); await page.getByLabel("To", { exact: true }).fill("2026-10-31"); };
    const dragBy = async (name: string, dx: number) => {
      const handle = page.getByRole("button", { name, exact: true }); await expect(handle).toBeEnabled();
      await handle.scrollIntoViewIfNeeded(); const box = (await handle.boundingBox())!;
      await page.mouse.move(box.x + box.width/2, box.y + box.height/2); await page.mouse.down(); await page.mouse.move(box.x + box.width/2 + dx, box.y + box.height/2, { steps: 5 }); await page.mouse.up();
    };
    await page.goto(path); await setRange();
    await expect(page.getByRole("button", { name: `Resize end for ${title1}` })).toBeEnabled();
    await dragBy(`Move ${title1}: 2026-10-10 to 2026-10-12`, 32);
    await expect(page.getByText("Schedule saved.", { exact: true })).toBeVisible();
    expect(writes.at(-1)).toMatchObject({ start: "2026-10-12", end: "2026-10-14" });
    await dragBy(`Resize end for ${title1}`, 16);
    await expect(page.getByRole("button", { name: `Move ${title1}: 2026-10-12 to 2026-10-15`, exact: true })).toBeEnabled();
    await dragBy(`Resize start for ${title1}`, -16);
    await expect(page.getByRole("button", { name: `Move ${title1}: 2026-10-11 to 2026-10-15`, exact: true })).toBeEnabled();
    await page.getByLabel("Predecessor", { exact: true }).selectOption(keys[0]); await page.getByLabel("Successor", { exact: true }).selectOption(keys[1]);
    await page.getByRole("button", { name: "Add dependency", exact: true }).click();
    await expect(page.getByTestId("dependency-arrow")).toHaveCount(1);
    if (module === "srm") await page.screenshot({ path: "../.tmp/gantt-editable.png", fullPage: true });
    await page.reload(); await setRange(); await expect(page.getByTestId("dependency-arrow")).toHaveCount(1);
    failNext = true; await dragBy(`Resize end for ${title1}`, 16);
    await expect(page.getByRole("alert")).toContainText("Record dates changed");
    await expect(page.getByRole("button", { name: `Move ${title1}: 2026-10-11 to 2026-10-15`, exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Remove dependency", exact: true }).click(); await expect(page.getByTestId("dependency-arrow")).toHaveCount(0);
    readOnly = true; await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(page.getByRole("button", { name: `Resize end for ${title1}`, exact: true })).toBeDisabled();
  });
}

for (const path of ["/pms/timeline-plus", "/pms/dependency-timeline", "/pms/product-launch", "/pms/work-hub", "/pms/impact", "/pms/ai-planner"]) {
  test(`${path} uses the live Gantt API`, async ({ page }) => {
    await authenticateCommunication(page);
    let task = { id: 1, project_id: 1, title: "Live delivery task", task_key: "LIVE-1", status: "In Progress", priority: "High", start_date: "2026-10-20", due_date: "2026-11-04", assignees: [] };
    await page.route("**/api/v1/project-management/gantt*", route => respond(route, { tasks: [task], dependencies: [], warnings: [], filters: { projects: [{ id: 1, name: "Live delivery", project_key: "LIVE", can_manage_tasks: true }], sprints: [], epics: [], assignees: [], statuses: ["In Progress"] } }));
    await page.route("**/api/v1/project-management/tasks/1/schedule", async route => { task = { ...task, ...route.request().postDataJSON() }; await respond(route, { task, warnings: [] }); });
    await page.goto(path);
    if (!["/pms/timeline-plus", "/pms/dependency-timeline"].includes(path)) await page.getByRole("button", { name: "Timeline", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Gantt", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Resize end date for LIVE-1" })).toBeVisible();
    await expect(page.getByText("Live delivery task", { exact: true }).first()).toBeVisible();
    if (path === "/pms/timeline-plus") {
      await page.getByRole("button", { name: "Edit schedule for Live delivery task" }).click();
      await page.getByLabel("Schedule due date", { exact: true }).fill("2026-11-10");
      await page.getByRole("button", { name: "Save schedule", exact: true }).click();
      await expect(page.getByText("Schedule saved", { exact: true })).toBeVisible();
      expect(task.due_date).toBe("2026-11-10");
    }
  });
}
