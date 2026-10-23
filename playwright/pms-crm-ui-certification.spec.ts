import { expect, test, type Page } from "../frontend/node_modules/playwright/test";

type CertRole = "super_admin" | "crm_user" | "pms_user" | "viewer";

const users: Record<CertRole, { id: number; email: string; role: string; is_superuser: boolean; employee_id: number | null }> = {
  super_admin: { id: 1, email: "suite.admin@test.local", role: "admin", is_superuser: true, employee_id: null },
  crm_user: { id: 2, email: "sales@test.local", role: "crm_sales_executive", is_superuser: false, employee_id: null },
  pms_user: { id: 3, email: "pm@test.local", role: "pms_project_manager", is_superuser: false, employee_id: null },
  viewer: { id: 4, email: "viewer@test.local", role: "pms_viewer", is_superuser: false, employee_id: null },
};

const pmsRoutes = [
  "/pms",
  "/pms/projects",
  "/pms/projects/new",
  "/pms/tasks",
  "/pms/reports",
  "/pms/timesheets",
  "/pms/workload",
  "/pms/risks",
  "/pms/projects/1",
  "/pms/projects/1/board",
  "/pms/projects/1/milestones",
  "/pms/projects/1/files",
];

const crmRoutes = [
  "/crm",
  "/crm/leads",
  "/crm/contacts",
  "/crm/companies",
  "/crm/deals",
  "/crm/pipeline",
  "/crm/tasks",
  "/crm/calendar",
  "/crm/reports",
  "/crm/lead-scoring",
  "/crm/settings",
  "/crm/leads/1",
  "/crm/deals/1",
];

test.describe("PMS and CRM UI certification smoke", () => {
  test.beforeEach(async ({ page }) => {
    await installConsoleCapture(page);
  });

  test("PMS pages render for a project manager on desktop and mobile", async ({ page }) => {
    await authenticate(page, "pms_user");
    for (const route of pmsRoutes) {
      await expectHealthyRoute(page, route, /KaryaFlow|Project|Task|Report|Timesheet|Risk|Board|Milestone|Workload|Create/i);
    }

    await page.setViewportSize({ width: 390, height: 820 });
    await expectHealthyRoute(page, "/pms", /KaryaFlow|Project/i);
    await expectNoHorizontalOverflow(page);
  });

  test("CRM pages render for a sales user on desktop and mobile", async ({ page }) => {
    await authenticate(page, "crm_user");
    for (const route of crmRoutes.filter(route => !["/crm/lead-scoring", "/crm/settings"].includes(route))) {
      await expectHealthyRoute(page, route, /CRM|Lead|Contact|Company|Deal|Pipeline|Report|Task|Calendar|Custom/i);
    }

    await expectDenied(page, "/crm/lead-scoring");
    await expectDenied(page, "/crm/settings");
    await page.setViewportSize({ width: 390, height: 820 });
    await expectHealthyRoute(page, "/crm/leads", /Lead|CRM/i);
    await expectNoHorizontalOverflow(page);
  });

  test("module route access is isolated by role", async ({ page }) => {
    await authenticate(page, "crm_user");
    await expectHealthyRoute(page, "/crm/leads", /Lead|CRM/i);
    await expectDenied(page, "/pms/projects");

    await authenticate(page, "pms_user");
    await expectHealthyRoute(page, "/pms/projects", /Project|KaryaFlow/i);
    await expectDenied(page, "/crm/leads");

    await authenticate(page, "viewer");
    await expectHealthyRoute(page, "/pms/projects", /Project|KaryaFlow/i);
    await expectDenied(page, "/crm/deals");

    await authenticate(page, "super_admin");
    await expectHealthyRoute(page, "/crm/leads", /Lead|CRM/i);
    await expectHealthyRoute(page, "/pms/projects", /Project|KaryaFlow/i);
    await expectHealthyRoute(page, "/hrms", /HRMS|Dashboard|Business Suite/i);
  });
});

async function authenticate(page: Page, role: CertRole) {
  const user = users[role];
  await installApiStubs(page, user);
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "cert-token",
      refreshToken: "cert-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: {
        accessToken: "cert-token",
        refreshToken: "cert-refresh",
        user: authUser,
        isAuthenticated: true,
      },
      version: 0,
    }));
  }, user);
}

async function installConsoleCapture(page: Page) {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) consoleErrors.push(message.text());
  });
  await page.exposeFunction("__certConsoleErrors", () => consoleErrors);
}

async function installApiStubs(page: Page, user: (typeof users)[CertRole]) {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    let status = 200;
    let body: unknown = method === "GET" ? [] : {};

    if (path === "/business-os/modules") {
      body = { enabled_modules: ["hrms", "crm", "srm", "project_management", "fam", "ai", "communication"], modules: [] };
    } else if (path.includes("/auth/me")) {
      body = { id: user.id, email: user.email, role: { name: user.role }, is_superuser: user.is_superuser, employee_id: user.employee_id };
    } else if (path.includes("/auth/sso/providers")) {
      body = [];
    } else if (path.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (path.startsWith("/project-management")) {
      body = pmsResponse(path, method);
    } else if (path.startsWith("/crm")) {
      body = crmResponse(path, method);
    } else if (path.startsWith("/reports")) {
      body = path.includes("dashboard") ? {} : [];
    } else if (path.startsWith("/employees") || path.startsWith("/company") || path.startsWith("/attendance") || path.startsWith("/hrms")) {
      body = [];
    }

    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}

function pmsResponse(path: string, method: string) {
  const project = {
    id: 1,
    name: "Certification Project",
    project_key: "CERT",
    status: "Active",
    priority: "High",
    progress_percent: 64,
    manager_user_id: 3,
    start_date: "2026-06-01",
    end_date: "2026-06-30",
  };
  const task = {
    id: 1,
    project_id: 1,
    project_name: project.name,
    project_key: project.project_key,
    task_key: "CERT-1",
    title: "Validate PMS flow",
    status: "In Progress",
    priority: "High",
    assignee_user_id: 3,
    assignee_name: "PM User",
    due_date: "2026-06-20",
    story_points: 5,
    tags: ["uat"],
  };
  if (method !== "GET") return { ...project, id: 1 };
  const sprint = {
    id: 1,
    project_id: 1,
    name: "Sprint 1",
    status: "Active",
    start_date: "2026-06-01",
    end_date: "2026-06-14",
    committed_task_count: 1,
    committed_story_points: 5,
    completed_story_points: 2,
    scope_change_count: 0,
    carry_forward_task_count: 0,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-04T00:00:00Z",
  };
  if (path.includes("/dashboard")) return { project, metrics: { total_tasks: 1, completed_tasks: 0, progress_percent: 64 }, tasks: [task], milestones: [] };
  if (path.includes("/sprints")) return [sprint];
  if (path.includes("/reports/task-distribution")) {
    return {
      total_tasks: 1,
      total_story_points: 5,
      by_status: [{ name: "In Progress", tasks: 1, story_points: 5 }],
      by_priority: [{ name: "High", tasks: 1, story_points: 5 }],
      by_assignee: [{ assignee_id: 3, name: "PM User", tasks: 1, story_points: 5 }],
    };
  }
  if (path.includes("/reports/burndown")) {
    return { sprint_id: 1, committed_story_points: 5, completed_story_points: 2, remaining_story_points: 3, points: [{ date: "2026-06-04", ideal_remaining_points: 3, actual_remaining_points: 3, completed_points: 2 }] };
  }
  if (path.includes("/reports/velocity")) {
    return { project_id: 1, average_velocity_points: 5, sprints: [{ id: 1, name: "Sprint 1", end_date: "2026-06-14", velocity_points: 5 }] };
  }
  if (path.includes("/reports/cumulative-flow")) {
    return { statuses: ["In Progress", "Done"], points: [{ date: "2026-06-04", "In Progress": 1, Done: 0 }] };
  }
  if (path.includes("/reports/cycle-time")) {
    return { average_lead_time_hours: 24, average_cycle_time_hours: 16, items: [{ task_id: 1, task_key: "CERT-1", title: "Validate PMS flow", assignee_id: 3, story_points: 5, lead_time_hours: 24, cycle_time_hours: 16 }] };
  }
  if (path.includes("/reports/time-in-status")) {
    return { statuses: [{ status: "In Progress", hours: 16, days: 0.7 }], items: [{ task_id: 1, task_key: "CERT-1", statuses: { "In Progress": 16 } }] };
  }
  if (path.includes("/reports/project-health")) {
    return { points: [{ project: "Certification Project", health_score: 86, overdue_tasks: 0, open_risks: 0 }] };
  }
  if (path.includes("/reports/team-performance")) {
    return { items: [{ assignee_id: 3, name: "PM User", assigned_tasks: 1, completed_tasks: 0, assigned_points: 5, completed_points: 0, completion_rate: 0, avg_cycle_time_hours: 16 }] };
  }
  if (path.includes("/reports")) return { rows: [] };
  if (path.includes("/projects/1/tasks")) return [task];
  if (path.includes("/projects/1/milestones")) {
    return [{ id: 1, project_id: 1, name: "UAT Gate", status: "In Progress", due_date: "2026-06-20", progress_percent: 50, client_approval_status: "Pending" }];
  }
  if (path.includes("/files")) {
    return [{ id: 1, project_id: 1, file_name: "scope.pdf", original_name: "scope.pdf", mime_type: "application/pdf", size_bytes: 1024, storage_path: "metadata://scope.pdf", version_number: 1, visibility: "Project Team", created_at: "2026-06-04T00:00:00Z" }];
  }
  if (path.includes("/tasks/1")) return task;
  if (path.includes("/tasks")) {
    return {
      items: [task],
      total: 1,
      page: 1,
      pageSize: 25,
      pages: 1,
      filters: {
        projects: [{ id: project.id, name: project.name, project_key: project.project_key }],
        sprints: [],
        epics: [],
        statuses: ["In Progress", "Done"],
        priorities: ["High", "Medium"],
        assignees: [{ id: 3, name: "PM User" }],
        reporters: [],
        tags: ["uat"],
      },
    };
  }
  if (path.includes("/projects/1")) return project;
  if (path.includes("/projects")) return [project];
  if (path.includes("/timesheets")) return [];
  if (path.includes("/workload")) {
    return {
      basis: "hours",
      from: "2026-06-01",
      to: "2026-06-07",
      weeks: [{ week_start: "2026-06-01", label: "Jun 1" }],
      projects: [{ id: 1, name: project.name, project_key: project.project_key }],
      sprints: [sprint],
      users: [{ id: 3, name: "PM User" }],
      summary: { over_capacity: 0, near_capacity: 0 },
      rows: [{
        user_id: 3,
        user_name: "PM User",
        email: "pm@test.local",
        totals: { planned_hours: 6, story_points: 5, task_count: 1, capacity_hours: 40, utilization_percent: 15 },
        cells: [{
          week_start: "2026-06-01",
          planned_hours: 6,
          story_points: 5,
          task_count: 1,
          capacity_hours: 40,
          utilization_percent: 15,
          load_value: 6,
          load_unit: "h",
          status: "normal",
          tasks: [{ id: 1, task_key: "CERT-1", title: "Validate PMS flow", priority: "High", status: "In Progress", planned_hours: 6, story_points: 5 }],
        }],
      }],
    };
  }
  if (path.includes("/risks")) return [];
  if (path.includes("/users")) return [{ id: 3, email: "pm@test.local", name: "PM User" }];
  return [];
}

function crmResponse(path: string, method: string) {
  const paginated = (items: unknown[]) => ({ items, total: items.length, page: 1, per_page: 25, pages: 1 });
  const lead = { id: 1, fullName: "Aarav Mehta", full_name: "Aarav Mehta", email: "aarav@example.com", status: "New", source: "Website", ownerUserId: 2 };
  const deal = { id: 1, name: "Certification Deal", amount: 250000, status: "open", pipelineId: 1, stageId: 1, ownerUserId: 2 };
  if (method !== "GET") return lead;
  if (path.includes("/module-info")) return { label: "CRM", status: "ready" };
  if (path.includes("/roles")) return { items: [{ key: "crm_admin" }, { key: "sales_manager" }, { key: "sales_executive" }, { key: "crm_viewer" }] };
  if (path.includes("/leads/1")) return lead;
  if (path.includes("/deals/1")) return deal;
  if (path.includes("/leads")) return paginated([lead]);
  if (path.includes("/deals")) return paginated([deal]);
  if (path.includes("/contacts")) return paginated([{ id: 1, fullName: "Priya Shah", full_name: "Priya Shah", email: "priya@example.com" }]);
  if (path.includes("/companies") || path.includes("/accounts")) return paginated([{ id: 1, name: "Acme India", industry: "Technology" }]);
  if (path.includes("/pipelines")) return paginated([{ id: 1, name: "Default Pipeline" }]);
  if (path.includes("/pipeline-stages")) return paginated([{ id: 1, name: "Qualification", pipelineId: 1 }]);
  if (path.includes("/reports")) return { items: [], total: 0, won: 0, lost: 0, rows: [] };
  return paginated([]);
}

async function expectHealthyRoute(page: Page, route: string, pattern: RegExp) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(route)}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  await expect(page.locator(".vite-error-overlay, #webpack-dev-server-client-overlay")).toHaveCount(0);
  await expect(page.locator("body")).toContainText(pattern, { timeout: 20_000 });
  await expectNoHorizontalOverflow(page);
  const consoleErrors = await page.evaluate(async () => (window as unknown as { __certConsoleErrors: () => Promise<string[]> }).__certConsoleErrors());
  expect(consoleErrors.filter((item) => !isAllowedConsoleSignal(item))).toEqual([]);
}

async function expectDenied(page: Page, route: string) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
  const wide = overflow ? await page.evaluate(() => [...document.querySelectorAll("body *")].filter(e => e.getBoundingClientRect().width > innerWidth && getComputedStyle(e).position !== "fixed").slice(0, 12).map(e => ({ tag:e.tagName, cls:e.className, width:e.getBoundingClientRect().width }))) : [];
  expect(overflow, JSON.stringify(wide)).toBe(false);
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function isAllowedConsoleSignal(message: string) {
  return [
    "favicon",
    "NO_COLOR",
    "React Router Future Flag Warning",
    "/project-management/realtime?token=cert-token",
  ].some((allowed) => message.includes(allowed));
}


test("PMS custom field values save and survive task reload", async ({ page }) => {
  await authenticate(page, "pms_user");
  let value = "2025";
  await page.route("**/api/**/projects/1/epics**", route => route.fulfill({ json: [] }));
  await page.route("**/api/**/tags", route => route.fulfill({ json: [] }));
  await page.route("**/api/**/tasks/1/**", async route => {
    if (!route.request().url().includes("/custom-fields")) { await route.fulfill({ json: [] }); return; }
    if (route.request().method() === "PUT") {
      value = route.request().postDataJSON().value;
      await route.fulfill({ json: { field_id: 1, value } });
    } else {
      await route.fulfill({ json: { can_edit: true, can_manage: true, fields: [{ id: 1, name: "Tax period", field_type: "dropdown", options: ["2025", "2026"], value }] } });
    }
  });
  await page.goto("/pms/tasks/1");
  await page.getByLabel("Tax period", { exact: true }).selectOption("2026");
  await page.getByRole("button", { name: "Save Tax period", exact: true }).click();
  await expect(page.getByText("Tax period saved", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Tax period", { exact: true })).toHaveValue("2026");
});


test("PMS team creation and edit render persisted group membership", async ({ page }) => {
  await authenticate(page, "pms_user");
  let teams: { id: number; name: string; alias: string; member_ids: number[] }[] = [];
  await page.route("**/api/**/workspaces", route => route.fulfill({ json: [{ id: 1, name: "Team workspace" }] }));
  await page.route("**/api/**/workspaces/1/members", route => route.fulfill({ json: [{ id: 5, user_id: 3, email: "pm@test.local", role: "Owner" }] }));
  await page.route("**/api/**/workspaces/1/teams**", async route => {
    if (route.request().method() === "GET") await route.fulfill({ json: { teams, can_manage: true } });
    else { const team = { id: 1, ...route.request().postDataJSON() }; teams = [team]; await route.fulfill({ json: team }); }
  });
  await page.goto("/pms/teams");
  await page.getByLabel("Team name", { exact: true }).fill("Audit reviewers");
  await page.getByLabel("Alias", { exact: true }).fill("audit-reviewers");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Audit reviewers", exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Edit Audit reviewers", exact: true }).click();
  await expect(page.getByRole("checkbox")).toBeChecked();
  await page.getByLabel("Team name", { exact: true }).fill("Audit leads");
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Audit leads", exact: true })).toBeVisible();
});


test("PMS private message send and reload preserve conversation", async ({ page }) => {
  await authenticate(page, "pms_user");
  const conversation = { id: 7, participants: [{ id: 3, email: "pm@test.local" }, { id: 8, email: "reviewer@test.local" }] };
  let messages: { id: number; author_id: number; body: string; created_at: string }[] = [];
  await page.route("**/api/**/workspaces", route => route.fulfill({ json: [{ id: 1, name: "Private workspace" }] }));
  await page.route("**/api/**/workspaces/1/members", route => route.fulfill({ json: [{ id: 8, user_id: 8, email: "reviewer@test.local", role: "Member" }] }));
  await page.route("**/api/**/workspaces/1/direct-conversations**", async route => {
    if (route.request().url().endsWith("/messages")) {
      if (route.request().method() === "POST") {
        const message = { id: 1, author_id: 3, body: route.request().postDataJSON().body, created_at: "2026-10-23T12:00:00Z" };
        messages = [message]; await route.fulfill({ json: message });
      } else await route.fulfill({ json: { messages, has_more: false } });
    } else await route.fulfill({ json: { conversations: [conversation], can_send: true, user_id: 3 } });
  });
  await page.goto("/pms/messages?workspace=1");
  await page.getByRole("button", { name: "reviewer@test.local", exact: true }).click();
  await page.getByLabel("Private message", { exact: true }).fill("Please review the audit");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.getByText("Please review the audit", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "reviewer@test.local", exact: true }).click();
  await expect(page.getByText("Please review the audit", { exact: true })).toBeVisible();
});


test("PMS custom field manager creates and edits fields", async ({ page }) => {
  await authenticate(page, "pms_user");
  let fields: Record<string, unknown>[] = [];
  await page.route("**/api/**/project-management/custom-fields", route => route.fulfill({ json: { fields, projects: [{ id: 1, name: "Audit", can_manage: true }] } }));
  await page.route("**/api/**/projects/1/custom-fields**", async route => {
    const body = route.request().postDataJSON();
    const field = { id: 1, field_type: fields[0]?.field_type || body.field_type, ...body, project_id: 1, project_name: "Audit", can_manage: true, created_at: "2026-10-23T10:00:00Z" };
    fields = [field]; await route.fulfill({ json: field });
  });
  await page.goto("/pms/custom-fields");
  await page.getByRole("button", { name: "Create new", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("Refund amount");
  await dialog.getByLabel("Field project").selectOption("1");
  await dialog.getByLabel("Field type").selectOption("money");
  await dialog.getByRole("button", { name: "Create field", exact: true }).click();
  await page.getByRole("button", { name: "Edit Refund amount", exact: true }).click();
  await dialog.getByLabel("Name", { exact: true }).fill("Refund balance");
  await dialog.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("button", { name: "Edit Refund balance", exact: true })).toBeVisible();
  await page.getByLabel("Filter custom field type").selectOption("date");
  await expect(page.getByText("No fields match these filters.", { exact: true })).toBeVisible();
});


test("PMS capability tiers distinguish implemented and pending features", async ({ page }) => {
  await authenticate(page, "pms_user");
  await page.goto("/pms/plans");
  for (const name of ["Core", "Business", "Business Plus", "Enterprise"]) await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page.getByLabel("Filter capability tier").selectOption("Enterprise");
  await expect(page.getByRole("heading", { name: "Core", exact: true })).toHaveCount(0);
  await page.getByLabel("Search plan features").fill("SCIM");
  await expect(page.getByRole("heading", { name: "SSO, SCIM and SAML", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Enterprise capabilities" }).getByText("Not implemented", { exact: true })).toHaveCount(1);
});


test("PMS tag manager edits and confirms bulk deletion", async ({ page }) => {
  await authenticate(page, "pms_user");
  let tags = [{ id: 1, name: "Audit", color: "#123456", usage: 2, created_at: "2026-10-23T12:00:00Z", projects: [{ id: 1, name: "Audit project" }] }];
  await page.route("**/api/**/tag-manager**", async route => {
    if (route.request().method() === "GET") await route.fulfill({ json: { tags, can_manage: true } });
    else if (route.request().url().endsWith("/delete")) { tags = []; await route.fulfill({ json: { deleted: [1] } }); }
    else { tags = [{ ...tags[0], ...route.request().postDataJSON() }]; await route.fulfill({ json: tags[0] }); }
  });
  await page.goto("/pms/tags");
  await page.getByRole("button", { name: "Edit Audit", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Review");
  await page.getByRole("button", { name: "Save tag", exact: true }).click();
  await page.getByLabel("Select Review", { exact: true }).check();
  await page.getByRole("button", { name: "Delete 1 selected", exact: true }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Edit Review", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Delete 1 selected", exact: true }).click();
  await page.getByRole("button", { name: "Delete permanently", exact: true }).click();
  await expect(page.getByText("No tags match this view.", { exact: true })).toBeVisible();
});


test("PMS task type preset persists and can be archived and restored", async ({ page }) => {
  await authenticate(page, "pms_user");
  let types: Record<string, unknown>[] = [];
  await page.route("**/api/**/task-types**", async route => {
    if (route.request().method() === "GET") await route.fulfill({ json: { types, can_manage: true } });
    else { const record = { id: 1, builtin: false, usage: 0, ...route.request().postDataJSON() }; types = [record]; await route.fulfill({ json: record }); }
  });
  await page.goto("/pms/task-types");
  await page.getByRole("button", { name: "Add VAT Return", exact: true }).click();
  await expect(page.getByRole("button", { name: "Edit VAT Return", exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Archive VAT Return", exact: true }).click();
  await expect(page.getByRole("button", { name: "Edit VAT Return", exact: true })).toHaveCount(0);
  await page.getByLabel("Include archived").check();
  await page.getByRole("button", { name: "Restore VAT Return", exact: true }).click();
  await expect(page.getByRole("button", { name: "Archive VAT Return", exact: true })).toBeVisible();
});


test("PMS task type save-and-create-fields carries type scope", async ({ page }) => {
  await authenticate(page, "pms_user");
  let types: Record<string, unknown>[] = [];
  await page.route("**/api/**/task-types**", async route => {
    if (route.request().method() === "GET") await route.fulfill({ json: { types, can_manage: true } });
    else { const record = { id: 1, builtin: false, usage: 0, ...route.request().postDataJSON() }; types = [record]; await route.fulfill({ json: record }); }
  });
  await page.route("**/api/**/project-management/custom-fields", route => route.fulfill({ json: { fields: [], projects: [{ id: 1, name: "Audit", can_manage: true }] } }));
  await page.goto("/pms/task-types");
  await page.getByLabel("Name", { exact: true }).fill("VAT Return");
  await page.getByLabel("Plural name", { exact: true }).fill("VAT Returns");
  await page.getByRole("button", { name: "Save and create fields", exact: true }).click();
  await expect(page).toHaveURL(/custom-fields\?taskType=VAT/);
  await expect(page.getByLabel("Filter task type scope")).toHaveValue("VAT Return");
  await page.getByRole("button", { name: "Create new", exact: true }).click();
  await expect(page.getByLabel("Field task type")).toHaveValue("VAT Return");
});


test("PMS timer survives reload and saves once on stop", async ({ page }) => {
  await authenticate(page, "pms_user");
  let timer: Record<string, unknown> | null = null;
  let stops = 0;
  await page.route("**/api/**/project-management/projects**", async route => {
    await route.fulfill({ json: route.request().url().includes("/tasks") ? [{ id: 1, project_id: 1, title: "Audit", task_key: "AUD-1" }] : [{ id: 1, name: "Audit project" }] });
  });
  await page.route("**/api/**/time-logs**", route => route.fulfill({ json: [] }));
  await page.route("**/api/**/project-management/timer**", async route => {
    if (route.request().url().endsWith("/start")) { timer = { ...route.request().postDataJSON(), started_at: new Date().toISOString() }; await route.fulfill({ json: timer }); }
    else if (route.request().url().endsWith("/stop")) { stops++; timer = null; await route.fulfill({ json: { log_id: 1, active: false, duration_minutes: 1 } }); }
    else await route.fulfill({ json: timer });
  });
  await page.goto("/pms/time-tracking");
  await page.getByLabel("Timer project", { exact: true }).selectOption("1");
  await page.getByLabel("Timer task", { exact: true }).selectOption("1");
  await page.getByLabel("Timer notes", { exact: true }).fill("Audit review");
  await page.getByRole("button", { name: "Start timer", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop and save", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Audit review", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Stop and save", exact: true }).click();
  await expect(page.getByText("Saved 1 minute to your time logs", { exact: true })).toBeVisible();
  expect(stops).toBe(1);
});


test("PMS Docs saves, previews tables and preserves a conflicting draft", async ({ page }) => {
  await authenticate(page, "pms_user");
  let doc: Record<string, unknown> | null = null;
  await page.route("**/api/**/project-management/projects**", async route => {
    if (route.request().url().endsWith("/docs")) {
      doc = { id: 1, project_id: 1, project_name: "Audit", version: 1, updated_at: "2026-10-23T12:00:00Z", updated_by: "pm@test.local", can_edit: true, ...route.request().postDataJSON() };
      await route.fulfill({ json: doc });
    } else await route.fulfill({ json: route.request().url().includes("/tasks") ? [] : [{ id: 1, name: "Audit" }] });
  });
  await page.route("**/api/**/project-management/docs**", async route => {
    if (route.request().method() === "PUT") await route.fulfill({ status: 409, json: { detail: "Document changed; your draft is kept" } });
    else await route.fulfill({ json: route.request().url().endsWith("/docs") ? doc ? [doc] : [] : doc });
  });
  await page.goto("/pms/docs");
  await page.getByLabel("Document project").selectOption("1");
  await page.getByLabel("Document title").fill("Audit memo");
  await page.getByLabel("Document content").fill("## Findings\n\n| Area | Status |\n| --- | --- |\n| VAT | Reviewed |");
  await page.getByRole("button", { name: "Save document", exact: true }).click();
  await expect(page.getByText("Saved version 1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Findings", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Reviewed", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit source", exact: true }).click();
  await page.getByLabel("Document content").fill("My unsaved concurrent changes");
  await page.getByRole("button", { name: "Save document", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("your draft is kept");
  await expect(page.getByLabel("Document content")).toHaveValue("My unsaved concurrent changes");
});


test("PMS subtasks create, filter, reorder and promote", async ({ page }) => {
  await authenticate(page, "pms_user");
  let children: any[] = [];
  await page.route("**/api/**/projects/1/epics**", route => route.fulfill({ json: [] }));
  await page.route("**/api/**/tags", route => route.fulfill({ json: [] }));
  await page.route("**/api/**/users/search**", route => route.fulfill({ json: [{ id: 3, email: "pm@test.local" }] }));
  await page.route("**/api/**/tasks/1/**", async route => {
    const url = route.request().url();
    if (url.endsWith("/subtasks/reorder")) {
      children = route.request().postDataJSON().item_ids.map((id: number) => children.find(child => child.id === id));
      await route.fulfill({ json: children });
    } else if (url.endsWith("/subtasks")) {
      if (route.request().method() === "POST") {
        const child = { id: 10 + children.length, project_id: 1, task_key: `UI-${10 + children.length}`, ...route.request().postDataJSON() };
        children.push(child); await route.fulfill({ json: child });
      } else await route.fulfill({ json: children });
    } else await route.fulfill({ json: url.includes("custom-fields") ? { can_edit: true, can_manage: true, fields: [] } : [] });
  });
  await page.route("**/api/**/tasks/10", async route => {
    expect(route.request().postDataJSON().parent_task_id).toBeNull();
    children = children.filter(child => child.id !== 10);
    await route.fulfill({ json: { id: 10, parent_task_id: null } });
  });
  await page.goto("/pms/projects/1/tasks/1");
  await page.getByLabel("Subtask title", { exact: true }).fill("Prepare evidence");
  await page.getByLabel("Subtask description", { exact: true }).fill("Attach reviewed documents");
  await page.locator('summary[aria-label="New subtask assignees"]').click();
  await page.getByLabel("pm@test.local", { exact: true }).check();
  await page.getByRole("button", { name: "Add subtask", exact: true }).click();
  await expect(page.getByRole("button", { name: "Prepare evidence", exact: true })).toBeVisible();
  expect(children[0].assignee_user_ids).toEqual([3]);
  expect(children[0].description).toBe("Attach reviewed documents");
  await page.getByLabel("Subtask title", { exact: true }).fill("Review evidence");
  await page.getByRole("button", { name: "Add subtask", exact: true }).click();
  await page.getByLabel("Move Review evidence up", { exact: true }).click();
  await expect.poll(() => children[0]?.title).toBe("Review evidence");
  await page.getByLabel("Search subtasks", { exact: true }).fill("Prepare");
  await expect(page.getByRole("button", { name: "Review evidence", exact: true })).toHaveCount(0);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Promote", exact: true }).click();
  await expect(page.getByRole("button", { name: "Prepare evidence", exact: true })).toHaveCount(0);
});
