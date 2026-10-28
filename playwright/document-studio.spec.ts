import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";

async function login(page: Page) {
  const root = process.env.STUDIO_API_URL || "http://127.0.0.1:1552";
  const response = await page.request.post(root + "/api/v1/auth/login", {
    data: { email: "admin@suiteqa.example.com", password: "SuiteQA@12345" },
  });
  expect(response.ok()).toBeTruthy();
  const tokens = await response.json();
  const profile = await page.request.get(root + "/api/v1/auth/me", {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  const raw = await profile.json();
  const user = {
    ...raw,
    role: typeof raw.role === "string" ? raw.role : raw.role?.name || "admin",
  };
  await page.addInitScript(
    ({ tokens, user }) => {
      (window as any).__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" };
      const value = JSON.stringify({
        state: {
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          user,
          isAuthenticated: true,
        },
        version: 0,
      });
      sessionStorage.setItem("hrms-auth", value);
      localStorage.setItem("hrms-auth", value);
    },
    { tokens, user },
  );
  await page.goto("/hrms/letters-certificates");
  await expect(
    page.getByRole("heading", { name: "Letters & Certificates", exact: true }),
  ).toBeVisible();
  if (
    await page
      .getByRole("button", { name: "Add starter templates" })
      .isVisible()
  ) {
    await page.getByRole("button", { name: "Add starter templates" }).click();
  }
  await expect(
    page
      .getByLabel("Template", { exact: true })
      .locator("option")
      .filter({ hasText: "Certificate of Completion" }),
  ).toHaveCount(1);
}

test("preview, issue, download and revoke a database-generated certificate", async ({
  page,
}) => {
  await login(page);
  const template = page.getByLabel("Template", { exact: true });
  const option = template
    .locator("option")
    .filter({ hasText: "Certificate of Completion" });
  await template.selectOption((await option.getAttribute("value")) as string);
  await page
    .getByLabel("Recipient", { exact: true })
    .selectOption({ label: "Ananya Rao · STUDIO-001" });
  await page
    .getByLabel("Program or achievement *", { exact: true })
    .fill(`Software Engineering ${test.info().project.name}`);
  await page.getByLabel("Start date *", { exact: true }).fill("2026-06-01");
  await page.getByLabel("End date *", { exact: true }).fill("2026-09-30");
  await page
    .getByLabel("Remarks", { exact: true })
    .fill("Completed assigned projects with dedication and care.");
  await expect(
    page.getByRole("button", { name: "Issue & download" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Preview PDF" }).click();
  await expect(
    page.getByRole("img", { name: "PDF page 1", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Issue & download" }),
  ).toBeEnabled();
  await expect(
    page
      .locator("p.sr-only")
      .filter({ hasText: "This certificate is presented to" }),
  ).toContainText("Ananya Rao");
  await page
    .getByRole("img", { name: "PDF page 1", exact: true })
    .screenshot({
      path: `.tmp/document-studio-pdf-${test.info().project.name}.png`,
    });
  await page.screenshot({
    path: `.tmp/document-studio-preview-${test.info().project.name}.png`,
    fullPage: true,
  });
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Issue & download" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toMatch(/^DOC-2026-.*\.pdf$/);
  await page.getByRole("tab", { name: "Issued", exact: true }).click();
  const article = page
    .locator("article")
    .filter({ hasText: download.suggestedFilename().replace(".pdf", "") });
  await expect(article).toBeVisible();
  await article.getByRole("button", { name: "Revoke", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic QA certificate revoked after verification");
  await page
    .getByRole("button", { name: "Revoke document", exact: true })
    .click();
  await expect(article).toContainText("Revoked");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("edit reusable templates and letterheads without changing issued records", async ({
  page,
}) => {
  const name = `Custom Letter ${test.info().project.name} ${Date.now()}`;
  await login(page);
  await page.getByRole("tab", { name: "Templates", exact: true }).click();
  await page.getByRole("button", { name: "New template", exact: true }).click();
  await page.getByLabel("Template name", { exact: true }).fill(name);
  await page
    .getByLabel("Document title (placeholders supported)", { exact: true })
    .fill("Internship Letter");
  await page
    .getByLabel("Body · plain text and {{group.field}} placeholders", {
      exact: true,
    })
    .fill(
      "This letter confirms the participation of {{recipient.name}} at {{company.name}}.",
    );
  await page
    .getByRole("button", { name: "Save template", exact: true })
    .click();
  await expect(page.getByRole("button", { name, exact: false })).toBeVisible();
  await page.getByRole("tab", { name: "Letterheads", exact: true }).click();
  await page
    .getByRole("button", { name: "Company letterhead", exact: false })
    .click();
  await page
    .getByLabel("Signatory name", { exact: true })
    .fill("HR Department");
  await page
    .getByRole("button", { name: "Save letterhead", exact: true })
    .click();
  await expect(
    page.getByText("Select a letterhead to configure your official branding."),
  ).toBeVisible();
  await page.screenshot({
    path: `.tmp/document-studio-letterheads-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
