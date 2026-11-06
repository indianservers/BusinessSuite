import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { writeFileSync } from "node:fs";
import { authenticate } from "./srm-test-utils";
import { demoProjects, demoPeople, demoTasks, demoMessages } from "./fixtures/pms-populated-data";

async function installPopulatedPreview(page: Page) {
  await page.setViewportSize({ width: 1600, height: 1200 });
  await authenticate(page, "admin");
  const names = ["Homepage-wireframes.pdf", "Brand-guidelines.pdf", "Project-plan.xlsx", "Client-requirements.docx", "Homepage-desktop.png", "Mobile-layout.png", "API-contract.json", "Release-checklist.xlsx", "Sprint-review.pdf", "Design-assets.zip", "Client-feedback.docx", "Logo-variations.png", "QA-test-cases.xlsx", "Accessibility-audit.pdf", "Deployment-guide.docx", "User-research.pdf", "Navigation-flow.png", "Handover-notes.pdf"];
  const assets = names.map((name,i)=>({id:i+1,project_id:301,folder_id:i<6?1:i<12?2:3,file_name:name,original_name:name,size_bytes:245760,visibility:"Internal",version_number:i%3+1,created_at:"2026-11-07T10:00:00Z",updated_at:"2026-11-07T10:00:00Z"}));
  const folders = [{id:1,name:"Design"},{id:2,name:"Planning"},{id:3,name:"Delivery"}];
  const notes = ["Client review — decisions & next steps", "Sprint 4 planning", "Release readiness checklist"].map((title,i)=>({id:501+i,title,content:"## Design review\n\nThe team reviewed the updated homepage and mobile navigation.\n\n- Priya will finalize the mobile layouts.\n- Rahul will confirm API integration.\n- Client approval is planned for 10 November.\n\n### Next review\nShare the staging link before the client walkthrough.",project_id:301,project_name:demoProjects[0].name,task_id:null,task_title:null,folder_id:null,tags:["Review","Planning"],pinned:i===0,favorite:i===0,archived:false,version:1,visibility:"private",visibility_scope:"private",can_edit:true,can_share:true,preview:"Decisions, owners, and next steps from the client review.",created_at:"2026-11-07T09:00:00Z",updated_at:"2026-11-07T10:00:00Z",deleted_at:null}));
  const invoices = [125000,45000,10000].map((amount,i)=>({id:i+1,project_id:301,invoice_number:`INV-2026-00${i+1}`,currency:"INR",total_amount:amount,balance_amount:i===0?0:amount,document_status:"issued",delivery_status:"sent",payment_status:i===0?"paid":"unpaid"}));
  const risks = [{id:1,project_id:301,title:"Client approval could delay release",description:"Final content approval is pending with the client.",category:"Delivery",probability:4,impact:4,risk_score:16,status:"mitigating",owner_user_id:100,due_date:"2026-11-10",mitigation_plan:"Schedule the approval walkthrough and agree a fallback release scope.",created_at:"2026-11-06T09:00:00Z"},{id:2,project_id:301,title:"Mobile navigation regression",description:"Validate the responsive navigation before the release.",category:"Quality",probability:2,impact:3,risk_score:6,status:"open",owner_user_id:103,due_date:"2026-11-12",mitigation_plan:"Run the mobile browser regression suite.",created_at:"2026-11-06T09:00:00Z"}];
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const projectId = Number(path.match(/(?:projects|dashboard)\/(\d+)/)?.[1]) || 301;
    const project = demoProjects.find(p => p.id === projectId);
    let body: unknown;
    if (path === "/access/settings/defaults/effective") body = { values: {}, modules: {}, companyId: 1, branchId: null };
    else if (path === "/access/setup") body = { companyId: 1, ready: true, items: [] };
    else if (path === "/master-data/companies") body = { items: [], total: 0, canCreate: false };
    else if (path === "/project-management/projects") body = demoProjects.slice(Number(url.searchParams.get("skip") || 0), Number(url.searchParams.get("skip") || 0) + Number(url.searchParams.get("limit") || 100));
    else if (path === "/project-management/custom-fields") body = { fields: [] };
    else if (path === "/project-management/custom-fields/records") body = { records: Object.fromEntries(demoProjects.map(p => [p.id, { fields: [], can_edit: true }])) };
    else if (/\/projects\/\d+$/.test(path)) body = project;
    else if (/\/dashboard\/\d+$/.test(path)) body = { project, assignment_count: 12, status_counts: { Done: 7, "In Progress": 2, Blocked: 1, "To Do": 2 }, metrics: { total_tasks: 12, completed_tasks: 7, overdue_tasks: 2, high_risks: 1 } };
    else if (/\/projects\/\d+\/tasks$/.test(path)) body = demoTasks(projectId);
    else if (/\/projects\/\d+\/activity$/.test(path)) body = [{id:1,summary:'Rahul completed "Homepage UI"',created_at:"2026-11-07T10:50:00Z"},{id:2,summary:"Priya uploaded the design review brief",created_at:"2026-11-07T09:15:00Z"},{id:3,summary:"Ananya updated the client review milestone",created_at:"2026-11-07T08:30:00Z"}];
    else if (path === "/project-management/files") body = assets;
    else if (path === "/project-management/file-folders") { if(route.request().method()==="POST") {folders.push({id:folders.length+1,name:route.request().postDataJSON().name});} body = folders; }
    else if (/\/project-management\/files\/\d+$/.test(path) && route.request().method()==="PATCH") { const file=assets.find(f=>f.id===Number(path.split("/").pop())); if(file) file.folder_id=route.request().postDataJSON().folder_id; body=file; }
    else if (/\/projects\/\d+\/board$/.test(path)) body = {id:1,project_id:projectId,name:"Delivery",total_project_tasks:12,columns:[{id:1,name:"To Do",status_key:"TODO",position:0,task_count:2,tasks:demoTasks(projectId).slice(10)},{id:2,name:"In Progress",status_key:"IN_PROGRESS",position:1,task_count:3,tasks:demoTasks(projectId).slice(7,10)},{id:3,name:"Done",status_key:"DONE",position:2,task_count:7,tasks:demoTasks(projectId).slice(0,7)}]};
    else if (/\/projects\/\d+\/boards$/.test(path)) body = {items:[{id:1,name:"Delivery"}]};
    else if (path === "/project-management/gantt") body = {tasks:demoTasks(301),dependencies:[],warnings:[],filters:{projects:demoProjects,sprints:[],epics:[],assignees:demoPeople,statuses:["To Do","In Progress","Done"]}};
    else if (path === "/project-management/workspaces") body = [{id:7,name:"BusinessSuite",role:"Owner"}];
    else if (path === "/project-management/workspaces/7/overview") body = {projects:demoProjects};
    else if (path === "/project-management/workspaces/7/members") body = demoPeople;
    else if (path === "/project-management/workspaces/7/eligible-people") body = [];
    else if (["/srm/business/sellers", "/srm/business/teams", "/srm/sales-orders", "/srm/engagements"].includes(path)) body = [];
    else if (path === "/project-management/notes") body = notes.filter(note=>note.title.toLowerCase().includes((url.searchParams.get("q")||"").toLowerCase()));
    else if (path === "/project-management/note-folders") body = [];
    else if (/\/notes\/\d+$/.test(path)) body = notes.find(note=>note.id===Number(path.split("/").pop()));
    else if (/\/notes\/\d+\/attachments$/.test(path)) body = {items:[],removed_items:[],max_file_bytes:3000000,max_files:10,max_note_bytes:20000000};
    else if (/\/notes\/\d+\/(?:backlinks|links)$/.test(path)) body = [];
    else if (path === "/project-management/risks") body = risks.filter(r=>(!url.searchParams.get("status")||r.status===url.searchParams.get("status")));
    else if (/\/projects\/\d+\/billing$/.test(path)) body = {commercial:null,invoices,engagements:[],can_create:false,can_issue:false,can_send:false};
    else if (/\/projects\/\d+\/members$/.test(path)) body = demoPeople;
    else if (/\/projects\/\d+\/milestones$/.test(path)) body = [{id:1,name:"Requirements & Planning",status:"Completed",due_date:"2026-10-20"},{id:2,name:"UI/UX Design",status:"Completed",due_date:"2026-10-28"},{id:3,name:"Client design approval",status:"In Progress",due_date:"2026-11-10"},{id:4,name:"Development & Integration",status:"Planned",due_date:"2026-11-20"},{id:5,name:"Testing & UAT",status:"Planned",due_date:"2026-11-28"},{id:6,name:"Go Live",status:"Planned",due_date:"2026-12-05"}];
    else if (/\/projects\/\d+\/field-values$/.test(path)) body = { fields: [], can_edit: true };
    else if (path === "/collaboration/contexts/lookup") body = { conversation_id: Number(url.searchParams.get("entity_id")) };
    else if (path.endsWith("/chat/conversations")) body = { can_send: true, conversations: demoProjects.map(p => ({ id: p.id, joined: true, archived: false, name: p.name, participants: demoPeople.map(p => ({ id: p.id, email: p.email })) })) };
    else if (/\/conversations\/\d+\/messages$/.test(path)) { const id = Number(path.match(/conversations\/(\d+)/)![1]); body = { messages: demoMessages(id), before: null, read_through: id * 1000 + 9 }; }
    else if (path.endsWith("/read")) body = { unread: 0 };
    else if (path === "/collaboration/events") body = { cursor: 1, changed: false };
    else { await route.fallback(); return; }
    await route.fulfill({ json: body });
  });
}

test("preview 36 realistic projects with populated dashboards and team discussions", async ({ page }) => {
  test.setTimeout(120000);
  await installPopulatedPreview(page);
  await page.goto("/pms/team-communication");
  const selector = page.getByLabel("Project conversation", { exact: true });
  await expect(selector.locator("option")).toHaveCount(36);
  await expect(page.getByText("Confirmed. I’ll post the staging link and screenshots once the fixes are ready.")).toBeVisible();
  const collaboration = page.getByRole("button", { name: /^Collaboration/ });
  if (await collaboration.getAttribute("aria-expanded") !== "true") await collaboration.click();
  await page.getByRole("link", { name: "Team Communication", exact: true }).scrollIntoViewIfNeeded();
  await page.locator(".pc-timeline").evaluate(el => { el.scrollTop = 0; });
  await page.mouse.move(1500, 120);
  await page.screenshot({ path: "docs/qa/pms-populated-team-communication.png", fullPage: true });
  await selector.selectOption("336");
  await expect(page.locator(".page-description").filter({ hasText: "Year-End Financial Readiness" })).toBeVisible();
  await expect(page.locator(".pc-timeline")).toContainText("Confirmed.");
  await page.goto("/pms/projects/301");
  await expect(page.getByRole("heading", { name: "BusinessSuite Website Redesign", exact: true })).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toHaveCount(0);
  await page.getByText("Project actions", { exact: true }).click();
  await expect(page.getByRole("link", { name: "Edit project", exact: true })).toBeVisible();
  await page.screenshot({ path: "docs/qa/pms-populated-project-details.png", fullPage: true });
  writeFileSync("docs/qa/pms-sample-projects.json", JSON.stringify({ sampleData: true, projects: demoProjects, people: demoPeople, tasks: demoProjects.flatMap(p => demoTasks(p.id)), messages: demoProjects.flatMap(p => demoMessages(p.id)) }, null, 2));
  await page.goto("/pms/projects/classic");
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();
  await expect(page.locator('[data-testid^="project-card-"]')).toHaveCount(36);
  await page.getByRole("button", { name: "Table", exact: true }).click();
  await expect(page.getByRole("link", { name: "BusinessSuite Website Redesign", exact: true })).toBeVisible();
  await page.mouse.move(1500, 120);
  await page.screenshot({ path: "docs/qa/pms-projects-list-36.png", fullPage: false });
  await page.screenshot({ path: "docs/qa/pms-projects-list-36-full.png", fullPage: true });
});

test("single-project overview and all eight project tabs work on desktop and mobile", async ({ page }) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", error => { errors.push(error.message); console.log("Project browser error:", error.message); });
  await installPopulatedPreview(page);
  await page.setViewportSize({ width: 1680, height: 1100 });
  await page.goto("/pms/projects/301");
  await expect(page.getByRole("heading", { name: "Project at a glance", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent Activity", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent Tasks", exact: true })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Project views", exact: true });
  await expect(nav.getByRole("link")).toHaveCount(8);
  await expect(nav.getByRole("link", { name: "Overview", exact: true })).toHaveAttribute("aria-current", "page");
  await page.mouse.move(1500, 100);
  await page.screenshot({ path: "docs/qa/pms-project-overview-reference-desktop.png", fullPage: true });
  for (const [label, suffix] of [["Tasks", "board"], ["Timeline", "timeline"], ["Team", "members"], ["Files", "files"], ["Finance", "billing"], ["Notes", "notes"], ["Risks", "risks"]]) {
    await nav.getByRole("link", { name: new RegExp(`^${label}`) }).click();
    await expect(page).toHaveURL(new RegExp(`/pms/projects/301/${suffix}(?:\\?.*)?$`));
    await expect(page.getByRole("heading", { name: "BusinessSuite Website Redesign", exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: new RegExp(`^${label}`) })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: "Something went wrong", exact: true })).toHaveCount(0);
    if (suffix === "board") {
      await expect(page.locator(".pipeline-card")).toHaveCount(12);
      await page.getByPlaceholder("Search tasks", { exact: true }).fill("wireframes");
      await expect(page.locator(".pipeline-card")).toHaveCount(1);
      await page.getByPlaceholder("Search tasks", { exact: true }).fill("");
    }
    if (suffix === "timeline") {
      await expect(page.getByRole("button", { name: /^Edit schedule for/ })).toHaveCount(12);
      await expect(page.getByLabel("Project", { exact: true })).toBeDisabled();
      await page.getByRole("button", { name: /^Edit schedule for/ }).first().click();
      await expect(page.getByLabel("Schedule start date", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Close", exact: true }).click();
    }
    if (suffix === "members") await expect(page.locator(".pd-member-card")).toHaveCount(6);
    if (suffix === "files") {
      await expect(page.locator(".pd-file-card")).toHaveCount(18);
      await page.getByLabel("Search project files", { exact: true }).fill("Homepage");
      await expect(page.locator(".pd-file-card")).toHaveCount(2);
      await page.getByLabel("Search project files", { exact: true }).fill("");
      await page.getByLabel("Folder name", { exact: true }).fill("Client approvals");
      await page.getByRole("button", { name: "Create folder", exact: true }).click();
      await expect(page.getByLabel("Filter files by folder", { exact: true }).locator("option")).toHaveCount(6);
      await page.getByLabel("Move Homepage-wireframes.pdf to folder", { exact: true }).selectOption("2");
      await expect(page.getByRole("status").filter({ hasText: "File moved to folder" })).toBeVisible();
      await page.getByLabel("Filter files by folder", { exact: true }).selectOption("1");
      await expect(page.locator(".pd-file-card")).toHaveCount(5);
      await page.getByLabel("Filter files by folder", { exact: true }).selectOption("all");
    }
    if (suffix === "billing") {
      await expect(page.getByRole("group", { name: /^Invoice INV/ })).toHaveCount(3);
      await page.getByText("Commercial identity & billing settings", { exact: true }).click();
      await expect(page.getByRole("button", { name: "Save billing identity", exact: true })).toBeVisible();
      await page.getByText("Commercial identity & billing settings", { exact: true }).click();
    }
    if (suffix === "notes") {
      await expect(page.getByLabel("Note title", { exact: true })).toHaveValue("Client review — decisions & next steps");
      await page.getByLabel("Search notes", { exact: true }).fill("Sprint");
      await expect(page.locator(".notes-card-list")).toContainText("Sprint 4 planning");
      await page.getByLabel("Search notes", { exact: true }).fill("");
    }
    if (suffix === "risks") {
      await expect(page.getByText("Client approval could delay release", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Project", { exact: true })).toBeDisabled();
      await page.getByLabel("Status", { exact: true }).selectOption("mitigating");
      await expect(page.getByText("Mobile navigation regression", { exact: true })).toHaveCount(0);
      await page.getByLabel("Status", { exact: true }).selectOption("");
      await page.getByRole("button", { name: "Add risk", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Add risk", exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Close risk form", exact: true }).click();
    }
    await page.locator(".pd-view-intro h2").click();
    await page.locator("#suite-main").evaluate(el=>{el.scrollTop=0;});
    await page.mouse.move(1500, 100);
    await page.screenshot({ path: `docs/qa/pms-project-tab-${suffix}.png`, fullPage: false });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `docs/qa/pms-project-tab-${suffix}-mobile.png`, fullPage: false });
    await page.setViewportSize({ width: 1680, height: 1100 });
  }
  await nav.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Project at a glance", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "BusinessSuite Website Redesign", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "docs/qa/pms-project-overview-reference-mobile.png", fullPage: false });
  await page.setViewportSize({ width: 1680, height: 1100 });
  await page.route(/\/project-management\/projects\?/, route => route.fulfill({ json: [demoProjects[0]] }));
  await page.goto("/pms/projects/336/files");
  await expect(page.getByRole("heading", { name: "Year-End Financial Readiness", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Upload files", exact: true })).toBeEnabled();
  await expect(page.locator(".pd-file-card")).toHaveCount(18);
  expect(errors).toEqual([]);
});
