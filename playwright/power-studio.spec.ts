import { test, expect } from "../frontend/node_modules/playwright/test";
import { setupPowerApps, fixtureRow, makeGraph } from "./power-apps-fixtures";
test.use({ viewport: { width: 1600, height: 1000 } });

test("canvas library configuration and draft autosave", async ({
  page,
}, info) => {
  const state = await setupPowerApps(page);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/power-apps/automations/new");
  await expect(
    page.getByRole("heading", { name: "Node library", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Welcome review");
  await page
    .getByRole("button", { name: "Add Manual Trigger", exact: true })
    .click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "1 nodes / 0 connections",
  );
  await page.getByLabel("Node name", { exact: true }).fill("Start here");
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await expect(page).toHaveURL(/automations\/\d+\/edit/);
  expect(state.records()[0].definition.schema_version).toBe(2);
  expect(state.records()[0].definition.nodes[0].label).toBe("Start here");
  await page
    .getByRole("button", { name: "Add If / Else", exact: true })
    .dragTo(page.locator(".as-canvas"), { targetPosition: { x: 400, y: 210 } });
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 0 connections",
  );
  await page
    .getByLabel("Left value", { exact: true })
    .fill("{{trigger.record.status}}");
  await page.getByLabel("Right value", { exact: true }).fill("Open");
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByLabel("From node", { exact: true })
    .selectOption({ label: "Start here" });
  await page
    .getByLabel("To node", { exact: true })
    .selectOption({ label: "If / Else" });
  await page
    .getByRole("button", { name: "Connect nodes", exact: true })
    .click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  await page.getByRole("button", { name: "Auto layout", exact: true }).click();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page.screenshot({
    path: info.outputPath("studio-first-connection.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  expect(state.writes.some((w) => /publish|execute/.test(w.path))).toBe(false);
});
test("saved workflow opens with an explicit runtime review link", async ({
  page,
}) => {
  await setupPowerApps(page, { records: [fixtureRow()] });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "4 nodes / 3 connections",
  );
  await expect(
    page.getByRole("button", { name: "Publish & runs", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Validate", exact: true }).click();
  await expect(
    page.getByText("Structure is valid", { exact: true }),
  ).toBeVisible();
});

async function connectNodes(
  page: import("../frontend/node_modules/playwright/test").Page,
  source: string,
  target: string,
  port = "Next",
) {
  if (
    await page
      .getByRole("button", { name: "Close configuration", exact: true })
      .isVisible()
  )
    await page
      .getByRole("button", { name: "Close configuration", exact: true })
      .click();
  await page
    .getByRole("combobox", { name: "From node", exact: true })
    .selectOption({ label: source });
  await page
    .getByRole("combobox", { name: "Output port", exact: true })
    .selectOption({ label: port });
  await page
    .getByRole("combobox", { name: "To node", exact: true })
    .selectOption({ label: target });
  await page
    .getByRole("button", { name: "Connect nodes", exact: true })
    .click();
}

test("true false branching variable insertion validation and local testing", async ({
  page,
}, info) => {
  const state = await setupPowerApps(page);
  await page.goto("/power-apps/automations/new");
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Conditional welcome");
  await page
    .getByRole("button", { name: "Add Manual Trigger", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add If / Else", exact: true })
    .click();
  await connectNodes(page, "Manual Trigger", "If / Else");
  await page
    .locator(".as-overview-nodes")
    .getByRole("button", { name: "If / Else", exact: true })
    .click();
  await page
    .locator(".as-config-field")
    .filter({ has: page.getByLabel("Left value", { exact: true }) })
    .getByRole("button", { name: "Insert variable", exact: true })
    .click();
  await page.getByRole("button", { name: /Trigger record \/ status/ }).click();
  await expect(page.getByLabel("Left value", { exact: true })).toHaveValue(
    "{{trigger.record.status}}",
  );
  await page.getByLabel("Right value", { exact: true }).fill("Open");
  await page
    .getByRole("button", { name: "Add Set Variable", exact: true })
    .click();
  await page.getByLabel("Node name", { exact: true }).fill("Welcome result");
  await page
    .getByLabel("Value", { exact: true })
    .fill("Welcome {{trigger.record.name}}");
  await connectNodes(page, "If / Else", "Welcome result", "True");
  await page
    .getByRole("button", { name: "Add Log Event", exact: true })
    .click();
  await page
    .getByLabel("Event message", { exact: true })
    .fill("No welcome required");
  await connectNodes(page, "If / Else", "Log Event", "False");
  await page.getByRole("button", { name: "Auto layout", exact: true }).click();
  await page.getByRole("button", { name: "Validate", exact: true }).click();
  await expect(
    page.getByText("Structure is valid", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Test workflow", exact: true })
    .click();
  await page
    .getByLabel("Test input / JSON", { exact: true })
    .fill('{"record":{"id":42,"status":"Open","name":"Design-time example"}}');
  await page
    .getByRole("button", { name: "Preview locally", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Preview timeline", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".as-preview-timeline>button")).toHaveCount(4);
  await page
    .getByRole("button", { name: "Close testing panel", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close validation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Toggle inspector", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Collapse node library", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Fit to screen", exact: true })
    .click();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await expect(page.locator(".async-progress")).toHaveCount(0);
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page.screenshot({
    path: info.outputPath("automation-studio-desktop.png"),
    fullPage: true,
  });
  expect(
    state.records()[0].definition.edges.map((e: any) => e.source_port),
  ).toEqual(expect.arrayContaining(["true", "false"]));
  expect(state.writes.some((w) => /publish|execute/.test(w.path))).toBe(false);
});

test("undo redo copy paste grouping and keyboard deletion", async ({
  page,
}) => {
  const state = await setupPowerApps(page, { records: [fixtureRow()] });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "4 nodes / 3 connections",
  );
  await page
    .locator(".react-flow__pane")
    .click({ position: { x: 30, y: 400 } });
  await page.keyboard.press("Control+a");
  await page.keyboard.press("Control+c");
  await page.keyboard.press("Control+v");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "8 nodes / 6 connections",
  );
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "4 nodes / 3 connections",
  );
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "8 nodes / 6 connections",
  );
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await page
    .locator(".react-flow__pane")
    .click({ position: { x: 30, y: 400 } });
  await page.keyboard.press("Control+a");
  await page
    .getByRole("button", { name: "Group selection", exact: true })
    .click();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect.poll(() => state.records()[0].definition.groups.length).toBe(1);
  await page
    .getByRole("button", { name: "Ungroup selection", exact: true })
    .click();
  await page
    .locator(".react-flow__pane")
    .click({ position: { x: 30, y: 400 } });
  await page.keyboard.press("Control+a");
  page.once("dialog", (dialog) => dialog.accept());
  await page.keyboard.press("Delete");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "0 nodes / 0 connections",
  );
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "4 nodes / 3 connections",
  );
});

test("autosave conflict preserves recovery and supports a separate copy", async ({
  page,
}) => {
  const state = await setupPowerApps(page, { records: [fixtureRow()] });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByLabel("Automation name", { exact: true })).toHaveValue(
    "Customer onboarding",
  );
  state.bumpVersion(41);
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("My unsaved revision");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Your local draft is preserved",
  );
  await expect(page.locator(".as-save-status")).toContainText("Save conflict");
  expect(state.records()[0].name).toBe("Updated by another user");
  page.once("dialog", (dialog) => dialog.accept());
  await page.reload();
  await expect(page.getByText(/An unsaved draft from/)).toBeVisible();
  await page
    .getByRole("button", { name: "Recover changes", exact: true })
    .click();
  await expect(page.getByLabel("Automation name", { exact: true })).toHaveValue(
    "My unsaved revision",
  );
  await page
    .getByRole("button", { name: "Save as separate copy", exact: true })
    .click();
  await expect(page.getByLabel("Automation name", { exact: true })).toHaveValue(
    "My unsaved revision (copy)",
  );
  expect(state.records().find((r) => r.id === 41).name).toBe(
    "Updated by another user",
  );
  expect(state.records()).toHaveLength(2);
});

test("read-only inspection blocks all edit controls", async ({ page }) => {
  const state = await setupPowerApps(page, {
    readOnly: true,
    records: [fixtureRow()],
  });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "4 nodes / 3 connections",
  );
  await expect(
    page.getByLabel("Automation name", { exact: true }),
  ).toHaveAttribute("readonly", "");
  await expect(
    page.getByRole("button", { name: "Save draft", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Add node", exact: true }),
  ).toBeDisabled();
  await page
    .locator(".as-overview-nodes")
    .getByRole("button", { name: "Transform 1", exact: true })
    .click();
  await expect(page.getByLabel("Node name", { exact: true })).toHaveAttribute(
    "readonly",
    "",
  );
  await expect(
    page.getByRole("button", { name: "Delete node", exact: true }),
  ).toBeDisabled();
  await page.keyboard.press("Control+d");
  expect(
    state.writes.filter((w) => w.method === "PUT" || w.method === "DELETE"),
  ).toHaveLength(0);
});

test("management rename archive duplicate versions settings and templates", async ({
  page,
}, info) => {
  const state = await setupPowerApps(page, { records: [fixtureRow()] });
  await page.goto("/power-apps/automations");
  await page.getByRole("tab", { name: "My Automations", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Customer onboarding", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Shared Automations", exact: true })
    .click();
  await expect(page.getByText("Make your first connection")).toBeVisible();
  await page.getByRole("tab", { name: "All Automations", exact: true }).click();
  await page
    .getByLabel("Actions for Customer onboarding", { exact: true })
    .click();
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await page
    .getByLabel("Rename automation", { exact: true })
    .fill("Client welcome");
  await page
    .getByRole("button", { name: "Save automation name", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Client welcome", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Actions for Client welcome", { exact: true }).click();
  await page
    .getByRole("button", { name: "Archive draft", exact: true })
    .click();
  await expect(page.getByText("Make your first connection")).toBeVisible();
  await page.getByRole("tab", { name: "Disabled", exact: true }).click();
  await expect(page.getByText("Archived draft", { exact: true })).toBeVisible();
  await page.getByLabel("Actions for Client welcome", { exact: true }).click();
  await page.getByRole("button", { name: "Unarchive", exact: true }).click();
  await page.getByRole("tab", { name: "All Automations", exact: true }).click();
  await page.getByLabel("Actions for Client welcome", { exact: true }).click();
  await page.getByRole("button", { name: "Duplicate", exact: true }).click();
  await expect(page.getByLabel("Automation name", { exact: true })).toHaveValue(
    "Client welcome (copy)",
  );
  expect(state.records()).toHaveLength(2);
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Copy version two");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page
    .getByRole("button", { name: "Open version history", exact: true })
    .click();
  await expect(page).toHaveURL(/versions/);
  await expect(
    page.getByRole("heading", { name: "Version history", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Compare version", { exact: true }).selectOption("1");
  await page.getByLabel("With version", { exact: true }).selectOption("2");
  await expect(
    page.getByText("Automation name changed", { exact: true }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Restore as new draft", exact: true })
    .last()
    .click();
  await expect(page.getByLabel("Automation name", { exact: true })).toHaveValue(
    "Client welcome (copy) (restored)",
  );
  expect(state.records()).toHaveLength(3);
  await page
    .getByRole("button", { name: "Open workflow settings", exact: true })
    .click();
  await expect(page).toHaveURL(/settings/);
  await page.getByLabel("History retention (days)", { exact: true }).fill("60");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  expect(
    state.records().find((r) => r.name.includes("restored")).definition.settings
      .retention_days,
  ).toBe(60);
  await page
    .getByRole("button", { name: "Back to automation list", exact: true })
    .click();
  await page.getByRole("tab", { name: "Published", exact: true }).click();
  await expect(page.getByText("No published automations")).toBeVisible();
  await page.getByRole("tab", { name: "Templates", exact: true }).click();
  await expect(page.locator(".al-templates article")).toHaveCount(39);
  await page.screenshot({
    path: info.outputPath("automation-templates.png"),
    fullPage: true,
  });
  await page
    .locator(".al-templates article")
    .first()
    .locator("summary")
    .click();
  await page
    .locator(".al-templates article")
    .first()
    .getByRole("button", { name: "Use template" })
    .click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
});

test("mobile node inspection and tablet panel resizing", async ({
  page,
}, info) => {
  await setupPowerApps(page, { records: [fixtureRow(41, makeGraph(2))] });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Toggle inspector", exact: true })
    .click();
  await page
    .locator(".as-overview-nodes")
    .getByRole("button", { name: "Transform 1", exact: true })
    .click();
  await expect(page.getByLabel("Node name", { exact: true })).toBeVisible();
  await expect(page.locator(".async-progress")).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("automation-studio-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close inspector", exact: true })
    .click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1150, height: 900 });
  await page
    .getByRole("button", { name: "Toggle inspector", exact: true })
    .click();
  const before = await page
    .locator(".as-panel-host")
    .evaluate((el) => el.getBoundingClientRect().width);
  await page
    .getByRole("separator", { name: "Resize configuration panel" })
    .focus();
  await page.keyboard.press("ArrowLeft");
  const after = await page
    .locator(".as-panel-host")
    .evaluate((el) => el.getBoundingClientRect().width);
  expect(after).toBeGreaterThan(before);
});

for (const count of [10, 50, 100, 250])
  test(`${count}-node editor responsiveness`, async ({ page }, info) => {
    const graph = makeGraph(count);
    await setupPowerApps(page, { records: [fixtureRow(41, graph)] });
    const started = Date.now();
    await page.goto("/power-apps/automations/41/edit");
    await expect(page.getByTestId("graph-count")).toHaveText(
      `${count} nodes / ${count - 1} connections`,
    );
    const renderMs = Date.now() - started;
    const metrics = await page.evaluate(
      async ({ graph }) => {
        const { validateGraph } = await import(
          /* @vite-ignore */ "/src/apps/power-apps/applications/automations/builder/graph.ts"
        );
        const catalog = await fetch(
          "/api/v1/power-apps/automations/node-catalog",
        ).then((r) => r.json());
        let t = performance.now();
        const serialized = JSON.stringify(graph);
        const serializationMs = performance.now() - t;
        t = performance.now();
        const result = validateGraph(graph, catalog.nodes);
        return {
          serializationMs,
          validationMs: performance.now() - t,
          bytes: serialized.length,
          valid: result.valid,
        };
      },
      { graph },
    );
    expect(metrics.valid).toBe(true);
    expect(metrics.serializationMs).toBeLessThan(200);
    expect(metrics.validationMs).toBeLessThan(500);
    const editStart = Date.now();
    await page
      .getByLabel("Automation name", { exact: true })
      .fill(`Measured ${count}-node draft`);
    await expect(
      page.getByLabel("Automation name", { exact: true }),
    ).toHaveValue(`Measured ${count}-node draft`);
    const interactionMs = Date.now() - editStart;
    expect(interactionMs).toBeLessThan(1500);
    await page
      .getByRole("button", { name: "Fit to screen", exact: true })
      .click();
    await expect(page.getByTestId("graph-count")).toHaveText(
      `${count} nodes / ${count - 1} connections`,
    );
    await page.getByRole("button", { name: "Save draft", exact: true }).click();
    await expect(page.locator(".as-save-status")).toContainText("Saved");
    const report = { count, renderMs, interactionMs, ...metrics };
    await info.attach("editor-responsiveness", {
      body: JSON.stringify(report, null, 2),
      contentType: "application/json",
    });
    const fs = await import("node:fs/promises");
    await fs.writeFile(
      info.outputPath(`performance-${count}.json`),
      JSON.stringify(report, null, 2),
    );
  });

test("mini-map renders workflow nodes and wheel and touch gestures zoom", async ({
  browser,
}, info) => {
  const context = await browser.newContext({
    baseURL: String(info.project.use.baseURL),
    hasTouch: true,
    viewport: { width: 1100, height: 900 },
  });
  const page = await context.newPage();
  try {
    await setupPowerApps(page, { records: [fixtureRow()] });
    await page.goto("/power-apps/automations/41/edit");
    await expect(page.getByTestId("graph-count")).toHaveText(
      "4 nodes / 3 connections",
    );
    await expect(page.locator(".react-flow__minimap-node")).toHaveCount(4);
    const colors = await page
      .locator(".react-flow__minimap-node")
      .evaluateAll((nodes) =>
        nodes.map(
          (n) => n.getAttribute("fill") || (n as SVGElement).style.fill,
        ),
      );
    expect(colors.every(Boolean)).toBe(true);
    const canvas = await page.locator(".as-canvas").boundingBox();
    const x = canvas!.x + canvas!.width / 2,
      y = canvas!.y + canvas!.height / 2;
    const before = await page
      .locator(".react-flow__viewport")
      .evaluate((el) => (el as HTMLElement).style.transform);
    await page.mouse.move(x, y);
    await page.mouse.wheel(0, -250);
    await expect
      .poll(() =>
        page
          .locator(".react-flow__viewport")
          .evaluate((el) => (el as HTMLElement).style.transform),
      )
      .not.toBe(before);
    const afterWheel = await page
      .locator(".react-flow__viewport")
      .evaluate((el) => (el as HTMLElement).style.transform);
    const cdp = await context.newCDPSession(page);
    await cdp.send("Input.synthesizePinchGesture", {
      x,
      y,
      scaleFactor: 1.2,
      relativeSpeed: 400,
      gestureSourceType: "touch",
    });
    await expect
      .poll(() =>
        page
          .locator(".react-flow__viewport")
          .evaluate((el) => (el as HTMLElement).style.transform),
      )
      .not.toBe(afterWheel);
  } finally {
    await context.close();
  }
});

test("legacy numeric node IDs and delay settings survive visual editing", async ({
  page,
}) => {
  const row = fixtureRow();
  row.definition = {
    schema_version: 1,
    trigger: { type: "manual" },
    nodes: [{ id: "123", type: "delay", next: [], delay_seconds: 180 }],
    entry: "123",
    max_attempts: 5,
    retry_backoff_seconds: 120,
  } as never;
  const state = await setupPowerApps(page, { records: [row] });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByText(/Imported schema v1 for review/)).toBeVisible();
  await page
    .locator(".as-overview-nodes")
    .getByRole("button", { name: "Delay", exact: true })
    .click();
  await expect(
    page.getByLabel("Duration (seconds)", { exact: true }),
  ).toHaveValue("180");
  await page
    .getByLabel("Node description", { exact: true })
    .fill("Imported draft reviewed");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  expect(
    state.records()[0].definition.nodes.find((n: any) => n.type === "delay").id,
  ).toBe("legacy_123");
  expect(state.records()[0].definition.settings.max_attempts).toBe(5);
});

test("copy remaps only dynamic references and reference selectors use authorized data", async ({
  page,
}) => {
  const state = await setupPowerApps(page, {
    records: [fixtureRow(41, makeGraph(2))],
  });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  const result = await page.evaluate(async () => {
    const helpers = await import(
      /* @vite-ignore */ "/src/apps/power-apps/applications/automations/builder/graph.ts"
    );
    const graph = {
      schema_version: 2,
      catalog_version: 1,
      nodes: [
        {
          id: "source",
          type: "set_variable",
          label: "Source",
          position: { x: 0, y: 0 },
          config: { value: "one" },
          credential_reference: null,
          advanced: {
            retry_attempts: 3,
            error_strategy: "stop",
            timeout_seconds: 60,
          },
        },
        {
          id: "target",
          type: "set_variable",
          label: "Target",
          position: { x: 400, y: 0 },
          config: {
            value: "{{steps.source.output.value}}",
            literal: "steps.source.output.value",
          },
          credential_reference: null,
          advanced: {
            retry_attempts: 3,
            error_strategy: "stop",
            timeout_seconds: 60,
          },
        },
      ],
      edges: [],
      groups: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      settings: {},
    };
    const copied = helpers.copySubgraph(graph, new Set(["source", "target"]));
    const pasted = helpers.pasteSubgraph(graph, copied).graph.nodes.slice(2);
    return { source: pasted[0].id, target: pasted[1].config };
  });
  expect(result.target.value).toBe(`{{steps.${result.source}.output.value}}`);
  expect(result.target.literal).toBe("steps.source.output.value");
  await page
    .getByRole("button", { name: "Add Create Task", exact: true })
    .click();
  await page
    .getByLabel("Task title", { exact: true })
    .fill("Design-time task only");
  await page
    .getByRole("button", { name: "Choose user reference", exact: true })
    .click();
  await page.getByRole("option", { name: /Alex Builder/ }).click();
  await expect(
    page.getByRole("combobox", { name: "Assignee", exact: true }),
  ).toHaveValue("1");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  expect(state.writes.some((w) => /publish|execute/.test(w.path))).toBe(false);
});
