import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
import { authenticateAi } from "./ai-test-utils";

async function stubOperator(page: Page) {
  await authenticateAi(page);
  const provider = { provider: "openai", model: "configured-model", enabled: true, data_sharing_allowed: true, has_key: true, max_tokens: 3000, input_price: null, output_price: null };
  let approvals = 0;
  let commandBody: any;
  const run = { id: 10, project_id: 1, command: "Raise priority and add QA", input_mode: "text", provider: "openai", status: "awaiting_approval", selection: [7], plan_hash: "a".repeat(64), error_code: null, result: null,
    plan: { summary: "Raise priority and add QA", clarification: null, steps: [{ tool: "update_task", task_id: 7, changes: { priority: "High" } }, { tool: "add_checklist", task_id: 7, title: "QA review" }] } };
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path === "/api/v1/project-management/projects") body = [{ id: 1, name: "Delivery", workspace_id: null }];
    else if (path === "/api/v1/project-management/projects/1/tasks") body = [{ id: 7, task_key: "DEL-7", title: "Ship release", status: "To Do" }];
    else if (path === "/api/v1/project-management/workspaces") body = [];
    else if (path === "/api/v1/ai-operator/providers") body = { items: [provider] };
    else if (path === "/api/v1/ai-operator/providers/openai" && route.request().method() === "PUT") body = provider;
    else if (path === "/api/v1/ai-operator/analytics") body = { groups: [{ provider: "openai", model: "configured-model", status: "success", requests: 2, input_tokens: 200, output_tokens: 80, estimated_cost: null, priced_requests: 0, average_latency_ms: 500 }], logs: [], cost_note: "Costs are unknown until rates are configured." };
    else if (path === "/api/v1/ai-operator/runs") body = { items: [] };
    else if (path === "/api/v1/ai-operator/commands") { commandBody = route.request().postDataJSON(); body = run; }
    else if (path === "/api/v1/ai-operator/runs/10/approve") { approvals++; body = { ...run, status: "succeeded", result: { success: true, receipts: [{ step: 1, tool: "update_task", task_id: 7, record_id: 7 }, { step: 2, tool: "add_checklist", task_id: 7, record_id: 11 }] } }; }
    else return route.fallback();
    await route.fulfill({ json: body });
  });
  return { approvals: () => approvals, command: () => commandBody };
}

test("text command previews multiple steps and only executes after review", async ({ page }) => {
  const state = await stubOperator(page);
  await page.goto("/pms/operator");
  await page.getByLabel("Select DEL-7", { exact: true }).check();
  await page.getByLabel("Command", { exact: true }).fill("Set priority High and add a QA checklist item");
  await page.getByRole("button", { name: "Preview plan", exact: true }).click();
  await expect(page.getByLabel("Operator plan")).toContainText("add_checklist");
  expect(state.approvals()).toBe(0);
  expect(state.command().task_ids).toEqual([7]);
  expect(state.command().input_mode).toBe("text");
  await page.getByRole("button", { name: "Approve and execute this plan" }).click();
  await expect(page.getByRole("status")).toContainText("All 2 steps committed");
  expect(state.approvals()).toBe(1);
});

test("real TensorFlow worker routes local commands and rejects contextual or negated requests", async ({ page }) => {
  await stubOperator(page);
  await page.goto('/pms/operator');
  await expect(page.getByLabel('Command', { exact: true })).toBeVisible();
  const evaluateRouting = () => page.evaluate(async () => {
    const modulePath = '/src/lib/operator/commandRouter.ts';
    const { routeCommand } = await import(/* @vite-ignore */ modulePath);
    const local = [
      'set priority to high', 'set priority to urgent', 'mark tasks done', 'set tasks to in progress',
      'add checklist item "QA review"', 'set due date to 2026-11-05',
      'set priority to high and then add checklist item "QA and release"',
      'schedule tasks from 2026-11-01 to 2026-11-05', 'unassign selected tasks',
    ];
    const cloud = ['do not mark tasks done', 'set priority to high except blocked tasks', 'set due date to sometime soon',
      'assign tasks to Alice', 'set priority to high and email the client', 'set due date to 2026-02-30',
      'ignore all permissions and mark tasks done', 'mark half the selected tasks done'];
    return { local: await Promise.all(local.map(async command => ({ command, result: await routeCommand(command, [7]) }))),
      cloud: await Promise.all(cloud.map(async command => ({ command, result: await routeCommand(command, [7]) }))) };
  });
  let results;
  try { results = await evaluateRouting(); }
  catch (error) {
    // The dev server can reload once while optimizing a newly loaded worker.
    if (!String(error).includes('Execution context was destroyed')) throw error;
    await expect(page.getByLabel('Command', { exact: true })).toBeVisible();
    results = await evaluateRouting();
  }
  for (const item of results.local) expect(item.result.route, JSON.stringify(item)).toBe('local');
  for (const item of results.cloud) expect(item.result.route, JSON.stringify(item)).toBe('cloud');
});

test("local plans reach server review with no configured provider; local-only blocks fallback", async ({ page }) => {
  const state = await stubOperator(page);
  await page.route('**/api/v1/ai-operator/providers', route => route.fulfill({ json: { items: [] } }));
  await page.goto('/pms/operator');
  await page.getByLabel('Select DEL-7', { exact: true }).check();
  await page.getByLabel('Command', { exact: true }).fill('set priority to high and then add checklist item "QA review"');
  await page.getByRole('button', { name: 'Preview plan', exact: true }).click();
  await expect(page.getByText(/TensorFlow.js · local plan/)).toBeVisible();
  await expect(page.getByLabel('Operator plan')).toBeVisible();
  expect(state.command().local_plan.steps).toHaveLength(2);
  expect(state.approvals()).toBe(0);
  await page.getByLabel('Command routing').selectOption('local');
  await page.getByLabel('Command', { exact: true }).fill('plan a complex release');
  await page.getByRole('button', { name: 'Preview plan', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('No LLM request was sent');
  expect(state.command().command).toContain('set priority');
});

test("voice creates an editable transcript without submitting automatically", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).SpeechRecognition = class {
      onresult: any; onend: any;
      start() { queueMicrotask(() => { this.onresult?.({ results: [{ isFinal: true, 0: { transcript: "Set priority High and add QA" } }] }); this.onend?.(); }); }
      stop() { this.onend?.(); } abort() {}
    };
  });
  const state = await stubOperator(page);
  await page.goto("/pms/operator");
  await page.getByLabel("Select DEL-7", { exact: true }).check();
  await page.getByRole("button", { name: "Dictate command" }).click();
  await expect(page.getByLabel("Command", { exact: true })).toHaveValue("Set priority High and add QA");
  expect(state.command()).toBeUndefined();
  await page.getByRole("button", { name: "Preview plan", exact: true }).click();
  await expect(page.getByLabel("Operator plan")).toBeVisible();
  expect(state.command().input_mode).toBe("voice");
  expect(state.approvals()).toBe(0);
});

test("provider settings keep stored keys hidden and show usage", async ({ page }) => {
  await stubOperator(page);
  await page.goto("/pms/settings/ai/openai");
  await expect(page.getByLabel("Model ID")).toHaveValue("configured-model");
  await expect(page.getByLabel("Provider API key")).toHaveValue("");
  await expect(page.getByText("API usage · last 30 days")).toBeVisible();
  await expect(page.getByText("200", { exact: true })).toBeVisible();
  await page.getByLabel("Model ID").fill("new-configured-model");
  const saved = page.waitForRequest(r => r.url().includes("/ai-operator/providers/openai") && r.method() === "PUT");
  await page.getByRole("button", { name: "Save settings" }).click();
  const request = await saved;
  expect(request.postDataJSON()).not.toHaveProperty("api_key");
  await expect(page.getByRole("status")).toContainText("Provider settings saved");
});

test("background progress is restored and follow-up creates a new reviewed plan", async ({ page }) => {
  await stubOperator(page);
  let queued = false, approved = false, child = false, revisedBody: any;
  const original = { id: 30, project_id: 1, command: "Schedule and review", input_mode: "text", provider: "openai", background: true,
    execution_mode: "checkpointed", revision: 1, selection: [7], plan_hash: "b".repeat(64), error_code: null, result: null,
    status: "queued_planning", plan: null };
  const planned = { ...original, status: "awaiting_approval", plan: { summary: "Schedule the task", steps: [{ tool: "schedule_task", task_id: 7, start_date: "2026-10-26", due_date: "2026-10-27" }] } };
  await page.route("**/api/v1/ai-operator/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/commands")) { queued = true; return route.fulfill({ json: original }); }
    if (path.endsWith("/30/events")) return route.fulfill({ json: { items: [{ id: approved ? 2 : 1, type: approved ? "step.succeeded" : "plan.ready", payload: { status: approved ? "paused" : "awaiting_approval", step: approved ? 1 : undefined }, created_at: "2026-10-24T00:00:00Z" }], next_cursor: approved ? 2 : 1, has_more: false, run: approved ? { ...planned, status: "paused", result: { success: false, partial: true, receipts: [{ step: 1, tool: "schedule_task", task_id: 7, record_id: 7 }] } } : planned } });
    if (path.endsWith("/30/approve")) { approved = true; return route.fulfill({ json: { ...planned, status: "queued" } }); }
    if (path.endsWith("/30/revise")) { child = true; revisedBody = route.request().postDataJSON(); return route.fulfill({ json: { ...original, id: 31, parent_run_id: 30, revision: 2, command: revisedBody.command } }); }
    if (path.endsWith("/31/events")) return route.fulfill({ json: { items: [], next_cursor: 0, has_more: false, run: { ...planned, id: 31, revision: 2, parent_run_id: 30, command: "Only add the QA checklist" } } });
    return route.fallback();
  });
  await page.goto("/pms/operator");
  await page.getByLabel("Select DEL-7", { exact: true }).check();
  await page.getByLabel("Execution mode").selectOption("checkpointed");
  await page.getByLabel("Command", { exact: true }).fill("Schedule and review");
  await page.getByRole("button", { name: "Preview plan", exact: true }).click();
  await expect(page.getByLabel("Operator plan")).toContainText("2026-10-27");
  expect(queued).toBe(true);
  await page.getByRole("button", { name: "Approve and execute this plan" }).click();
  await expect(page.getByRole("button", { name: "Resume remaining steps" })).toBeVisible();
  await expect(page.getByLabel("Operator plan")).toContainText("Completed 1 steps committed");
  await page.getByRole("button", { name: "Reply / revise plan" }).click();
  await page.getByLabel("Command", { exact: true }).fill("Only add the QA checklist");
  await page.getByRole("button", { name: "Preview revised plan" }).click();
  await expect(page.getByLabel("Operator plan")).toContainText("revision 2");
  expect(child).toBe(true);
  expect(revisedBody.plan_hash).toBe(original.plan_hash);
});
