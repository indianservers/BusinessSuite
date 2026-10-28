import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";

const apiRoot = "http://127.0.0.1:1553/api/v1";
async function login(page: Page) {
  const response = await page.request.post(apiRoot + "/auth/login", {
    data: { email: "admin@suiteqa.example.com", password: "SuiteQA@12345" },
  });
  expect(response.ok()).toBeTruthy();
  const tokens = await response.json();
  const raw = await (
    await page.request.get(apiRoot + "/auth/me", {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    })
  ).json();
  const user = {
    ...raw,
    role: typeof raw.role === "string" ? raw.role : raw.role?.name || "admin",
  };
  await page.addInitScript(
    ({ tokens, user }) => {
      (window as any).__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" };
      const state = JSON.stringify({
        state: {
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          user,
          isAuthenticated: true,
        },
        version: 0,
      });
      sessionStorage.setItem("hrms-auth", state);
      localStorage.setItem("hrms-auth", state);
    },
    { tokens, user },
  );
  return { Authorization: `Bearer ${tokens.access_token}` };
}

test("create level variants, publish a weekly pack, and extend only a selected deadline", async ({
  page,
}) => {
  const headers = await login(page);
  await page.goto("/pms/batch-tasks");
  await page
    .getByLabel("Program PMS project", { exact: true })
    .selectOption({ label: "Intern Learning Lab" });
  await page
    .getByRole("button", { name: "New task pack", exact: true })
    .click();
  const name = `QA pack ${test.info().project.name} ${Date.now()}`;
  await page.getByLabel("Pack name", { exact: true }).fill(name);
  await page
    .getByLabel("Step 1 title", { exact: true })
    .fill(`Beginner discovery ${name}`);
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await page
    .getByLabel("Step 1 title", { exact: true })
    .fill(`Advanced discovery ${name}`);
  await page
    .getByRole("button", { name: "Add weekly step", exact: true })
    .click();
  await page.getByRole("checkbox", { name: "week_1", exact: true }).check();
  await page
    .getByRole("button", { name: "Save task pack", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Task pack saved." }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Assign pack", exact: true }).click();
  const saved = page.getByLabel("Saved task pack", { exact: true });
  await saved.selectOption(
    (await saved
      .locator("option")
      .filter({ hasText: name })
      .getAttribute("value")) as string,
  );
  await page
    .getByLabel("Task pack batch", { exact: true })
    .selectOption({ label: "Intern QA Batch" });
  await page
    .getByLabel("Pack reviewer", { exact: true })
    .selectOption({ label: "admin@suiteqa.example.com" });
  await page
    .getByRole("button", { name: "Select batch as beginner", exact: true })
    .click();
  await page
    .getByLabel("Skill level for Rahul Test", { exact: true })
    .selectOption("advanced");
  await expect(
    page.getByRole("button", { name: "Publish task pack", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Preview task pack", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Preview: 4 individual assignments · 2 interns",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Publish task pack", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Published 4 assignments" }),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Extend deadlines", exact: true })
    .click();
  const checkbox = page.getByRole("checkbox", {
    name: `Extend Beginner discovery ${name} for Ananya Test`,
    exact: true,
  });
  await checkbox.check();
  const newDate = new Date();
  newDate.setDate(newDate.getDate() + 21);
  await page
    .getByLabel("New deadline", { exact: true })
    .fill(newDate.toLocaleDateString("en-CA"));
  await page
    .getByLabel("Extension reason", { exact: true })
    .fill("Additional time for the learning assessment");
  await page
    .getByRole("button", { name: "Preview extension", exact: true })
    .click();
  await expect(
    page.getByText(
      `1 assignments will change to ${newDate.toLocaleDateString("en-CA")}`,
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Extend selected deadlines", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Extended 1 deadlines" }),
  ).toBeVisible();
  await expect(checkbox.locator("xpath=ancestor::tr")).toContainText(
    newDate.toLocaleDateString("en-CA"),
  );
  const projectId = await page
    .getByLabel("Program PMS project", { exact: true })
    .inputValue();
  const history = await (
    await page.request.get(
      `${apiRoot}/interns-hub/management/learning/deadlines/history?project_id=${projectId}`,
      { headers },
    )
  ).json();
  expect(history.items[0].count).toBe(1);
  await page
    .locator('section[aria-label="Intern task programs"]')
    .screenshot({
      path: `.tmp/intern-task-programs-${test.info().project.name}.png`,
    });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("reviewers score each task pack rubric criterion", async ({ page }) => {
  const headers = await login(page);
  const options = await (
    await page.request.get(apiRoot + "/interns-hub/management/options", {
      headers,
    })
  ).json();
  const projectId = options.projects.find(
    (p: any) => p.name === "Intern Learning Lab",
  ).id;
  const packs = await (
    await page.request.get(
      `${apiRoot}/interns-hub/management/learning/packs?project_id=${projectId}`,
      { headers },
    )
  ).json();
  const pack = packs[packs.length - 1];
  expect(pack).toBeTruthy();
  const internLogin = await page.request.post(apiRoot + "/auth/login", {
    data: {
      email: "program1@suiteqa.example.com",
      password: "SuiteQA@12345",
      module: "interns_hub",
    },
  });
  expect(internLogin.ok(), await internLogin.text()).toBeTruthy();
  const internHeaders = {
    Authorization: `Bearer ${(await internLogin.json()).access_token}`,
  };
  const mineResponse = await page.request.get(apiRoot + "/interns-hub/tasks", {
    headers: internHeaders,
  });
  expect(mineResponse.ok(), await mineResponse.text()).toBeTruthy();
  const mine = await mineResponse.json();
  const first = mine.find(
    (t: any) =>
      t.title.startsWith("Beginner discovery") &&
      !t.blocked_by.length &&
      t.status === "Pending",
  );
  expect(first).toBeTruthy();
  const submitted = await page.request.post(
    `${apiRoot}/interns-hub/tasks/${first.id}/submissions`,
    {
      headers: internHeaders,
      data: { notes: "Completed the task with evidence", confirmed: true },
    },
  );
  expect(submitted.ok()).toBeTruthy();
  await page.goto("/hrms/interns/reviews?tab=Pending%20Reviews");
  const row = page.getByRole("row").filter({ hasText: first.title });
  await row.getByRole("button").first().click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("group", { name: /Task pack evaluation rubric/ }),
  ).toBeVisible();
  await dialog
    .getByLabel("Rubric score: Correctness", { exact: true })
    .fill("45");
  await dialog.getByLabel("Rubric score: Quality", { exact: true }).fill("25");
  await dialog
    .getByLabel("Rubric score: Explanation", { exact: true })
    .fill("15");
  await expect(
    dialog.getByLabel("Score (maximum 100)", { exact: true }),
  ).toHaveValue("85");
  await dialog
    .locator('[contenteditable="true"]')
    .first()
    .fill("Meets the requirements and includes clear evidence");
  await dialog
    .getByRole("checkbox", { name: /I have inspected this version/ })
    .check();
  await expect(
    dialog.getByRole("button", { name: "Save PMS Review", exact: true }),
  ).toBeEnabled();
  await dialog
    .getByRole("button", { name: "Save PMS Review", exact: true })
    .click();
  await expect(
    page.getByText("PMS review recorded", { exact: true }),
  ).toBeVisible();
});
