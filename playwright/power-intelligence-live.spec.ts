import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
async function session(page: Page, index = 0) {
  const manifest = JSON.parse(
    await fs.readFile(
      path.resolve(__dirname, "../.tmp/power-studio-live-session.json"),
      "utf8",
    ),
  );
  const actor = manifest.users[index];
  const response = await page.request.get(manifest.api + "/access/me", {
    headers: { Authorization: "Bearer " + actor.token },
  });
  expect(response.ok()).toBe(true);
  const access = await response.json();
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
              name: "Isolated QA user",
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
  return { manifest, actor };
}
import scenarios from "../backend/tests/fixtures/power_studio_scenarios.json";
const root = "/power-apps/automations";
async function focus(page: Page, id: string) {
  await page.keyboard.press("Control+f");
  await page.getByLabel("Search workflow nodes", { exact: true }).fill(id);
  await page.locator(".as-workflow-search>div button").first().click();
}
for (const scenario of scenarios)
  test(`intelligent scenario ${scenario.id}: ${scenario.name}`, async ({
    page,
  }, info) => {
    test.setTimeout(150000);
    const { manifest, actor } = await session(page);
    const headers = { Authorization: "Bearer " + actor.token };
    const response = await page.request.post(manifest.api + root, {
      headers,
      data: {
        name: `Intelligence ${scenario.id}`,
        description: "Isolated design-time scenario",
        definition: scenario.definition,
      },
    });
    expect(response.status(), await response.text()).toBe(201);
    const row = await response.json();
    const errors: string[] = [],
      consoleErrors: string[] = [],
      externalRequests: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error") consoleErrors.push(m.text());
    });
    page.on("request", (request) => {
      if (/\/api\/v1\/(?:pms|crm|employees|interns-hub)\//.test(request.url()))
        externalRequests.push(request.url());
    });
    await page.goto(`/power-apps/automations/${row.id}/edit`);
    await expect(page.getByTestId("graph-count")).toHaveText(
      `${scenario.definition.nodes.length} nodes / ${scenario.definition.edges.length} connections`,
    );
    await focus(page, scenario.expected_node);
    await page
      .getByLabel("Node description", { exact: true })
      .fill("Reviewed synthetic scenario");
    await page.getByLabel("Node description", { exact: true }).blur();
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await page
      .getByRole("button", { name: "Open authoring tools", exact: true })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Intelligent automation studio" }),
    ).toBeVisible();
    const tool = page.getByRole("dialog", {
      name: "Intelligent automation studio",
    });
    const definition = (
      await (
        await page.request.get(manifest.api + root + "/node-catalog", {
          headers,
        })
      ).json()
    ).nodes.find(
      (n: any) =>
        n.id ===
        scenario.definition.nodes.find((n) => n.id === scenario.expected_node)!
          .type,
    );
    const field = definition.fields[0];
    const mappedValue =
      scenario.id === "B"
        ? "Design-time task title"
        : scenario.expected_output.value;
    await tool
      .locator(".ai-mapping-grid>div")
      .last()
      .getByRole("button")
      .first()
      .click();
    await tool
      .getByRole("button", { name: "Constant value", exact: true })
      .click();
    while (
      await tool
        .getByRole("button", { name: "Remove transformation", exact: true })
        .count()
    )
      await tool
        .getByRole("button", { name: "Remove transformation", exact: true })
        .first()
        .click();
    await tool
      .getByLabel("Mapping constant JSON", { exact: true })
      .fill(JSON.stringify(mappedValue));
    await tool
      .getByRole("button", { name: "Preview mapping", exact: true })
      .click();
    await expect(
      tool.getByLabel("Mapping preview result", { exact: true }),
    ).toBeVisible();
    await tool
      .getByRole("button", { name: "Apply validated mapping", exact: true })
      .click();
    await tool
      .getByRole("button", { name: "Reusable blocks", exact: true })
      .click();
    await tool
      .getByLabel("Block name", { exact: true })
      .fill(`Scenario ${scenario.id} reusable`);
    const output = Object.keys(definition.output_schema)[0];
    await tool
      .getByLabel("Block input output contract JSON", { exact: true })
      .fill(
        JSON.stringify({
          inputs: [
            {
              name: "input",
              node_id: scenario.expected_node,
              field: field.key,
              data_type: "any",
              default: mappedValue,
            },
          ],
          outputs: [
            {
              name: "output",
              node_id: scenario.expected_node,
              field: output,
              data_type: "any",
              default: null,
            },
          ],
        }),
      );
    await tool
      .getByRole("button", { name: "Save selection as block", exact: true })
      .click();
    await tool
      .getByRole("button")
      .filter({ hasText: `Scenario ${scenario.id} reusable` })
      .click();
    await expect(
      tool.getByLabel("Block version", { exact: true }),
    ).toBeVisible();
    await tool
      .getByRole("button", { name: "Insert pinned block version", exact: true })
      .click();
    await expect(page.getByTestId("graph-count")).toContainText(
      `${scenario.definition.nodes.length + 1} nodes`,
    );
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await tool.getByRole("button", { name: "Templates", exact: true }).click();
    await expect(tool.locator(".ai-template-grid>button")).toHaveCount(39);
    await tool.locator(".ai-template-grid>button").first().click();
    await expect(
      tool.getByRole("img", { name: "Proposed workflow graph", exact: true }),
    ).toBeVisible();
    page.once("dialog", (d) => d.accept());
    await tool
      .getByRole("button", { name: "Use reviewed template", exact: true })
      .click();
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await tool
      .getByRole("button", { name: "Import / export", exact: true })
      .click();
    const downloadEvent = page.waitForEvent("download");
    await tool
      .getByRole("button", { name: "Export portable workflow", exact: true })
      .click();
    const exported = await downloadEvent;
    const exportedPath = info.outputPath("workflow.json");
    await exported.saveAs(exportedPath);
    const portable = JSON.parse(await fs.readFile(exportedPath, "utf8"));
    expect(portable.definition.nodes.length).toBe(
      scenario.definition.nodes.length,
    );
    expect(
      portable.definition.nodes.every((n: any) => !n.credential_reference),
    ).toBe(true);
    await tool
      .getByLabel("Import workflow JSON", { exact: true })
      .fill(JSON.stringify(portable));
    await tool
      .getByRole("button", { name: "Validate import preview", exact: true })
      .click();
    await expect(
      tool.getByRole("button", { name: "Apply reviewed import", exact: true }),
    ).toBeEnabled();
    page.once("dialog", (d) => d.accept());
    await tool
      .getByRole("button", { name: "Apply reviewed import", exact: true })
      .click();
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await tool.getByRole("button", { name: "Simulation", exact: true }).click();
    await tool
      .getByLabel("Simulation input JSON", { exact: true })
      .fill(JSON.stringify(scenario.input));
    await tool
      .getByLabel("Explicit synthetic node outputs JSON", { exact: true })
      .fill(JSON.stringify(scenario.synthetic));
    await tool
      .getByRole("button", { name: "Prepare safe simulation", exact: true })
      .click();
    await expect(
      tool.getByText("Structurally valid · local simulation prepared", {
        exact: true,
      }),
    ).toBeVisible();
    await tool
      .getByRole("button", { name: "Step through", exact: true })
      .click();
    await expect(
      tool.locator(".ai-debug-grid>div").first().getByRole("button"),
    ).toHaveCount(1);
    await tool
      .getByRole("button", { name: "Inspect all", exact: true })
      .click();
    await expect(
      tool.locator(".ai-debug-grid>div").first().getByRole("button"),
    ).toHaveCount(scenario.definition.nodes.length);
    const reportEvent = page.waitForEvent("download");
    await tool
      .getByRole("button", { name: "Export debug report", exact: true })
      .click();
    const report = await reportEvent;
    const reportPath = info.outputPath("debug.json");
    await report.saveAs(reportPath);
    const debug = JSON.parse(await fs.readFile(reportPath, "utf8"));
    expect(debug.integration_execution).toBe(false);
    expect(
      debug.timeline.find((e: any) => e.node_id === scenario.expected_node)
        .output,
    ).toEqual(scenario.expected_output);
    if (scenario.id === "E")
      await page.screenshot({
        path: info.outputPath("intelligent-simulation.png"),
        fullPage: true,
      });
    await tool
      .getByRole("button", { name: "Documentation", exact: true })
      .click();
    await expect(
      tool.getByRole("button", { name: "Export documentation", exact: true }),
    ).toBeVisible();
    await tool.getByRole("button", { name: "Quality", exact: true }).click();
    await expect(
      tool.getByRole("heading", { name: /Design quality/ }),
    ).toBeVisible();
    await tool
      .getByRole("button", { name: "Close authoring studio", exact: true })
      .click();
    await page.getByRole("button", { name: "Save draft", exact: true }).click();
    await expect(page.locator(".as-save-status")).toContainText("Saved");
    await page.reload();
    await expect(page.getByTestId("graph-count")).toHaveText(
      `${scenario.definition.nodes.length} nodes / ${scenario.definition.edges.length} connections`,
    );
    const persisted = (
      await (
        await page.request.get(`${manifest.api}${root}/${row.id}`, { headers })
      ).json()
    ).definition;
    expect(new Set(persisted.nodes.map((n: any) => n.id)).size).toBe(
      persisted.nodes.length,
    );
    expect(
      persisted.nodes.find((n: any) => n.id === scenario.expected_node)
        .mappings[field.key],
    ).toBeTruthy();
    expect(
      persisted.edges.map((e: any) => [e.source, e.source_port, e.target]),
    ).toEqual(
      scenario.definition.edges.map((e) => [e.source, e.source_port, e.target]),
    );
    expect(
      (
        await page.request.get(`${manifest.api}${root}/${row.id}`, {
          headers: { Authorization: "Bearer " + manifest.users[2].token },
        })
      ).status(),
    ).toBe(404);
    expect(
      (
        await page.request.put(`${manifest.api}${root}/${row.id}`, {
          headers: { Authorization: "Bearer " + manifest.users[1].token },
          data: { name: "Denied", definition: persisted, expected_version: 1 },
        })
      ).status(),
    ).toBe(403);
    expect(
      (
        await page.request.post(`${manifest.api}${root}/${row.id}/publish`, {
          headers,
          data: {
            expected_version: (
              await (
                await page.request.get(`${manifest.api}${root}/${row.id}`, {
                  headers,
                })
              ).json()
            ).version,
          },
        })
      ).status(),
    ).toBe(409);
    expect(errors).toEqual([]);
    expect(consoleErrors).toEqual([]);
    expect(externalRequests).toEqual([]);
  });
test("AI unavailable stays honest and a labeled proposal fixture requires explicit approval", async ({
  page,
}) => {
  const { manifest, actor } = await session(page);
  const headers = { Authorization: "Bearer " + actor.token };
  const scenario = scenarios[0];
  const created = await page.request.post(manifest.api + root, {
    headers,
    data: { name: "AI review QA", definition: scenario.definition },
  });
  const row = await created.json();
  await page.goto(`/power-apps/automations/${row.id}/edit`);
  await page
    .getByRole("button", { name: "Create with AI", exact: true })
    .click();
  const tool = page.getByRole("dialog", {
    name: "Intelligent automation studio",
  });
  await tool
    .getByLabel("Describe your workflow", { exact: true })
    .fill("Explain this synthetic approval design");
  await tool
    .getByRole("button", { name: "Generate proposal", exact: true })
    .click();
  await expect(tool.getByRole("alert")).toBeVisible();
  await expect(
    tool.getByRole("button", {
      name: "Approve and apply proposal",
      exact: true,
    }),
  ).toHaveCount(0);
  const proposal = scenarios[2].definition;
  await page.route("**/power-apps/automations/ai/propose*", (route) =>
    route.fulfill({
      json: {
        summary: "Explicit UI test proposal fixture",
        findings: ["Synthetic proposal supplied only by this browser test"],
        definition: proposal,
        validation: {
          valid: true,
          issues: [],
          executable: false,
          node_count: proposal.nodes.length,
          edge_count: proposal.edges.length,
          catalog_version: 1,
        },
        requires_approval: true,
      },
    }),
  );
  await tool
    .getByRole("button", { name: "Generate proposal", exact: true })
    .click();
  await expect(
    tool.getByText("Explicit UI test proposal fixture", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("graph-count")).toContainText(
    `${scenario.definition.nodes.length} nodes`,
  );
  page.once("dialog", (d) => d.accept());
  await tool
    .getByRole("button", { name: "Approve and apply proposal", exact: true })
    .click();
  await expect(page.getByTestId("graph-count")).toContainText(
    `${proposal.nodes.length} nodes`,
  );
});

test("visual logic router loop merge and recommendation controls persist", async ({
  page,
}, info) => {
  test.setTimeout(120000);
  const { manifest, actor } = await session(page);
  const headers = { Authorization: "Bearer " + actor.token };
  await page.goto("/power-apps/automations/new");
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Visual logic tools QA");
  await page
    .getByRole("button", { name: "Add Manual Trigger", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add If / Else", exact: true })
    .click();
  await page
    .locator(".as-config summary")
    .filter({ hasText: "Visual logic builder" })
    .click();
  await page.getByRole("button", { name: "Add rule", exact: true }).click();
  await page.getByLabel("Rule 1 right", { exact: true }).fill("1000");
  await page
    .getByRole("button", { name: "Add nested group", exact: true })
    .click();
  await page
    .getByLabel("Condition join level 1", { exact: true })
    .selectOption("or");
  await page.getByRole("button", { name: "Add Switch", exact: true }).click();
  await page
    .locator(".as-config summary")
    .filter({ hasText: "Visual logic builder" })
    .click();
  await page
    .getByRole("button", { name: "Add named branch", exact: true })
    .click();
  await page.getByLabel("Branch 1 label", { exact: true }).fill("Critical");
  await page.getByLabel("Branch 1 match", { exact: true }).fill("Critical");
  await page
    .getByLabel("Routing value", { exact: true })
    .fill("{{trigger.record.priority}}");
  await page
    .getByRole("button", { name: "Add named branch", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByLabel("From node", { exact: true })
    .selectOption({ label: "Switch" });
  await expect(
    page.getByLabel("Output port", { exact: true }).locator("option").first(),
  ).toHaveText("Critical");
  await page
    .getByLabel("To node", { exact: true })
    .selectOption({ label: "If / Else" });
  await page
    .getByRole("button", { name: "Connect nodes", exact: true })
    .click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "3 nodes / 1 connections",
  );
  await page.getByRole("button", { name: "Add Loop", exact: true }).click();
  await page
    .locator(".as-config summary")
    .filter({ hasText: "Visual logic builder" })
    .click();
  await page
    .getByLabel("Loop mode", { exact: true })
    .selectOption("bounded_parallel");
  await page.getByLabel("concurrency", { exact: true }).fill("3");
  await page.getByLabel("max_iterations", { exact: true }).fill("5");
  await page.getByLabel("Loop timeout", { exact: true }).fill("120");
  await page.getByRole("button", { name: "Add Merge", exact: true }).click();
  await page
    .locator(".as-config summary")
    .filter({ hasText: "Visual logic builder" })
    .click();
  await page
    .getByRole("group", { name: "Join semantics", exact: true })
    .getByLabel("Merge strategy", { exact: true })
    .selectOption("keyed");
  await page.getByLabel("Merge keys", { exact: true }).fill("not-json");
  await expect(page.locator(".as-config").getByRole("alert")).toBeVisible();
  await page.getByLabel("Merge keys", { exact: true }).fill('["left","right"]');
  await expect(page.locator(".as-config").getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await expect(page).toHaveURL(/automations\/\d+\/edit/);
  const id = Number(/automations\/(\d+)/.exec(page.url())![1]);
  const saved = (
    await (
      await page.request.get(`${manifest.api}${root}/${id}`, { headers })
    ).json()
  ).definition;
  expect(
    saved.nodes.find((n: any) => n.type === "if_else").config.condition.rules
      .length,
  ).toBe(2);
  expect(
    saved.nodes.find((n: any) => n.type === "switch").config.routes[0].label,
  ).toBe("Critical");
  expect(
    saved.nodes.find((n: any) => n.type === "loop").config.concurrency,
  ).toBe(3);
  expect(saved.nodes.find((n: any) => n.type === "merge").config.keys).toEqual([
    "left",
    "right",
  ]);
  await page.reload();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "5 nodes / 1 connections",
  );
  const trigger = saved.nodes.find((n: any) => n.type === "manual_trigger");
  await focus(page, trigger.id);
  await page
    .locator(".as-config summary")
    .filter({ hasText: "Recommended next steps" })
    .click();
  const recommendations = page.getByRole("region", {
    name: "Recommended next nodes",
  });
  await page.locator(".ai-recommendations button").first().click();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "6 nodes / 2 connections",
  );
});
