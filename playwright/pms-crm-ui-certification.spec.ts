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
    for (const route of crmRoutes) {
      await expectHealthyRoute(page, route, /CRM|Lead|Contact|Company|Deal|Pipeline|Report|Task|Calendar|Custom/i);
    }

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

    if (path.includes("/auth/me")) {
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
      body = {};
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
  expect(overflow).toBe(false);
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
