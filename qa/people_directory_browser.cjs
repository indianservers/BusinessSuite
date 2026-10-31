// Disposable loopback-only QA: never point this script at a deployed service.
const fs = require("fs");
fs.mkdirSync(".local", { recursive: true });
const {
  chromium,
  expect: raw,
} = require("../frontend/node_modules/playwright/test");
const expect = raw.configure({ timeout: 45000 });
(async () => {
  const r = await fetch("http://127.0.0.1:1552/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "admin@suiteqa.example.com",
      password: "SuiteQA@12345",
    }),
  });
  if (!r.ok) throw Error("Login " + r.status);
  const login = await r.json();
  const access = await (
    await fetch("http://127.0.0.1:1552/api/v1/access/me", {
      headers: { Authorization: "Bearer " + login.access_token },
    })
  ).json();
  const browser = await chromium.launch({ headless: true });
  globalThis.browser = browser;
  const context = await browser.newContext({
    viewport: { width: 1672, height: 941 },
  });
  await context.addInitScript(
    ({ login, access }) =>
      sessionStorage.setItem(
        "hrms-auth",
        JSON.stringify({
          state: {
            accessToken: login.access_token,
            refreshToken: login.refresh_token,
            isAuthenticated: true,
            user: {
              id: login.user_id,
              email: login.email,
              role: "admin",
              is_superuser: true,
              access,
            },
          },
          version: 0,
        }),
      ),
    { login, access },
  );
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", async (r) => {
    if (r.status() >= 400 && r.url().includes("people-workspace"))
      console.error("HTTP", r.status(), (await r.text()).slice(0, 300));
  });

  await page.goto("http://127.0.0.1:5187/pms/people");
  await expect(page.locator(".pd-person-card")).toHaveCount(5);
  await page.getByLabel("Search people directory").fill("Sneha");
  await expect(page.locator(".pd-person-card")).toHaveCount(1);
  await page.getByLabel("List view").click();
  await expect(page.locator(".pd-person-card")).toHaveCount(1);
  await page.getByLabel("Card view").click();
  await page.getByRole("button", { name: "More filters", exact: true }).click();
  await page.getByLabel("Filter teams", { exact: true }).selectOption("1");
  await page.getByLabel("Filter batches", { exact: true }).selectOption("1");
  await expect(page.locator(".pd-person-card")).toHaveCount(1);
  await page.getByLabel("Saved people views").selectOption("save");
  await page.getByLabel("People view name").fill("My intern team");
  await page.getByRole("button", { name: "Save view", exact: true }).click();
  await page.locator(".pd-person-identity a").first().click();
  await expect(page).toHaveURL(/people\/2/);
  await expect(
    page.getByRole("heading", { name: "Sneha Patel", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "tasks", exact: true }).click();
  await expect(page).toHaveURL(/tab=tasks/);
  await page
    .locator(".pd-profile")
    .getByRole("link", { name: "People directory", exact: true })
    .click();
  await expect(page.getByLabel("Search people directory")).toHaveValue("Sneha");
  await expect(page.locator(".pd-person-card")).toHaveCount(1);
  console.log(
    "PASS combined filters, card/list view, saved view, profile and return state",
  );
  await page.goto("http://127.0.0.1:5187/pms/people");
  await expect(page.locator(".pd-person-card")).toHaveCount(5);
  await page.getByRole("button", { name: "New team", exact: true }).click();
  await page
    .getByLabel("Team name", { exact: true })
    .fill("Directory QA Team " + Date.now());
  await page
    .getByLabel("Team alias", { exact: true })
    .fill("directory-qa-" + Date.now());
  await page
    .getByLabel("Team description")
    .fill("Created through the real directory workflow");
  await page.getByLabel("Team member employee@suiteqa.example.com").check();
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".pd-right-panel")).toContainText(
    "Directory QA Team",
  );
  console.log("PASS create team with selected existing member");
  await page
    .locator(".pd-person-card")
    .filter({ hasText: "Sneha Patel" })
    .getByRole("button", { name: "Assign task", exact: true })
    .click();
  await expect(page).toHaveURL(/tasks\/new\?people=2/);
  await expect(page.getByLabel("Task Title", { exact: true })).toBeVisible();
  await expect(page.locator(".ts-chips").first()).toContainText("Sneha Patel");
  console.log("PASS direct full-page person assignment");
  await page.goto("http://127.0.0.1:5187/pms/tasks/new?batches=1");
  await expect(
    page.getByRole("button", { name: /^Interns Batch Assign/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("checkbox", { name: /Interns/ })).toBeChecked();
  await page.getByLabel("Execution mode").selectOption("individual");
  await page
    .getByLabel("Task Title", { exact: true })
    .fill("Directory individual browser QA");
  await page.getByLabel("Due date", { exact: true }).fill("2026-11-15");
  await page.getByLabel("Select reviewer", { exact: true }).click();
  await page.getByRole("checkbox", { name: /Rahul Sharma/ }).check();
  await page.getByLabel("Select reviewer", { exact: true }).click();
  await page
    .getByRole("button", { name: "Create Task", exact: true })
    .first()
    .click();
  await expect(page.locator(".ts-job")).toContainText("Completed: 2 of 2");
  console.log("PASS individual batch distribution with reviewer and progress");
  await page.goto("http://127.0.0.1:5187/pms/people");
  await expect(page.locator(".pd-person-card")).toHaveCount(5);
  await expect(page.locator(".async-progress")).toHaveCount(0);
  await page.screenshot({
    path: ".local/people-directory-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  for (const [label, width, height] of [
    ["tablet", 1024, 768],
    ["mobile", 390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    await expect
      .poll(() =>
        page
          .locator("#suite-main")
          .evaluate((el) => el.getBoundingClientRect().width),
      )
      .toBeGreaterThan(width < 700 ? width - 10 : width - 270);
    await page.screenshot({
      path: ".local/people-directory-" + label + ".png",
      fullPage: true,
      animations: "disabled",
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .locator(".pd-mobile-tabs")
      .getByRole("button", { name: "teams", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "New team", exact: true }),
    ).toBeVisible();
    await page
      .locator(".pd-mobile-tabs")
      .getByRole("button", { name: "people", exact: true })
      .click();
    console.log("PASS " + label + " layout and group navigation");
  }

  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto(
    "http://127.0.0.1:5187/pms/people?q=nonexistent-directory-person",
  );
  await expect(
    page.getByRole("heading", { name: "No people match these filters" }),
  ).toBeVisible();
  console.log("PASS empty results");
  await page.route(
    "**/api/v1/project-management/people-workspace/people?**",
    (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "QA simulated directory outage" }),
      }),
  );
  await page.goto("http://127.0.0.1:5187/pms/people?q=retry-check");
  await expect(page.locator(".pd-alert")).toBeVisible();
  await page.unroute("**/api/v1/project-management/people-workspace/people?**");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No people match these filters" }),
  ).toBeVisible();
  console.log("PASS API failure and retry");
  await page.route(
    "**/api/v1/project-management/people-workspace/people?**",
    async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 900));
      await route.continue();
    },
  );
  await page.goto("http://127.0.0.1:5187/pms/people?q=Rahul");
  await expect(page.getByLabel("Loading directory")).toBeVisible();
  await expect(page.locator(".pd-person-card")).toHaveCount(1);
  await page.unroute("**/api/v1/project-management/people-workspace/people?**");
  console.log("PASS slow response loading state");
  await page.goto("http://127.0.0.1:5187/pms/people");
  await expect(page.locator(".pd-person-card")).toHaveCount(5);
  const exportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export", exact: true }).click();
  expect((await exportDownload).suggestedFilename()).toBe(
    "people-directory.csv",
  );
  await page.getByRole("button", { name: "Import", exact: true }).click();
  const importDialog = page.getByRole("dialog", {
    name: "Import people",
    exact: true,
  });
  await page
    .getByLabel("Import people CSV")
    .setInputFiles({
      name: "people.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "Name,Email\nA,qa-invite@example.com\nDuplicate,qa-invite@example.com\nMissing,\n",
      ),
    });
  await expect(importDialog).toContainText("1 valid");
  await expect(importDialog).toContainText("2 row errors");
  await expect(importDialog).toContainText("Duplicate row");
  await page
    .getByRole("button", { name: "Send valid invitations", exact: true })
    .click();
  await expect(importDialog).toContainText(/invited/i);
  await page.getByLabel("Close dialog").click();
  console.log(
    "PASS scoped export and import preview, duplicate/empty row validation and invitation",
  );
  await page.getByRole("button",{name:"Add Person",exact:true}).click();await expect(page.getByRole("dialog",{name:"Create login account",exact:true})).toBeVisible();console.log("PASS existing account creation workflow");
  await page.goto("http://127.0.0.1:5187/pms/people");await expect(page.locator(".pd-person-card")).toHaveCount(5);await page.getByRole("button",{name:"New batch",exact:true}).click();await expect(page.getByRole("dialog",{name:"Create Batch",exact:true})).toBeVisible();console.log("PASS existing InternHub batch creation workflow");
  if (errors.length) throw Error(errors.join(";"));
  await browser.close();
})().catch(async (e) => {
  console.error(e);
  await globalThis.browser?.close();
  process.exit(1);
});
