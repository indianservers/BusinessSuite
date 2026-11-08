import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";
async function setup(page: any) {
  await authenticate(page, "admin");
  const rows = [
    {
      id: 701,
      name: "Website delivery",
      project_key: "WEB",
      status: "Active",
      priority: "High",
      health: "Good",
      due_date: "2020-01-01",
      owner_user_id: 100,
      owner_name: "Portfolio owner",
      client_name: "Acme",
      team: [{ id: 100, name: "Portfolio owner", role: "Manager" }, {id:101,name:"Delivery lead",role:"Member"}],
      workspace_id: 1,
      task_count: 4,
      completed_task_count: 1,
      calculated_progress: 25,
      overdue_task_count: 1,
      can_edit_project: true,
      can_manage_tasks: true,
    },
    {
      id: 702,
      name: "Completed engagement",
      project_key: "DONE",
      workspace_id: 2,
      status: "Completed",
      priority: "Medium",
      health: "Good",
      task_count: 2,
      completed_task_count: 2,
      calculated_progress: 100,
      can_edit_project: false,
    },
  ].map((p) => ({
    ...p,
    progress_percent: 0,
    is_archived: false,
    created_at: "2026-01-01",
    updated_at: "2026-11-01",
  }));
  await page.route("**/api/v1/project-management/**", async (route: any) => {
    const path = new URL(route.request().url()).pathname;
    let body: any = [];
    if (path.endsWith("/projects")) body = rows;
    else if (path.endsWith("/custom-fields")) body = { fields: [] };
    else if (path.endsWith("/custom-fields/records")) body = { records: {} };
    else if (path.endsWith("/workspaces"))
      body = [{ id: 1, name: "Main workspace", role: "Admin" }];
    else if (route.request().method() === "PATCH") {
      const p = rows.find((p) => path.endsWith("/" + p.id));
      Object.assign(p!, route.request().postDataJSON());
      body = p;
    }
    await route.fulfill({ json: body });
  });
  await page.route("**/api/v1/pipeline-workspaces/**", async (route: any) =>
    route.fulfill({
      json:
        route.request().method() === "GET"
          ? { preferences: { module_filters: {} }, views: [], can_share: true }
          : {},
    }),
  );
  await page.route("**/api/v1/access/settings/defaults/effective", (route) =>
    route.fulfill({
      json: { values: {}, modules: {}, companyId: 1, branchId: null },
    }),
  );
  await page.route("**/api/v1/access/setup", (route) =>
    route.fulfill({ json: { companyId: 1, ready: true, items: [] } }),
  );
  await page.goto("/pms/projects");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(2);
}
test("portfolio filters, edits, previews, export and views", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1680, height: 1000 });
  await setup(page);
  await expect(page.locator(".portfolio-ring")).toHaveText("50%");
  await page.screenshot({
    path: "docs/qa/pms-portfolio-desktop.png",
    fullPage: true,
  });
  await page
    .getByLabel("Portfolio summary")
    .getByRole("button", { name: "Overdue 1", exact: true })
    .click();
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(1);
  await page
    .getByRole("button", { name: "All Projects 2", exact: true })
    .click();
  await page
    .getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    })
    .selectOption("Critical");
  await expect(page.getByRole("status")).toContainText("updated");
  await page
    .getByRole("button", { name: "Preview Website delivery", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("1 complete / 4 total");
  await page.keyboard.press("Escape");
  await page.getByRole("textbox", { name: "Search projects" }).fill("Acme");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(1);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export filtered projects as CSV", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("projects.csv");
  await page.getByRole("button",{name:"Add portfolio views",exact:true}).click();await page.locator(".wv-catalog .wv-view-option").filter({has:page.getByText("Gallery",{exact:true})}).getByRole("button").first().click();
  await expect(page.locator(".portfolio-cards article")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Dashboard", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Projects by status" }),
  ).toBeVisible();
});
test("mobile cards and quick creation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await expect(page.locator(".portfolio-table-wrap")).toBeHidden();
  await expect(page.locator(".portfolio-mobile-cards article")).toHaveCount(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "docs/qa/pms-portfolio-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "New Project", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Main workspace");
  await expect(
    page.getByRole("button", { name: "Create project", exact: true }),
  ).toBeDisabled();
});
test("compound conditions and bulk changes respect editable selection", async ({
  page,
}) => {
  await setup(page);
  await page.getByRole("button", { name: "More filters", exact: true }).click();
  await page.getByText("Combine filter conditions", { exact: false }).click();
  await page
    .getByRole("button", { name: "Add condition", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Condition 1 value" })
    .fill("Website");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Add condition", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Condition 2 value" })
    .fill("Completed");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(0);
  await page
    .getByRole("combobox", { name: "Filter condition matching" })
    .selectOption("any");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(2);
  await page
    .getByRole("checkbox", { name: "Select Completed engagement", exact: true })
    .isDisabled();
  await page
    .getByRole("checkbox", { name: "Select Website delivery", exact: true })
    .check();
  await page
    .getByRole("combobox", { name: "Bulk priority", exact: true })
    .selectOption("Low");
  await expect(page.getByRole("dialog", {name:"Review bulk change"})).toBeVisible();
  await page.getByRole("button", {name:"Apply changes",exact:true}).click();
  await expect(
    page.getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    }),
  ).toHaveValue("Low");
  await page.route("**/api/v1/project-management/projects/701", (route) =>
    route.fulfill({ status: 403, json: { detail: "Access changed" } }),
  );
  await page
    .getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    })
    .selectOption("High");
  await expect(page.getByRole("alert")).toContainText("Access changed");
  await expect(
    page.getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    }),
  ).toHaveValue("Low");
});


test("project click previews, double-click opens, and quick actions respect permissions", async ({ page }) => {
  await page.setViewportSize({ width: 1680, height: 1000 });
  await setup(page);
  const row = page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)").first();
  const name = row.locator(".portfolio-project-name");
  await name.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page).toHaveURL(/\/pms\/projects$/);
  await page.keyboard.press("Escape");
  await row.getByText("Acme", { exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await row.locator(".pms-record-more").click();
  await expect(page.getByRole("menuitem", {name:"Add task",exact:true})).toBeVisible();
  await page.keyboard.press("Escape");
  await page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)").nth(1).locator(".pms-record-more").click();
  await expect(page.getByRole("menuitem",{name:"Add task",exact:true})).toHaveCount(0);
  await page.keyboard.press("Escape");
  await name.dblclick();
  await expect(page).toHaveURL(/\/pms\/projects\/701$/);
  await expect(page.locator(".portfolio-preview")).toHaveCount(0);
});

test("gallery supports preview, double-click and explicit open", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await setup(page);
  await page.getByRole("button",{name:"Add portfolio views",exact:true}).click();await page.locator(".wv-catalog .wv-view-option").filter({has:page.getByText("Gallery",{exact:true})}).getByRole("button").first().click();
  const card = page.locator(".portfolio-cards article").first();
  await card.locator("h2 button").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(card.getByRole("link", { name: "Open", exact: true })).toHaveAttribute("href", "/pms/projects/701");
  await card.locator("h2 button").dblclick();
  await expect(page).toHaveURL(/\/pms\/projects\/701$/);
});


test("preview navigation, pinned browsing and remembered width", async ({page})=>{
  await page.setViewportSize({width:1680,height:1000});await setup(page);
  await page.getByRole("button",{name:"Preview Website delivery",exact:true}).click();
  await page.getByRole("button",{name:"Next project",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("Completed engagement");
  await page.getByRole("button",{name:"Previous project",exact:true}).click();
  const resize=page.getByRole("separator",{name:"Resize project preview"});await resize.focus();await page.keyboard.press("ArrowLeft");
  await expect(resize).toHaveAttribute("aria-valuenow","640");
  await page.getByRole("button",{name:"Keep preview open",exact:true}).click();
  await expect(page.locator(".portfolio-pinned-preview")).toBeVisible();
  await page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)").nth(1).locator(".portfolio-project-name").click();
  await expect(page.locator(".portfolio-pinned-preview")).toContainText("Completed engagement");
  await page.getByRole("button",{name:"Close record details",exact:true}).click();
  await page.locator(".portfolio-view-options > summary").click();
  await page.getByRole("combobox",{name:"Project focus",exact:true}).selectOption("recent");
  await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(2);
});

test("personal table layout hides columns, changes density, and resets",async({page})=>{
  await page.setViewportSize({width:1680,height:1000});await setup(page);
  await page.locator(".native-table-toolbar summary").click();
  await page.getByRole("combobox",{name:"Row density",exact:true}).selectOption("compact");
  await expect(page.locator(".native-table-compact")).toBeVisible();
  await page.locator(".native-column-options").getByRole("checkbox",{name:"Client",exact:true}).uncheck();
  await expect(page.locator(".portfolio-table th").filter({hasText:/^Client$/})).toHaveCount(0);
  await page.getByRole("button",{name:"Move Owner / Team left",exact:true}).click();
  await page.getByRole("button",{name:"Reset table layout",exact:true}).click();
  await expect(page.locator(".portfolio-table th").filter({hasText:/^Client$/})).toHaveCount(1);
});

test("preview task completion, milestone creation and private note use existing APIs",async({page})=>{
  await page.setViewportSize({width:1680,height:1000});await setup(page);
  const changes:any[]=[];let taskStatus="To Do";
  await page.route("**/api/v1/project-management/projects/701/tasks?**",r=>r.fulfill({json:[{id:11,project_id:701,title:"Late task",task_key:"WEB-1",status:taskStatus,due_date:"2020-01-01"}]}));
  await page.route("**/api/v1/project-management/tasks/11",async r=>{changes.push(r.request().postDataJSON());taskStatus="Done";await r.fulfill({json:{id:11,status:"Done"}});});
  await page.route("**/api/v1/project-management/projects/701/milestones**",async r=>{if(r.request().method()==="POST")changes.push(r.request().postDataJSON());await r.fulfill({json:r.request().method()==="GET"?[]:{id:12}});});
  await page.route("**/api/v1/project-management/notes",async r=>{changes.push(r.request().postDataJSON());await r.fulfill({json:{id:13}});});
  await page.getByRole("button",{name:"Preview Website delivery",exact:true}).click();
  await page.getByRole("checkbox",{name:"Complete Late task",exact:true}).click();
  await expect.poll(()=>changes.some(c=>c.status==="Done")).toBeTruthy();
  await page.getByRole("button",{name:"milestones",exact:true}).click();
  await page.getByLabel("Quick milestone name",{exact:true}).fill("Launch review");
  await page.getByRole("button",{name:"Add milestone",exact:true}).click();
  await expect.poll(()=>changes.some(c=>c.name==="Launch review")).toBeTruthy();
  await page.getByRole("button",{name:"Quick note",exact:true}).click();
  await page.getByLabel("Quick note title",{exact:true}).fill("Decision");await page.getByLabel("Quick note text",{exact:true}).fill("Confirm scope");
  await page.getByRole("button",{name:"Save private note",exact:true}).click();
  await expect.poll(()=>changes.some(c=>c.title==="Decision"&&c.project_id===701)).toBeTruthy();
});

test("project creation keeps drafts and can create another",async({page})=>{
  await setup(page);await page.getByRole("button",{name:"New Project",exact:true}).click();
  await page.getByLabel("Project name",{exact:true}).fill("Draft retained");
  await page.keyboard.press("Escape");await page.getByRole("button",{name:"New Project",exact:true}).click();
  await expect(page.getByLabel("Project name",{exact:true})).toHaveValue("Draft retained");
  await page.getByRole("combobox",{name:"Project brief template",exact:true}).selectOption("launch");
  await page.getByRole("checkbox",{name:"Create another after saving",exact:true}).check();
  await page.route("**/api/v1/project-management/projects",r=>r.fulfill({json:{id:800,name:"Draft retained",status:"Active"}}));
  await page.getByRole("button",{name:"Create project",exact:true}).click();
  await expect(page.getByRole("dialog",{name:"New project",exact:true})).toBeVisible();
  await expect(page.getByLabel("Project name",{exact:true})).toHaveValue("");
});

test("bulk deadline waits for review and failed inline changes retain retry",async({page})=>{
  await setup(page);await page.getByRole("checkbox",{name:"Select Website delivery",exact:true}).check();
  await page.getByLabel("Bulk deadline",{exact:true}).fill("2027-01-01");
  await page.getByRole("button",{name:"Review deadline change",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("2027-01-01");
  await page.getByRole("button",{name:"Apply changes",exact:true}).click();
  await expect(page.getByRole("status").filter({hasText:"Deadline updated"})).toBeVisible();
  let failed=true;
  await page.route("**/api/v1/project-management/projects/701",r=>failed?r.fulfill({status:503,json:{detail:"Temporary failure"}}):r.fulfill({json:{id:701,status:"Active",priority:"Critical"}}));
  await page.getByRole("combobox",{name:"Priority for Website delivery",exact:true}).selectOption("Critical");
  await expect(page.getByRole("button",{name:"Retry saved edit",exact:true})).toBeVisible();
  failed=false;await page.getByRole("button",{name:"Retry saved edit",exact:true}).click();
  await expect(page.getByRole("combobox",{name:"Priority for Website delivery",exact:true})).toHaveValue("Critical");
});

test("page action sheet reuses page controls and keyboard search",async({page})=>{
  await setup(page);await page.locator(".portfolio-heading").click();await page.keyboard.press("Alt+Shift+A");
  const dialog=page.getByRole("dialog",{name:"Page actions",exact:true});await expect(dialog).toBeVisible();
  await dialog.getByRole("textbox",{name:"Find page action",exact:true}).fill("New Project");
  await dialog.getByRole("button",{name:"New Project",exact:true}).click();
  await expect(page.getByRole("dialog",{name:"New project",exact:true})).toBeVisible();
  await page.keyboard.press("Escape");await page.locator(".portfolio-heading").click();await page.keyboard.press("/");
  await expect(page.getByRole("textbox",{name:"Search projects",exact:true})).toBeFocused();
});


test("mobile project actions use existing menu as touch sheet",async({page})=>{
 await page.setViewportSize({width:390,height:844});await setup(page);
 const card=page.locator(".portfolio-mobile-cards article").first();await card.locator(".portfolio-mobile-more button").click();
 await expect(page.locator(".pms-record-mobile-sheet")).toBeVisible();
 const bounds=await page.locator(".pms-record-mobile-sheet").boundingBox();expect(bounds!.width).toBeGreaterThan(350);expect(bounds!.y+bounds!.height).toBeGreaterThan(820);
 await page.keyboard.press("Escape");await expect(page.locator(".pms-record-mobile-sheet")).toHaveCount(0);
});
test("status changes offer working undo",async({page})=>{
 await setup(page);const status=page.getByRole("combobox",{name:"Status for Website delivery",exact:true});await status.selectOption("On Hold");await expect(status).toHaveValue("On Hold");
 await page.getByRole("button",{name:"Undo",exact:true}).click();await expect(status).toHaveValue("Active");
});


test("owner undo, attention filters, filter chips and per-workspace preferences",async({page})=>{
 await page.setViewportSize({width:1680,height:1000});await setup(page);
 const owner=page.getByRole("combobox",{name:"Owner for Website delivery",exact:true});await owner.selectOption("101");await expect(owner).toHaveValue("101");await page.getByRole("button",{name:"Undo",exact:true}).click();await expect(owner).toHaveValue("100");
 await page.locator(".portfolio-view-options > summary").click(); await page.getByRole("combobox",{name:"Project focus",exact:true}).selectOption("attention");await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(1);
 await page.getByRole("button",{name:"Clear focus filter",exact:true}).click();await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(2);
 await page.getByRole("combobox",{name:"Filter status",exact:true}).selectOption("Active");await expect(page.getByRole("button",{name:"Clear status filter",exact:true})).toBeVisible();
 await page.getByRole("button",{name:"Clear all",exact:true}).click();await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(2);
 await page.getByRole("textbox",{name:"Search projects",exact:true}).fill("Website");await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(1);
 await page.goto("/pms/projects?workspace=2");await expect(page.getByRole("textbox",{name:"Search projects",exact:true})).toHaveValue("");await expect(page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)")).toHaveCount(1);await expect(page.locator(".portfolio-table")).toContainText("Completed engagement");
});

test("project shortcut choices apply to the consolidated menu and reduced motion is respected",async({page})=>{
 await page.setViewportSize({width:1680,height:1000});await setup(page);
 await page.locator(".portfolio-view-options > summary").click();await page.getByText("Quick action buttons",{exact:true}).click();
 await page.getByRole("checkbox",{name:"duplicate",exact:true}).uncheck();await page.locator(".portfolio-view-options > summary").click();
 await page.locator(".portfolio-table .pms-record-more").first().click();await expect(page.getByRole("menuitem",{name:"Duplicate project",exact:true})).toHaveCount(0);await page.keyboard.press("Escape");
 await page.locator(".portfolio-view-options > summary").click();await page.getByRole("checkbox",{name:"duplicate",exact:true}).check();await page.locator(".portfolio-view-options > summary").click();
 await page.locator(".portfolio-table .pms-record-more").first().click();await expect(page.getByRole("menuitem",{name:"Duplicate project",exact:true})).toBeVisible();await page.keyboard.press("Escape");
 await expect(page.getByRole("combobox",{name:"Filter status",exact:true}).locator('option[value="Active"]')).toHaveText("Active (1)");
 await expect(page.locator('.portfolio-table [title="No deadline set"]')).toHaveCount(1);await expect(page.locator(".portfolio-table")).toContainText("owner needed");
 await page.emulateMedia({reducedMotion:"reduce"});const duration=await page.locator("#suite-main").evaluate(el=>getComputedStyle(el).animationDuration);expect(parseFloat(duration)).toBeLessThan(.001);
});

test("compact dates open an editor, save on Enter, and cancel on Escape",async({page})=>{
 await page.setViewportSize({width:1680,height:1000});await setup(page);
 const patches:any[]=[];page.on("request",request=>{if(request.method()==="PATCH"&&request.url().endsWith("/projects/701"))patches.push(request.postDataJSON());});
 const date=page.getByRole("button",{name:"Edit Due date for Website delivery",exact:true});await expect(date).toBeVisible();await date.click();
 const input=page.getByLabel("Due date for Website delivery",{exact:true});await input.fill("2026-12-10");await input.press("Enter");
 await expect.poll(()=>patches.some(p=>p.due_date==="2026-12-10")).toBeTruthy();await expect(date).toBeVisible();
 const before=patches.length;await date.click();await input.fill("2026-12-20");await input.press("Escape");await expect(date).toBeVisible();expect(patches.length).toBe(before);
});

test("group creation shows the chosen status before submission",async({page})=>{
 await page.setViewportSize({width:1680,height:1000});await setup(page);
 await page.getByRole("button",{name:"Add project in Completed",exact:true}).click();
 const dialog=page.getByRole("dialog",{name:"New project",exact:true});await expect(dialog.getByLabel("New project status",{exact:true})).toHaveValue("Completed");
 await expect(dialog.getByLabel("Project workspace",{exact:true})).toHaveValue("1");await page.keyboard.press("Escape");
});
test("grouping uses owner names and combines missing dates",async({page})=>{
 await page.setViewportSize({width:1680,height:1000});await setup(page);
 const group=page.getByLabel("Group loaded rows by",{exact:true});await group.selectOption("Owner / Team");
 await expect(page.locator(".native-group-row .suite-group-badge").filter({hasText:/^Portfolio owner$/})).toHaveCount(1);
 await group.selectOption("Start date");await expect(page.locator(".native-group-row")).toHaveCount(1);await expect(page.locator(".native-group-row .suite-group-badge")).toHaveText("Not set");await expect(page.locator(".native-group-row .suite-group-count")).toHaveText("2");
});
