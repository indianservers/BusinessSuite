import { expect, test, type Locator, type Page } from "../frontend/node_modules/playwright/test";

type RoleName =
  | "admin"
  | "hr"
  | "employee"
  | "hr_company_admin"
  | "hr_workflow_admin"
  | "hr_custom_field_admin";

const users: Record<RoleName, { id: number; email: string; role: string; is_superuser: boolean; employee_id: number | null }> = {
  admin: { id: 1, email: "admin.rbac@test.local", role: "admin", is_superuser: true, employee_id: null },
  hr: { id: 2, email: "hr.rbac@test.local", role: "hr", is_superuser: false, employee_id: null },
  employee: { id: 3, email: "employee.rbac@test.local", role: "employee", is_superuser: false, employee_id: 1001 },
  hr_company_admin: { id: 4, email: "company.delegate@test.local", role: "hr_company_admin", is_superuser: false, employee_id: null },
  hr_workflow_admin: { id: 5, email: "workflow.delegate@test.local", role: "hr_workflow_admin", is_superuser: false, employee_id: null },
  hr_custom_field_admin: { id: 6, email: "customfield.delegate@test.local", role: "hr_custom_field_admin", is_superuser: false, employee_id: null },
};

const registeredRoutes = [
  "/hrms",
  "/hrms/dashboard",
  "/hrms/role-home",
  "/hrms/admin-home",
  "/hrms/hr-home",
  "/hrms/executive-home",
  "/hrms/manager-dashboard",
  "/hrms/ess",
  "/hrms/employee-directory",
  "/hrms/employees",
  "/hrms/employees/new",
  "/hrms/employees/1",
  "/hrms/probation",
  "/hrms/attendance",
  "/hrms/my-attendance",
  "/hrms/attendance/shift-roster",
  "/hrms/my-roster",
  "/hrms/timesheets",
  "/hrms/workflow",
  "/hrms/workflow-designer",
  "/hrms/notifications",
  "/hrms/leave",
  "/hrms/payroll",
  "/hrms/my-payslips",
  "/hrms/fnf-settlements",
  "/hrms/investment-declaration",
  "/hrms/recruitment",
  "/hrms/performance",
  "/hrms/benefits",
  "/hrms/lms",
  "/hrms/statutory-compliance",
  "/hrms/background-verification",
  "/hrms/whatsapp-ess",
  "/hrms/custom-fields",
  "/hrms/enterprise",
  "/hrms/engagement",
  "/hrms/helpdesk",
  "/hrms/reports",
  "/hrms/advanced-analytics",
  "/hrms/logs",
  "/hrms/company",
  "/hrms/org-chart",
  "/hrms/settings",
  "/hrms/assets",
  "/hrms/onboarding",
  "/hrms/documents",
  "/hrms/exit",
  "/hrms/ai-assistant",
  "/hrms/profile",
];

const criticalPatternRoutes = [
  "/hrms/security",
  "/hrms/employee-master",
  "/hrms/payroll/setup",
  "/hrms/payroll/run",
  "/hrms/payroll/tools",
  "/hrms/payroll/reports",
  "/hrms/payroll/bulk-publish",
  "/hrms/payroll/bulk-export",
  "/hrms/employees/bulk-import",
  "/hrms/attendance/bulk-import",
  "/hrms/workflow/admin",
  "/hrms/audit-log",
];

const employeeAllowed = new Set([
  "/hrms",
  "/hrms/ess",
  "/hrms/profile",
  "/hrms/my-attendance",
  "/hrms/leave",
  "/hrms/my-payslips",
  "/hrms/documents",
  "/hrms/workflow",
  "/hrms/my-roster",
]);

const employeeForbiddenHrefs = [
  "/hrms/payroll",
  "/hrms/attendance",
  "/hrms/attendance/shift-roster",
  "/hrms/reports",
  "/hrms/company",
  "/hrms/workflow-designer",
  "/hrms/custom-fields",
  "/hrms/settings",
  "/hrms/security",
  "/hrms/logs",
  "/hrms/recruitment",
  "/hrms/employees",
  "/hrms/employee-master",
  "/hrms/payroll/setup",
  "/hrms/payroll/run",
  "/hrms/payroll/tools",
  "/hrms/payroll/reports",
  "/hrms/payroll/bulk-publish",
  "/hrms/employees/bulk-import",
  "/hrms/attendance/bulk-import",
  "/hrms/workflow/admin",
  "/hrms/audit-log",
];

const regularHrDenied = new Set([
  "/hrms/company",
  "/hrms/workflow-designer",
  "/hrms/custom-fields",
  "/hrms/enterprise",
  "/hrms/settings",
  "/hrms/logs",
  "/hrms/security",
]);

const optionalDelegation: Record<Exclude<RoleName, "admin" | "hr" | "employee">, { allowed: string; forbidden: string[]; visible: string; hidden: string[] }> = {
  hr_company_admin: {
    allowed: "/hrms/company",
    forbidden: ["/hrms/workflow-designer", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/settings", "/hrms/logs", "/hrms/security"],
    visible: "Company",
    hidden: ["Workflow Designer", "Custom Fields", "Enterprise", "Settings", "Logs"],
  },
  hr_workflow_admin: {
    allowed: "/hrms/workflow-designer",
    forbidden: ["/hrms/company", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/settings", "/hrms/logs", "/hrms/security"],
    visible: "Workflow Designer",
    hidden: ["Company", "Custom Fields", "Enterprise", "Settings", "Logs"],
  },
  hr_custom_field_admin: {
    allowed: "/hrms/custom-fields",
    forbidden: ["/hrms/company", "/hrms/workflow-designer", "/hrms/enterprise", "/hrms/settings", "/hrms/logs", "/hrms/security"],
    visible: "Custom Fields",
    hidden: ["Company", "Workflow Designer", "Enterprise", "Settings", "Logs"],
  },
};

test.describe("HRMS RBAC all-role UI verification", () => {
  test("employee sees only self-service UI and forbidden direct URLs show 403", async ({ page }) => {
    await authenticate(page, "employee");
    await page.goto("/hrms/ess");
    await expectAllowed(page, "/hrms/ess");

    await expectVisibleText(page, ["My Profile", "My Attendance", "My Leave", "My Payslips", "My Documents", "My Requests"]);
    await expectNoHref(page, employeeForbiddenHrefs);

    for (const route of registeredRoutes) {
      await expectRoute(page, route, !employeeAllowed.has(route));
    }
    for (const route of criticalPatternRoutes) {
      await expectRoute(page, route, true);
    }
  });

  test("employee global search, profile menu, return home, refresh and history stay isolated", async ({ page }) => {
    await authenticate(page, "employee");
    await page.goto("/hrms/ess");

    const employeeSearch = await openGlobalSearch(page);
    await expectSearchResultVisible(employeeSearch, "ESS Profile");
    await expectSearchResultHidden(employeeSearch, ["Payroll", "Talent", "Org Chart"]);
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: /employee\.rbac/i }).click();
    await expectVisibleText(page, ["My Profile", "ESS Portal", "Change Password"]);
    await expectHiddenText(page, ["Company", "Reports", "Settings"]);
    await expectNoHref(page, ["/hrms/payroll", "/hrms/company", "/hrms/reports", "/hrms/settings"]);
    await page.keyboard.press("Escape");

    await page.goto("/hrms/payroll");
    await expect403(page, "/hrms/payroll", "Employee Self Service", "Payroll Operations");
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect403(page, "/hrms/payroll", "Employee Self Service", "Payroll Operations");
    await page.getByRole("link", { name: "Return Home" }).click();
    await expect(page).toHaveURL(/\/hrms\/ess$/);

    await page.goto("/hrms/my-payslips");
    await expectAllowed(page, "/hrms/my-payslips");
    await page.goto("/hrms/payroll");
    await expect403(page, "/hrms/payroll", "Employee Self Service", "Payroll Operations");
    await page.goBack({ waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/hrms\/my-payslips$/);
    await page.goForward({ waitUntil: "domcontentloaded" });
    await expect403(page, "/hrms/payroll", "Employee Self Service", "Payroll Operations");
  });

  test("employee mobile navigation and collapsed sidebar do not expose forbidden links", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 820 });
    await authenticate(page, "employee");
    await page.goto("/hrms/ess");

    await page.locator("header button").first().click();
    await expectVisibleText(page, ["ESS Dashboard", "My Profile", "My Attendance", "My Leave", "My Payslips", "My Documents", "My Requests"]);
    await expectNoHref(page, employeeForbiddenHrefs);
  });

  test("regular HR can use operations but cannot use system administration routes", async ({ page }) => {
    await authenticate(page, "hr");
    await page.goto("/hrms/hr-home");
    await expectAllowed(page, "/hrms/hr-home");
    await expectHrefs(page, ["/hrms/employees", "/hrms/attendance", "/hrms/attendance/shift-roster", "/hrms/leave", "/hrms/payroll", "/hrms/reports"]);
    await expectNoHref(page, ["/hrms/company", "/hrms/workflow-designer", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/security"]);

    for (const route of ["/hrms/payroll", "/hrms/attendance", "/hrms/attendance/shift-roster", "/hrms/reports"]) {
      await expectRoute(page, route, false);
    }
    for (const route of regularHrDenied) {
      await expectRoute(page, route, true);
    }

    await page.goto("/hrms/hr-home");
    const hrSearch = await openGlobalSearch(page);
    await expectSearchResultVisible(hrSearch, "Payroll");
    await expectSearchResultVisible(hrSearch, "Talent");
    await expectSearchResultHidden(hrSearch, ["Company hierarchy"]);
  });

  test("optional delegated HR roles get only their delegated system route", async ({ page }) => {
    for (const [role, rules] of Object.entries(optionalDelegation) as Array<[keyof typeof optionalDelegation, typeof optionalDelegation[keyof typeof optionalDelegation]]>) {
      await authenticate(page, role);
      await page.goto("/hrms/hr-home");
      await expectAllowed(page, "/hrms/hr-home");
      await expectHrefs(page, [rules.allowed]);
      await expectNoHref(page, rules.forbidden);

      await expectRoute(page, rules.allowed, false);
      for (const route of rules.forbidden) {
        await expectRoute(page, route, true);
      }
      await expectRoute(page, "/hrms/payroll", false);
      await expectRoute(page, "/hrms/enterprise", true);
      await expectRoute(page, "/hrms/logs", true);
    }
  });

  test("admin retains administrative access and does not see 403 on HRMS route inventory", async ({ page }) => {
    await authenticate(page, "admin");
    await page.goto("/hrms/admin-home");
    await expectAllowed(page, "/hrms/admin-home");
    await expectHrefs(page, ["/hrms/company", "/hrms/workflow-designer", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/logs", "/hrms/payroll"]);

    for (const route of registeredRoutes) {
      await expectRoute(page, route, false);
    }
    for (const route of ["/hrms/security", "/hrms/payroll/setup", "/hrms/payroll/run", "/hrms/payroll/tools", "/hrms/payroll/reports", "/hrms/payroll/bulk-publish"]) {
      await expectRoute(page, route, false);
    }
  });
});

async function authenticate(page: Page, role: RoleName) {
  const user = users[role];
  await installApiStubs(page, user);
  await page.goto("/hrms/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(async (authUser) => {
    const { useAuthStore } = await import("/src/store/authStore.ts");
    useAuthStore.setState({
      accessToken: "rbac-test-token",
      refreshToken: "rbac-test-refresh",
      user: authUser,
      isAuthenticated: true,
      isHydrated: true,
    });
    localStorage.clear();
    localStorage.setItem("hrms-auth", JSON.stringify({
      state: {
        accessToken: "rbac-test-token",
        refreshToken: "rbac-test-refresh",
        user: authUser,
        isAuthenticated: true,
      },
      version: 0,
    }));
  }, user);
}

async function installApiStubs(page: Page, user: typeof users[RoleName]) {
  await page.unroute("**/api/**").catch(() => undefined);
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    let body: unknown = method === "GET" ? [] : {};
    if (url.includes("/auth/me")) {
      body = { id: user.id, email: user.email, role: { name: user.role }, is_superuser: user.is_superuser, employee_id: user.employee_id };
    } else if (url.includes("/auth/sso/providers")) {
      body = [];
    } else if (url.includes("/notifications/unread")) {
      body = { unread: 0 };
    } else if (url.includes("/reports/global-search")) {
      body = { results: [] };
    } else if (url.includes("/payroll/payslips")) {
      body = [];
    } else if (url.includes("/workflow")) {
      body = [];
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function expectRoute(page: Page, route: string, denied: boolean) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  if (denied) {
    await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
  } else {
    await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
  }
}

async function expectAllowed(page: Page, route: string) {
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(route)}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toHaveCount(0);
}

async function expect403(page: Page, route: string, roleLabel: string, requiredPermission: string) {
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(route)}$`));
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
  await expect(page.getByText(roleLabel, { exact: false })).toBeVisible();
  await expect(page.getByText(route, { exact: false })).toBeVisible();
  await expect(page.getByText(requiredPermission, { exact: false })).toBeVisible();
}

async function openGlobalSearch(page: Page) {
  const trigger = page.locator('button:has(input[readonly][placeholder*="Search"])').first();
  if (await trigger.count()) {
    await trigger.click({ force: true });
  } else {
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  }
  const searchInput = page.getByPlaceholder("Search anything...");
  await expect(searchInput).toBeVisible();
  return searchInput.locator("..").locator("..").locator("..");
}

async function expectVisibleText(page: Page, labels: string[]) {
  for (const label of labels) {
    await expect(page.getByText(label, { exact: false }).first()).toBeVisible();
  }
}

async function expectHiddenText(page: Page, labels: string[]) {
  for (const label of labels) {
    await expect(page.getByText(label, { exact: false })).toHaveCount(0);
  }
}

async function expectNoHref(page: Page, hrefs: string[]) {
  for (const href of hrefs) {
    await expect(page.locator(`a[href="${href}"]`)).toHaveCount(0);
  }
}

async function expectHrefs(page: Page, hrefs: string[]) {
  for (const href of hrefs) {
    await expect(page.locator(`a[href="${href}"]`).first()).toBeVisible();
  }
}

async function expectSearchResultVisible(searchPanel: Locator, label: string) {
  await expect(searchPanel.getByRole("button", { name: new RegExp(escapeRegExp(label), "i") })).toBeVisible();
}

async function expectSearchResultHidden(searchPanel: Locator, labels: string[]) {
  for (const label of labels) {
    await expect(searchPanel.getByRole("button", { name: new RegExp(escapeRegExp(label), "i") })).toHaveCount(0);
  }
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
