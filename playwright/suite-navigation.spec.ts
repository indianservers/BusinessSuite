import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";
import fs from "node:fs";
import path from "node:path";

const password = "SuiteQA@12345";
const api = "http://127.0.0.1:1551/api/v1";
async function signIn(
  page: Page,
  next = "/dashboard",
  email = "admin@suiteqa.example.com",
) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login|\/continue/);
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}
async function openSidebar(page: Page) {
  const trigger = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  if ((page.viewportSize()?.width || 0) < 1024) await trigger.click();
  return page.getByRole("navigation", {
    name: "Module navigation",
    exact: true,
  });
}
async function snapshot(page: Page, name: string, project: string) {
  const target = path.resolve(
    __dirname,
    `../docs/qa/suite-navigation-${name}-${project}.png`,
  );
  fs.mkdirSync(path.dirname(target), { recursive: true });
  await expect(page.locator(".async-progress")).toHaveCount(0, {
    timeout: 15_000,
  });
  await page.screenshot({ path: target, fullPage: true });
}
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  // Assert unexpected React/runtime errors, rather than swallowing them.
  test.info().annotations.push({
    type: "runtime-errors",
    description: "Checked after each journey",
  });
  (page as Page & { suiteErrors?: string[] }).suiteErrors = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as Page & { suiteErrors?: string[] }).suiteErrors || []).toEqual(
    [],
  );
});

test("public entry, application filtering and contextual login", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your work starts here." }),
  ).toBeVisible();
  await expect(page.locator(".md-card")).toHaveCount(6);
  await page.keyboard.press("Control+k");
  await expect(
    page.getByLabel("Search applications", { exact: true }),
  ).toBeFocused();
  await page.getByLabel("Search applications", { exact: true }).fill("payroll");
  await expect(page.locator(".md-card")).toHaveCount(1);
  await page.getByLabel("Search applications", { exact: true }).fill("");
  await noOverflow(page);
  await snapshot(page, "prelogin", info.project.name);
  await page
    .getByRole("link", { name: "Sign in to VyaparaCRM", exact: true })
    .click();
  await expect(
    page.getByText("Continue to VyaparaCRM after signing in."),
  ).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Keep me signed in" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Continue with Google" }),
  ).toHaveCount(0);
  await noOverflow(page);
  await snapshot(page, "login", info.project.name);
});

test("persistent credential errors, password visibility and field associations", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("#email")).toHaveAttribute("aria-invalid", "true");
  await page
    .getByLabel("Email address", { exact: true })
    .fill("admin@suiteqa.example.com");
  await page.getByLabel("Password", { exact: true }).fill("Incorrect@123");
  await page
    .getByRole("button", { name: "Show password", exact: true })
    .click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("#login-error")).toBeVisible();
  await expect(page.getByLabel("Email address", { exact: true })).toHaveValue(
    "admin@suiteqa.example.com",
  );
  await expect(page.locator("#login-error")).toBeFocused();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "aria-describedby",
    "login-error",
  );
  await noOverflow(page);
});

test("password recovery confirmation and reset back navigation", async ({
  page,
}) => {
  await page.goto("/login");
  await page
    .getByLabel("Email address", { exact: true })
    .fill("admin@suiteqa.example.com");
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await expect(page.getByLabel("Email address", { exact: true })).toHaveValue(
    "admin@suiteqa.example.com",
  );
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(
    page.getByRole("heading", { name: "Check your inbox" }),
  ).toBeVisible();
  await expect(
    page.getByText(/If an account exists for admin@suiteqa.example.com/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Try another email" }).click();
  await expect(
    page.getByRole("heading", { name: "Recover access" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Back to login", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Sign in to Business Suite" }),
  ).toBeVisible();
  await page.goto("/reset-password?token=unused-back-navigation-token");
  await expect(
    page.getByRole("heading", { name: "Reset password" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Back to login", exact: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await noOverflow(page);
});

test("dashboard favorites, real badges, compact view and profile menu", async ({
  page,
}, info) => {
  await signIn(page);
  await expect(page.locator(".md-card")).toHaveCount(6);
  await expect(page.getByText("Featured", { exact: true })).toHaveCount(0);
  await expect(
    page
      .getByRole("article", { name: "AI HRMS", exact: true })
      .locator(".md-icon"),
  ).toHaveCSS("color", "rgb(0, 85, 255)");
  await page.getByLabel("Search your modules", { exact: true }).fill("payroll");
  await expect(page.locator(".md-card")).toHaveCount(1);
  await page.getByRole("button", { name: "Clear module search" }).click();
  await page
    .getByRole("button", { name: "Pin VyaparaCRM", exact: true })
    .click();
  await expect(page.locator(".md-card").first()).toHaveAttribute(
    "aria-label",
    "VyaparaCRM",
  );
  await page.getByRole("checkbox", { name: "Favorites only" }).check();
  await expect(page.locator(".md-card")).toHaveCount(1);
  await page.getByRole("checkbox", { name: "Favorites only" }).uncheck();
  await page.getByRole("checkbox", { name: "Compact view" }).check();
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: "Compact view" }),
  ).toBeChecked();
  await expect(
    page.getByRole("button", { name: "Unpin VyaparaCRM" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("checkbox", { name: "Compact view" }).uncheck();
  await page.getByRole("button", { name: "Open account menu" }).click();
  await expect(
    page.getByRole("menuitem", { name: "My profile", exact: true }),
  ).toBeVisible();
  await page.getByRole("menuitem", { name: "Account settings" }).click();
  await expect(page).toHaveURL(/\/account#security$/);
  await expect(
    page.getByRole("heading", { name: "Account settings" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "All applications", exact: true })
    .click();
  await noOverflow(page);
  await snapshot(page, "dashboard", info.project.name);
});

test("feature links, recent pages, breadcrumbs, groups and mobile drawer", async ({
  page,
}, info) => {
  await signIn(page);
  await page
    .getByRole("link", { name: "VyaparaCRM: Customers", exact: true })
    .click();
  await expect(page).toHaveURL(/\/crm\/contacts$/);
  const breadcrumbs = page.getByRole("navigation", {
    name: "Breadcrumb",
    exact: true,
  });
  await expect(
    breadcrumbs.getByRole("link", { name: "All applications", exact: true }),
  ).toBeVisible();
  await expect(breadcrumbs.locator('[aria-current="page"]')).toContainText(
    "Contacts",
  );
  await noOverflow(page);
  await snapshot(page, "module", info.project.name);
  const nav = await openSidebar(page);
  await expect(
    nav.getByRole("button", { expanded: true }).first(),
  ).toBeVisible();
  const firstGroup = nav.getByRole("button").first();
  const groupName = await firstGroup.innerText();
  await firstGroup.click();
  await expect(firstGroup).toHaveAttribute("aria-expanded", "false");
  await page.reload();
  await openSidebar(page);
  await expect(
    page
      .getByRole("navigation", { name: "Module navigation", exact: true })
      .getByRole("button", { name: groupName, exact: true }),
  ).toHaveAttribute("aria-expanded", "false");
  if (info.project.name === "mobile") {
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Open navigation", exact: true }),
    ).toBeFocused();
    await openSidebar(page);
  }
  await page
    .locator(".suite-sidebar")
    .getByRole("link", { name: "All applications", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Continue working" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Resume", exact: true }),
  ).toHaveAttribute("href", "/crm/contacts");
  await page.getByRole("button", { name: "Clear recent pages" }).click();
  await expect(
    page.getByRole("region", { name: "Continue working" }),
  ).toHaveCount(0);
  await noOverflow(page);
});

test("shared command search and module switching include Power Apps", async ({
  page,
}, info) => {
  await signIn(page, "/crm/contacts");
  await openSidebar(page);
  const switcher = page.getByLabel("Switch business module", { exact: true });
  await expect(switcher.locator('option[value="/power-apps"]')).toHaveCount(1);
  await switcher.selectOption("/hrms");
  await expect(page).toHaveURL(/\/hrms$/);
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Search Business Suite" }),
  ).toHaveCount(1);
  await page
    .getByRole("combobox", { name: "Search authorized applications and pages" })
    .fill("Power Apps");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/power-apps$/);
  await expect(
    page.getByRole("navigation", { name: "Business Suite navigation" }),
  ).toBeVisible();
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Search Business Suite" }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Close search" }).click();
  await page
    .getByRole("link", { name: "All applications", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await noOverflow(page);
  await snapshot(page, "postlogin", info.project.name);
});

test("company switching uses names and isolates favorites, recents and notifications", async ({
  page,
}) => {
  await signIn(page);
  await page.getByRole("button", { name: "Pin AI HRMS", exact: true }).click();
  await expect(
    page.getByLabel("Current company", { exact: true }),
  ).toContainText("Indian Servers");
  await page.getByLabel("Current company", { exact: true }).selectOption("2");
  await expect(page.getByLabel("Current company", { exact: true })).toHaveValue(
    "2",
  );
  await expect(
    page.getByRole("button", { name: "Pin AI HRMS", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /^Notifications/ }).click();
  await expect(
    page.getByText("Other company private update", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Review your contacts", { exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("Current company", { exact: true }).selectOption("1");
  await expect(
    page.getByRole("button", { name: "Unpin AI HRMS", exact: true }),
  ).toBeVisible();
  await noOverflow(page);
});

test("permission-aware inbox and unauthorized return paths", async ({
  page,
}) => {
  await signIn(page, "/fam/ledgers", "employee@suiteqa.example.com");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("status").filter({ hasText: "That page isn't available" }),
  ).toBeVisible();
  await expect(page.locator(".md-card")).toHaveCount(1);
  await expect(
    page.getByText("Recommended for your role", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /^Notifications/ }).click();
  await expect(
    page.getByText("Profile update available", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Finance update", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByText("Review your contacts", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Other company private update", { exact: true }),
  ).toHaveCount(0);
  await noOverflow(page);
});

test("notification reads update suite badges and link to real destinations", async ({
  page,
}) => {
  await signIn(page);
  const token = await page.evaluate(
    () => JSON.parse(sessionStorage.getItem("hrms-auth")!).state.accessToken,
  );
  const me = await page.request.get(`${api}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const user = await me.json();
  const title = `Navigation update ${Date.now()}`;
  const created = await page.request.post(`${api}/notifications/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      user_id: user.id,
      company_id: 1,
      module: "crm",
      title,
      message: "Open the contacts page.",
      action_url: "/crm/contacts",
      channels: ["in_app"],
    },
  });
  expect(created.ok()).toBe(true);
  await page.reload();
  await expect(
    page
      .getByRole("article", { name: "VyaparaCRM", exact: true })
      .getByRole("link", { name: /unread update/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: /^Notifications/ }).click();
  const notification = page
    .locator(".suite-notification-list article")
    .filter({ hasText: title });
  await expect(notification).toBeVisible();
  await expect(
    notification.getByRole("link", { name: "Open update" }),
  ).toHaveAttribute("href", "/crm/contacts");
  await notification
    .getByRole("button", { name: "Mark read", exact: true })
    .click();
  await expect(notification.getByText("New", { exact: true })).toHaveCount(0);
  await page
    .getByLabel("Filter notifications by application")
    .selectOption("hrms");
  await expect(page.getByText(title, { exact: true })).toHaveCount(0);
  await noOverflow(page);
});

test("safe deep links, legacy login and logout cache cleanup", async ({
  page,
}) => {
  await page.goto("/crm/contacts?view=all#top");
  await expect(page).toHaveURL(/\/login\?next=/);
  await page
    .getByLabel("Email address", { exact: true })
    .fill("admin@suiteqa.example.com");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("checkbox", { name: "Keep me signed in" }).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/crm\/contacts\?view=all#top$/);
  await page.goto("/dashboard");
  await page.route("**/api/v1/auth/logout", (route) => route.abort());
  await page.getByRole("button", { name: "Open account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(
    await page.evaluate(
      () => JSON.parse(sessionStorage.getItem("hrms-auth")!).state.user,
    ),
  ).toBeNull();
  expect(
    await page.evaluate(() => localStorage.getItem("suite-remembered-auth")),
  ).toContain('"isAuthenticated":false');
  await signIn(page, "//outside.invalid/");
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/pms/login?next=%2Fcrm%2Fcontacts");
  await expect(page).toHaveURL(/\/crm\/contacts$/);
});

test("dashboard access loading and failure show a single recoverable state", async ({
  page,
}) => {
  await signIn(page);
  let fail = true;
  await page.route("**/api/v1/access/me", async (route) => {
    if (!fail) return route.continue();
    await new Promise((resolve) => setTimeout(resolve, 300));
    return route.fulfill({ status: 503, json: { detail: "QA unavailable" } });
  });
  await page.reload();
  await expect(page.locator(".suite-dashboard-skeleton")).toHaveCount(6);
  await expect(
    page.getByText("No applications assigned yet", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText(/available modules/)).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "We couldn't load your applications." }),
  ).toBeVisible();
  await expect(
    page.getByText("No applications assigned yet", { exact: true }),
  ).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.locator(".md-card")).toHaveCount(6);
});

test("reset success returns to sign in and account settings change the password", async ({
  page,
}, info) => {
  const device = info.project.name;
  const nextPassword = "SuiteQA@Reset54321";
  await page.goto(`/reset-password?token=suite-qa-reset-${device}-token`);
  await page.getByLabel("New password", { exact: true }).fill(nextPassword);
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("Mismatch@54321");
  await page
    .getByRole("button", { name: "Reset password", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Passwords do not match.",
  );
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill(nextPassword);
  await page
    .getByRole("button", { name: "Reset password", exact: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("status").filter({ hasText: "Password reset." }),
  ).toBeVisible();
  await page
    .getByLabel("Email address", { exact: true })
    .fill(`reset-${device}@suiteqa.example.com`);
  await page.getByLabel("Password", { exact: true }).fill(nextPassword);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("button", { name: "Open account menu" }).click();
  await page
    .getByRole("menuitem", { name: "Account settings", exact: true })
    .click();
  await page.getByLabel("Current password", { exact: true }).fill(nextPassword);
  await page
    .getByLabel("New password", { exact: true })
    .fill("SuiteQA@Changed54321");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("SuiteQA@Changed54321");
  await page
    .getByRole("button", { name: "Change password", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Your password has been changed." }),
  ).toBeVisible();
  await noOverflow(page);
});

test("company sign-in options prioritize the email domain and preserve context", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/sso/providers/active", (route) =>
    route.fulfill({
      json: [
        {
          id: 8,
          name: "Partner account",
          provider_type: "oidc",
          domain_hint: "partner.example.com",
          button_label: "Continue with partner",
        },
        {
          id: 9,
          name: "Company account",
          provider_type: "oidc",
          domain_hint: "suiteqa.example.com",
          button_label: "Continue with company",
        },
      ],
    }),
  );
  await page.goto("/login?next=%2Fcrm%2Fcontacts");
  await page
    .getByLabel("Email address", { exact: true })
    .fill("admin@suiteqa.example.com");
  await expect(
    page.locator(".suite-login-providers button").first(),
  ).toHaveText("Continue with company");
  await expect(
    page.getByText("Your organization uses Continue with company.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Continue to VyaparaCRM after signing in.", { exact: true }),
  ).toBeVisible();
  await noOverflow(page);
});
