import { test, expect } from "../frontend/node_modules/playwright/test";
import { setupPowerApps, fixtureRow, makeGraph } from "./power-apps-fixtures";
test.use({ viewport: { width: 1600, height: 1000 } });
test("premium search tabs typed mappings notes groups and persisted canvas settings", async ({
  page,
}, info) => {
  const graph = makeGraph(3);
  graph.variables = { greeting: "Welcome", limit: 12 };
  const state = await setupPowerApps(page, {
    records: [fixtureRow(41, graph)],
  });
  await page.goto("/power-apps/automations/41/edit");
  await page
    .locator(".react-flow__pane")
    .click({ position: { x: 20, y: 300 } });
  await page.keyboard.press("Control+f");
  await page
    .getByLabel("Search workflow nodes", { exact: true })
    .fill("Transform 2");
  await page.locator(".as-workflow-search>div button").click();
  await expect(page.getByLabel("Node name", { exact: true })).toHaveValue(
    "Transform 2",
  );
  await page
    .getByRole("button", { name: "Insert variable", exact: true })
    .click();
  await page
    .getByLabel("Search variables", { exact: true })
    .fill("Workflow / greeting");
  await page
    .getByRole("button")
    .filter({ hasText: "Workflow / greeting" })
    .click();
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue(
    /workflow.variables.greeting/,
  );
  await page.getByLabel("Value", { exact: true }).fill("");
  await page.getByLabel("Value", { exact: true }).pressSequentially("{{");
  await page
    .getByLabel("Search variables", { exact: true })
    .fill("Workflow / greeting");
  await page
    .getByRole("button")
    .filter({ hasText: "Workflow / greeting" })
    .click();
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue(
    "{{workflow.variables.greeting}}",
  );
  await page.getByRole("tab", { name: "Input / Output", exact: true }).click();
  await expect(
    page.getByText("DECLARED INPUT PORTS", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Settings", exact: true }).click();
  await page.getByLabel("Disable node", { exact: true }).check();
  await page.getByRole("tab", { name: "Documentation", exact: true }).click();
  await expect(
    page.getByText("Documentation / help", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page.getByLabel("Canvas options", { exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Snap to grid", exact: true })
    .uncheck();
  await page
    .getByLabel("Default connection style", { exact: true })
    .selectOption("orthogonal");
  await page
    .getByRole("button", { name: "Add sticky note", exact: true })
    .click();
  await page.getByLabel("Canvas options", { exact: true }).click();
  await page
    .getByLabel("Note text", { exact: true })
    .fill("<script>safe plain text</script> Review the outcome");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page.reload();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "3 nodes / 2 connections",
  );
  expect(state.records()[0].definition.nodes[2].disabled).toBe(true);
  expect(state.records()[0].definition.editor.snap_to_grid).toBe(false);
  expect(state.records()[0].definition.annotations[0].text).toContain(
    "<script>",
  );
  expect(await page.locator(".as-annotation script").count()).toBe(0);
  await page
    .locator(".react-flow__pane")
    .click({ position: { x: 20, y: 300 } });
  await page.keyboard.press("Control+a");
  await page
    .getByRole("button", { name: "Group selection", exact: true })
    .click();
  await page.getByLabel("Group label", { exact: true }).fill("Review branch");
  await page
    .getByRole("button", { name: "Collapse group", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Expand group Review branch",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page.reload();
  await expect(
    page.getByRole("button", {
      name: "Expand group Review branch",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Expand group Review branch", exact: true })
    .click();
  await page.keyboard.press("Control+f");
  await page
    .getByLabel("Search workflow nodes", { exact: true })
    .fill("Transform 2");
  await page.locator(".as-workflow-search>div button").click();
  await expect(page.getByLabel("Node name", { exact: true })).toHaveValue(
    "Transform 2",
  );
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Collapse node library", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Fit to screen", exact: true })
    .click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page.screenshot({
    path: info.outputPath("premium-studio.png"),
    fullPage: true,
  });
});
test("connection insertion rejects ambiguity then safely reconnects compatible node", async ({
  page,
}) => {
  const state = await setupPowerApps(page, {
    records: [fixtureRow(41, makeGraph(2))],
  });
  await page.goto("/power-apps/automations/41/edit");
  await page
    .getByRole("button", { name: "Fit to screen", exact: true })
    .click();
  await expect(page.getByTestId("node-trigger")).toBeVisible();
  await page.evaluate(async () => {
    let previous = "",
      stable = 0;
    for (let frame = 0; frame < 120 && stable < 4; frame++) {
      await new Promise(requestAnimationFrame);
      const value =
        document
          .querySelector(".react-flow__viewport")
          ?.getAttribute("style") || "";
      stable = value === previous ? stable + 1 : 0;
      previous = value;
    }
  });
  const point = await page
    .locator(".react-flow__edge-path")
    .first()
    .evaluate((element: SVGPathElement) => {
      const p = element.getPointAtLength(element.getTotalLength() / 2);
      const matrix = element.getScreenCTM()!;
      return { x: p.x * matrix.a + matrix.e, y: p.y * matrix.d + matrix.f };
    });
  await page.mouse.click(point.x, point.y);
  await expect(
    page.getByRole("heading", { name: "Connection", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Insert node between", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add If / Else", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Ambiguous ports" }),
  ).toBeVisible();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  await page
    .getByRole("button", { name: "Add Set Variable", exact: true })
    .last()
    .click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "3 nodes / 2 connections",
  );
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  const saved = state.records()[0].definition;
  expect(
    saved.edges.some(
      (e: any) => e.source === "trigger" && e.target === "step_1",
    ),
  ).toBe(false);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "3 nodes / 2 connections",
  );
});
test("palette favorites recent nodes cut paste and read-only collapsed inspection", async ({
  page,
}) => {
  const graph = makeGraph(2);
  graph.groups = [
    {
      id: "group_a",
      label: "Protected",
      node_ids: ["trigger", "step_1"],
      position: { x: 0, y: 100 },
      width: 700,
      height: 400,
      collapsed: true,
    },
  ];
  const state = await setupPowerApps(page, {
    records: [fixtureRow(41, graph)],
  });
  await page.goto("/power-apps/automations/41/edit");
  await page
    .getByRole("button", { name: "Favorite Set Variable", exact: true })
    .click();
  await page
    .getByLabel("Node category", { exact: true })
    .selectOption("Favorites");
  await expect(
    page.getByRole("button", { name: "Add Set Variable", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Add Set Variable", exact: true })
    .click();
  await page
    .getByLabel("Node category", { exact: true })
    .selectOption("Recently used");
  await expect(
    page.getByRole("button", { name: "Add Set Variable", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Expand group Protected", exact: true })
    .click();
  await page
    .locator(".react-flow__pane")
    .click({ position: { x: 20, y: 450 } });
  await page.keyboard.press("Control+a");
  page.once("dialog", (d) => d.accept());
  await page.keyboard.press("Control+x");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "0 nodes / 0 connections",
  );
  await page.keyboard.press("Control+v");
  await expect(page.getByTestId("graph-count")).toHaveText(
    "3 nodes / 1 connections",
  );
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  expect(
    new Set(state.records()[0].definition.nodes.map((n: any) => n.id)).size,
  ).toBe(3);
});

test("readonly viewers expand collapsed groups without mutating a draft", async ({
  page,
}) => {
  const graph = makeGraph(2);
  graph.groups = [
    {
      id: "group_a",
      label: "Protected",
      node_ids: ["trigger", "step_1"],
      position: { x: 0, y: 100 },
      width: 700,
      height: 400,
      collapsed: true,
    },
  ];
  const state = await setupPowerApps(page, {
    readOnly: true,
    records: [fixtureRow(41, graph)],
  });
  await page.goto("/power-apps/automations/41/edit");
  await page
    .getByRole("button", { name: "Expand group Protected", exact: true })
    .click();
  await expect(page.getByTestId("node-trigger")).toBeVisible();
  await page
    .locator(".as-overview-nodes")
    .getByRole("button", { name: "Transform 1", exact: true })
    .click();
  await expect(page.getByLabel("Node name", { exact: true })).toHaveAttribute(
    "readonly",
    "",
  );
  expect(state.writes.filter((w) => w.method !== "GET")).toHaveLength(0);
  expect(state.records()[0].definition.groups[0].collapsed).toBe(true);
});
test("subworkflow navigation retains an authorized parent breadcrumb", async ({
  page,
}) => {
  const child = fixtureRow(42, makeGraph(2));
  child.name = "Child workflow";
  const parent = fixtureRow(41, makeGraph(2));
  parent.name = "Parent workflow";
  parent.definition.nodes[1].type = "sub_workflow";
  parent.definition.nodes[1].config = { workflow_id: "42" };
  await setupPowerApps(page, { records: [parent, child] });
  await page.goto("/power-apps/automations/41/edit");
  await page
    .locator(".as-overview-nodes")
    .getByRole("button", { name: "Transform 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Open referenced workflow", exact: true })
    .click();
  await expect(page).toHaveURL(/automations\/42\/edit/);
  await expect(
    page.getByRole("navigation", { name: "Workflow breadcrumbs" }),
  ).toContainText("Parent workflow");
  await page
    .getByRole("navigation", { name: "Workflow breadcrumbs" })
    .getByRole("button", { name: "Parent workflow", exact: true })
    .click();
  await expect(page).toHaveURL(/automations\/41\/edit/);
});
