import { loginDestination } from "../frontend/src/lib/login";
import { test, expect } from "../frontend/node_modules/playwright/test";

test("one company-branded login URL for every module", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Business Suite", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("QA Alpha", { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByText("AI HRMS", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Enter your HRMS credentials")).toHaveCount(0);
  await page.screenshot({
    path: "../docs/qa/business-suite-login.png",
    fullPage: true,
  });
  for (const home of ["hrms", "crm", "pms", "srm", "fam"]) {
    await page.goto(`/${home}/login`);
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Business Suite", exact: true }),
    ).toBeVisible();
  }
  await page.goto("/power-apps/approvals?environment=development");
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/login?next=%2Fhrms");
  await expect(page).toHaveURL(/\/login$/);
  const payload = page.waitForRequest(
    (r) => r.url().endsWith("/auth/login") && r.method() === "POST",
  );
  await page.getByLabel("Email address").fill("missing@qa.invalid");
  await page.getByLabel("Password", { exact: true }).fill("Incorrect@123456");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  expect((await payload).postDataJSON()).not.toHaveProperty("module");
});

test("login redirects reject external hosts and normalized login loops", () => {
  expect(loginDestination(null)).toBe("/dashboard");
  for (const path of [
    "https://evil.invalid",
    "//evil.invalid",
    "/\\evil.invalid",
    "/crm/../../login",
    "/crm/login",
  ])
    expect(loginDestination(path)).toBe("/dashboard");
  expect(
    loginDestination("/power-apps/approvals?environment=development"),
  ).toBe("/dashboard");
});

test("authorized application dashboard supports search, navigation and mobile", async ({
  page,
}) => {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const manifest = JSON.parse(
    await fs.readFile(
      path.resolve(__dirname, "../.tmp/power-approvals-live-session.json"),
      "utf8",
    ),
  );
  const actor = manifest.users[0];
  const access = await (
    await page.request.get(manifest.api + "/access/me", {
      headers: { Authorization: `Bearer ${actor.token}` },
    })
  ).json();
  await page.addInitScript(
    ({ actor, access }) => {
      sessionStorage.setItem(
        "hrms-auth",
        JSON.stringify({
          state: {
            accessToken: actor.token,
            refreshToken: "isolated-browser-session",
            isAuthenticated: true,
            user: {
              id: actor.id,
              email: actor.email,
              role: actor.role,
              is_superuser: false,
              access,
            },
          },
          version: 0,
        }),
      );
    },
    { actor, access },
  );
  await page.goto("/");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Your work starts here." }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Power Apps", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".md-grid a[href*='login']")).toHaveCount(0);
  await page.screenshot({
    path: "../docs/qa/module-dashboard.png",
    fullPage: true,
  });
  await page
    .getByRole("textbox", { name: "Search your modules" })
    .fill("Power Apps");
  await expect(page.locator(".md-card")).toHaveCount(1);
  await page
    .getByRole("textbox", { name: "Search your modules" })
    .fill("no matching application");
  await expect(
    page.getByRole("heading", { name: "No matching modules" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Show my applications" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/qa/module-dashboard-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Open Power Apps", exact: true })
    .click();
  await expect(page).toHaveURL(/\/power-apps$/);
});
