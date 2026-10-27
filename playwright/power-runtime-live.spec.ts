import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
async function session(page: Page, index = 0) {
  const manifest = JSON.parse(
    await fs.readFile(
      path.resolve(__dirname, "../.tmp/power-studio-live-session.json"),
      "utf8",
    ),
  );
  const actor = manifest.users[index],
    headers = { Authorization: `Bearer ${actor.token}` };
  const access = await (
    await page.request.get(`${manifest.api}/access/me`, { headers })
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
              name: "Runtime QA",
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
  return { api: manifest.api, headers, manifest };
}
const node = (
  id: string,
  type: string,
  config: Record<string, unknown> = {},
  x = 100,
) => ({
  id,
  type,
  label: type.replace(/_/g, " "),
  position: { x, y: 150 },
  config,
});
const edge = (source: string, target: string) => ({
  id: `${source}_${target}`,
  source,
  target,
  source_port: "out",
  target_port: "in",
});
async function workflow(
  page: Page,
  ctx: Awaited<ReturnType<typeof session>>,
  kind = "manual_trigger",
  middle = "set_variable",
  config: Record<string, unknown> = { value: 42 },
) {
  const definition = {
    schema_version: 2,
    nodes: [
      node(
        "start",
        kind,
        kind === "scheduled_trigger"
          ? { schedule: "* * * * *", timezone: "UTC" }
          : kind === "webhook_trigger"
            ? { event_name: "runtime.qa" }
            : {},
        0,
      ),
      node("action", middle, config, 350),
      node(
        "log",
        "log_event",
        { message: "Runtime completed", level: "info" },
        700,
      ),
    ],
    edges: [edge("start", "action"), edge("action", "log")],
  };
  const response = await page.request.post(
    `${ctx.api}/power-apps/automations`,
    {
      headers: ctx.headers,
      data: { name: `Runtime QA ${kind} ${middle}`, definition },
    },
  );
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}
async function activate(
  page: Page,
  ctx: Awaited<ReturnType<typeof session>>,
  row: any,
  delegated = false,
) {
  for (const action of ["validate", "publish", "activate"]) {
    const r = await page.request.post(
      `${ctx.api}/power-apps/automations/${row.id}/runtime/${action}`,
      {
        headers: ctx.headers,
        data: {
          expected_version: row.version,
          policy: delegated ? { identity: "owner", delegated_owner: true } : {},
        },
      },
    );
    expect(r.ok(), await r.text()).toBe(true);
  }
}
async function run(
  page: Page,
  ctx: Awaited<ReturnType<typeof session>>,
  id: number,
) {
  const r = await page.request.post(
    `${ctx.api}/power-apps/automations/${id}/execute`,
    {
      headers: ctx.headers,
      data: { input: {}, idempotency_key: crypto.randomUUID() },
    },
  );
  expect(r.ok(), await r.text()).toBe(true);
  return (await r.json()).id;
}
async function waitStatus(
  page: Page,
  ctx: Awaited<ReturnType<typeof session>>,
  id: number,
  status: string,
) {
  await expect
    .poll(
      async () => {
        const r = await page.request.get(
          `${ctx.api}/power-apps/executions/${id}`,
          { headers: ctx.headers },
        );
        return (await r.json()).execution?.status;
      },
      { timeout: 35000 },
    )
    .toBe(status);
}

test("publish activate execute and inspect real persisted history", async ({
  page,
}, testInfo) => {
  const ctx = await session(page),
    row = await workflow(page, ctx);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`/power-apps/automations/${row.id}/runtime`);
  await page.getByRole("button", { name: "Validate saved draft" }).click();
  await expect(page.locator(".rt-notice")).toContainText(
    "passed runtime validation",
  );
  await page.getByRole("button", { name: "Publish V1", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirm publish", exact: true })
    .click();
  await expect(page.locator(".rt-notice")).toContainText("published");
  await page.getByRole("button", { name: "Activate", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirm activate", exact: true })
    .click();
  await expect(page.locator(".rt-notice")).toContainText("activated");
  await page
    .getByRole("button", { name: "Start execution", exact: true })
    .click();
  await expect(page).toHaveURL(/executions\/\d+/);
  await expect(page.locator(".rt-run-meta .rt-status")).toHaveText(
    "completed",
    { timeout: 35000 },
  );
  await expect(
    page.getByRole("heading", { name: "Execution timeline" }),
  ).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await page.getByRole("button", { name: /3\. log event/ }).click();
  await expect(page.locator(".rt-debug pre")).toContainText(
    "Runtime completed",
  );
  await expect(page.locator(".rt-debug pre")).toContainText("attempt");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export sanitized report" }).click();
  const file = await download;
  await file.saveAs(testInfo.outputPath("execution-report.json"));
  const report = JSON.parse(
    await fs.readFile(testInfo.outputPath("execution-report.json"), "utf8"),
  );
  expect(report.execution.status).toBe("completed");
  expect(report.execution.workflow_version).toBe(1);
  expect(report.steps.every((s: any) => s.attempt === 1)).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("execution-debugger.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  await page.getByRole("link", { name: "All executions" }).click();
  await expect(
    page.getByRole("heading", { name: "Execution history" }),
  ).toBeVisible();
  await expect(
    page.locator(".rt-metrics article").filter({ hasText: "Completed" }),
  ).not.toContainText("—");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("executions-mobile.png"),
    fullPage: true,
  });
});

test("cancel a durable wait and retry a failed pure step", async ({ page }) => {
  const ctx = await session(page);
  const waiting = await workflow(page, ctx, "manual_trigger", "delay", {
    seconds: 300,
  });
  await activate(page, ctx, waiting);
  const id = await run(page, ctx, waiting.id);
  await waitStatus(page, ctx, id, "waiting");
  await page.goto(`/power-apps/automations/executions/${id}`);
  await expect(page.locator(".rt-run-meta .rt-status")).toHaveText("waiting");
  await page.getByRole("button", { name: "Cancel run", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirm cancel", exact: true })
    .click();
  await expect(page.locator(".rt-run-meta .rt-status")).toHaveText("cancelled");
  const failing = await workflow(page, ctx, "manual_trigger", "parse_json", {
    value: "not JSON",
  });
  await activate(page, ctx, failing);
  const failed = await run(page, ctx, failing.id);
  await waitStatus(page, ctx, failed, "failed");
  await page.goto(`/power-apps/automations/executions/${failed}`);
  await page.getByRole("button", { name: "Retry failed step safely" }).click();
  await expect
    .poll(
      async () => {
        const r = await page.request.get(
          `${ctx.api}/power-apps/executions/${failed}`,
          { headers: ctx.headers },
        );
        return (await r.json()).steps.find((s: any) => s.node_id === "action")
          .attempt;
      },
      { timeout: 35000 },
    )
    .toBe(2);
  await page.getByRole("button", { name: "Re-run with confirmation" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "current active publication",
  );
  await page.getByRole("button", { name: "Go back" }).click();
  await page.getByRole("button", { name: "Re-run with confirmation" }).click();
  await page
    .getByRole("button", { name: "Confirm rerun", exact: true })
    .click();
  await expect(page).not.toHaveURL(new RegExp(`/executions/${failed}$`));
  await expect(page.locator(".rt-run-meta .rt-status")).toHaveText("failed", {
    timeout: 35000,
  });
  const newId = Number(new URL(page.url()).pathname.split("/").pop());
  expect(newId).not.toBe(failed);
  const rerunHistory = await (
    await page.request.get(`${ctx.api}/power-apps/executions/${newId}`, {
      headers: ctx.headers,
    })
  ).json();
  expect(rerunHistory.execution.id).toBe(newId);
});

test("secured webhook and one-time schedule enqueue real runs", async ({
  page,
}) => {
  const ctx = await session(page);
  const hook = await workflow(page, ctx, "webhook_trigger");
  await activate(page, ctx, hook, true);
  const configured = await page.request.put(
    `${ctx.api}/power-apps/automations/${hook.id}/triggers/webhook`,
    {
      headers: ctx.headers,
      data: {
        enabled: true,
        config: {
          schema: {
            type: "object",
            properties: { message: { type: "string" } },
            required: ["message"],
            additionalProperties: false,
          },
        },
      },
    },
  );
  expect(configured.ok(), await configured.text()).toBe(true);
  const ingress = await configured.json();
  const body = JSON.stringify({ message: "Signed runtime QA" }),
    stamp = String(Math.floor(Date.now() / 1000)),
    nonce = crypto.randomUUID();
  const signature = crypto
    .createHmac("sha256", ingress.secret)
    .update(`${stamp}.${nonce}.${body}`)
    .digest("hex");
  expect(
    (
      await page.request.post(`http://127.0.0.1:1545${ingress.endpoint}`, {
        data: body,
        headers: { "content-type": "application/json" },
      })
    ).status(),
  ).toBe(401);
  const signed = {
    data: body,
    headers: {
      "content-type": "application/json",
      "x-power-timestamp": stamp,
      "x-power-nonce": nonce,
      "x-power-signature": signature,
    },
  };
  const accepted = await page.request.post(
    `http://127.0.0.1:1545${ingress.endpoint}`,
    signed,
  );
  expect(accepted.status(), await accepted.text()).toBe(202);
  const id = (await accepted.json()).id;
  await waitStatus(page, ctx, id, "completed");
  expect(
    (
      await page.request.post(
        `http://127.0.0.1:1545${ingress.endpoint}`,
        signed,
      )
    ).status(),
  ).toBe(409);
  const schedule = await workflow(page, ctx, "scheduled_trigger");
  await activate(page, ctx, schedule, true);
  const scheduled = await page.request.put(
    `${ctx.api}/power-apps/automations/${schedule.id}/triggers/scheduled`,
    {
      headers: ctx.headers,
      data: {
        enabled: true,
        config: {
          mode: "once",
          at: new Date(Date.now() + 1500).toISOString(),
          timezone: "UTC",
        },
      },
    },
  );
  expect(scheduled.ok(), await scheduled.text()).toBe(true);
  await expect
    .poll(
      async () => {
        const r = await page.request.get(
          `${ctx.api}/power-apps/executions?workflow=${schedule.id}`,
          { headers: ctx.headers },
        );
        const list = await r.json();
        return list.items.filter((x: any) => x.status === "completed").length;
      },
      { timeout: 35000 },
    )
    .toBe(1);
});

test("reviewer and foreign tenant cannot perform runtime operations", async ({
  page,
}) => {
  const ctx = await session(page),
    row = await workflow(page, ctx);
  await activate(page, ctx, row);
  const id = await run(page, ctx, row.id);
  await waitStatus(page, ctx, id, "completed");
  const reviewer = await session(page, 1),
    foreign = ctx.manifest.users[2];
  expect(
    (
      await page.request.get(`${ctx.api}/power-apps/executions/${id}`, {
        headers: { Authorization: `Bearer ${foreign.token}` },
      })
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.post(`${ctx.api}/power-apps/executions/${id}/retry`, {
        headers: reviewer.headers,
      })
    ).status(),
  ).toBe(403);
  await page.goto(`/power-apps/automations/executions/${id}`);
  await expect(
    page.getByRole("heading", { name: "Execution timeline" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Cancel run", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Re-run with confirmation" }),
  ).toHaveCount(0);
});

test("loop instances retain independent debugger selection", async ({
  page,
}) => {
  const ctx = await session(page);
  const definition = {
    schema_version: 2,
    nodes: [
      node("start", "manual_trigger", {}, 0),
      {
        ...node("loop", "for_each", { items: [1, 2], max_iterations: 2 }, 300),
        label: "Bounded loop",
      },
      {
        ...node(
          "body",
          "set_variable",
          { value: "{{steps.loop.output.value}}" },
          600,
        ),
        label: "Loop body",
      },
      node(
        "done",
        "log_event",
        { message: "Loop complete", level: "info" },
        900,
      ),
    ],
    edges: [
      edge("start", "loop"),
      { ...edge("loop", "body"), source_port: "body" },
      { ...edge("loop", "done"), source_port: "done" },
    ],
  };
  const response = await page.request.post(
    `${ctx.api}/power-apps/automations`,
    {
      headers: ctx.headers,
      data: { name: "Runtime loop inspection", definition },
    },
  );
  expect(response.ok(), await response.text()).toBe(true);
  const row = await response.json();
  await activate(page, ctx, row);
  const id = await run(page, ctx, row.id);
  await waitStatus(page, ctx, id, "completed");
  await page.goto(`/power-apps/automations/executions/${id}`);
  await expect(
    page.getByRole("heading", { name: "Execution timeline" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /5\. Loop body/ }).click();
  await expect(page.locator(".rt-debug pre")).toContainText('"value": 2');
  await page.getByRole("button", { name: /4\. Loop body/ }).click();
  await expect(page.locator(".rt-debug pre")).toContainText('"value": 1');
});
