import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
async function setup(page: Page, index = 0) {
  const m = JSON.parse(
    await fs.readFile(
      path.resolve(__dirname, "../.tmp/power-approvals-live-session.json"),
      "utf8",
    ),
  );
  const actor = m.users[index],
    headers = { Authorization: `Bearer ${actor.token}` };
  const access = await (
    await page.request.get(m.api + "/access/me", { headers })
  ).json();
  await page.addInitScript(
    ({ actor, access }) => {
      window.__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" };
      sessionStorage.setItem(
        "hrms-auth",
        JSON.stringify({
          state: {
            accessToken: actor.token,
            refreshToken: null,
            user: {
              id: actor.id,
              email: actor.email,
              name: "Approval QA",
              role: actor.role,
              primary_role: actor.role,
              is_superuser: false,
              access,
            },
            isAuthenticated: true,
          },
          version: 0,
        }),
      );
    },
    { actor, access },
  );
  return { m, headers };
}
async function request(page: Page) {
  const { m } = await setup(page, 3);
  const headers = { Authorization: `Bearer ${m.users[0].token}` };
  const p = await page.request.post(m.api + "/power-apps/approvals/policies", {
    headers,
    data: {
      name: "Browser approval " + Date.now(),
      definition: {
        stages: [
          {
            id: "review",
            name: "Independent finance review",
            mode: "all",
            selectors: [{ kind: "user", ids: [m.users[3].id] }],
          },
        ],
        fields: [
          { key: "amount", label: "Amount", kind: "number", required: true },
        ],
      },
    },
  });
  expect(p.ok()).toBeTruthy();
  const policy = await p.json();
  const active = await page.request.post(
    `${m.api}/power-apps/approvals/policies/${policy.id}/activate?expected_version=1`,
    { headers },
  );
  expect(active.ok()).toBeTruthy();
  const response = await page.request.post(
    m.api + "/power-apps/approvals/requests",
    {
      headers,
      data: {
        policy_id: policy.id,
        title: "Review supplier evidence",
        fields: { amount: 450 },
        request_key: crypto.randomUUID(),
      },
    },
  );
  expect(response.ok()).toBeTruthy();
  const row = await response.json();
  await expect
    .poll(
      async () => {
        const detail = await (
          await page.request.get(
            `${m.api}/power-apps/approvals/requests/${row.id}`,
            { headers },
          )
        ).json();
        return detail.assignments?.length;
      },
      { timeout: 30000 },
    )
    .toBe(1);
  return { m, headers, row, policy };
}
test("approval dashboard, inbox and authenticated worker resume", async ({
  page,
}) => {
  const { row } = await request(page);
  await page.goto("/power-apps/approvals");
  await expect(
    page.getByRole("heading", { name: "Keep good work moving." }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "New request", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".ap-request-row").first()).toBeVisible();
  await page.screenshot({
    path: "../docs/qa/power-approvals-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Approval inbox", exact: false })
    .first()
    .click();
  await page
    .getByRole("button")
    .filter({ hasText: "Review supplier evidence" })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Audit evidence verified")).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByText("Approved", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/qa/power-approvals-decision.png",
    fullPage: true,
  });
  expect(row.id).toBeGreaterThan(0);
});
test("mobile document review and reasoned rejection", async ({ page }) => {
  const { row, m, headers } = await request(page);
  const fileBody = Buffer.from(
    "Isolated approval supporting evidence. Amount: 450.",
  );
  const upload = await page.request.post(
    `${m.api}/power-apps/approvals/requests/${row.id}/attachments`,
    {
      headers,
      multipart: {
        file: {
          name: "supporting-evidence.txt",
          mimeType: "text/plain",
          buffer: fileBody,
        },
      },
    },
  );
  expect(upload.ok()).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/power-apps/approvals/requests?request=${row.id}`);
  await expect(page.getByRole("dialog")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /supporting-evidence.txt/ }).click();
  expect((await download).suggestedFilename()).toBe("supporting-evidence.txt");
  await page
    .getByLabel("Decision reason")
    .fill("Supporting evidence needs correction");
  await page.screenshot({
    path: "../docs/qa/power-approvals-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByText("Rejected", { exact: true }).first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
test("standalone pages and disabled templates", async ({ page }) => {
  await setup(page);
  for (const route of [
    "templates",
    "policies",
    "delegations",
    "analytics",
    "audit",
    "settings",
    "new",
    "designer",
  ]) {
    await page.goto("/power-apps/approvals/" + route);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  await page.goto("/power-apps/approvals/templates");
  await expect(
    page.getByText("Disabled template", { exact: true }),
  ).toHaveCount(20);
  await page
    .getByRole("button", { name: /Configure template/ })
    .first()
    .click();
  await expect(
    page.getByRole("button", { name: "Save version" }),
  ).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await page.screenshot({
    path: "../docs/qa/power-approvals-designer.png",
    fullPage: true,
  });
});
