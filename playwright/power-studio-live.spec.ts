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
test("real API save reload preview version snapshots and tenant authorization", async ({
  page,
}, info) => {
  const { manifest, actor } = await session(page);
  await page.goto("/power-apps/automations/new");
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Real API draft QA");
  await page
    .getByRole("button", { name: "Add Manual Trigger", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add Set Variable", exact: true })
    .click();
  await page.getByLabel("Value", { exact: true }).fill("{{trigger.record.id}}");
  await page
    .getByRole("button", { name: "Close configuration", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "From node", exact: true })
    .selectOption({ label: "Manual Trigger" });
  await page
    .getByRole("combobox", { name: "To node", exact: true })
    .selectOption({ label: "Set Variable" });
  await page
    .getByRole("button", { name: "Connect nodes", exact: true })
    .click();
  await page.getByRole("button", { name: "Auto layout", exact: true }).click();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await expect(page).toHaveURL(/automations\/\d+\/edit/);
  const id = Number(/automations\/(\d+)/.exec(page.url())![1]);
  await page.reload();
  await expect(page.getByTestId("graph-count")).toHaveText(
    "2 nodes / 1 connections",
  );
  await page.getByRole("button", { name: "Validate", exact: true }).click();
  await expect(
    page.getByText("Structure is valid", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Test workflow", exact: true })
    .click();
  await page
    .getByLabel("Test input / JSON", { exact: true })
    .fill('{"record":{"id":42}}');
  await page
    .getByRole("button", { name: "Preview locally", exact: true })
    .click();
  await expect(page.locator(".as-preview-timeline>button")).toHaveCount(2);
  await page.locator(".as-preview-timeline>button").last().click();
  await expect(page.locator(".as-preview-inspect")).toContainText("42");
  const headers = { Authorization: "Bearer " + actor.token };
  const versions = await page.request.get(
    `${manifest.api}/power-apps/automations/${id}/versions`,
    { headers },
  );
  expect((await versions.json()).items.length).toBeGreaterThan(0);
  const overview = await page.request.get(
    manifest.api + "/power-apps/overview",
    { headers },
  );
  expect((await overview.json()).counts.workflow_executions).toBe(0);
  const publish = await page.request.post(
    `${manifest.api}/power-apps/automations/${id}/publish`,
    {
      headers,
      data: {
        expected_version: (
          await (
            await page.request.get(
              `${manifest.api}/power-apps/automations/${id}`,
              { headers },
            )
          ).json()
        ).version,
      },
    },
  );
  expect(publish.status()).toBe(409);
  const other = manifest.users[2];
  const unauthorized = await page.request.get(
    `${manifest.api}/power-apps/automations/${id}`,
    { headers: { Authorization: "Bearer " + other.token } },
  );
  expect(unauthorized.status()).toBe(404);
  await page.screenshot({
    path: info.outputPath("studio-real-api-preview.png"),
    fullPage: true,
  });
});
test("real API read-only reviewer can inspect but cannot save", async ({
  page,
}) => {
  const { manifest, actor } = await session(page, 1);
  const builder = manifest.users[0];
  const created = await page.request.post(
    manifest.api + "/power-apps/automations",
    {
      headers: { Authorization: "Bearer " + builder.token },
      data: {
        name: "Reviewer QA",
        definition: { schema_version: 2, nodes: [], edges: [] },
      },
    },
  );
  expect(created.status()).toBe(201);
  const row = await created.json();
  await page.goto(`/power-apps/automations/${row.id}/edit`);
  await expect(
    page.getByRole("button", { name: "Save draft", exact: true }),
  ).toBeDisabled();
  const rejected = await page.request.put(
    `${manifest.api}/power-apps/automations/${row.id}`,
    {
      headers: { Authorization: "Bearer " + actor.token },
      data: {
        name: "Not allowed",
        expected_version: row.version,
        definition: row.definition,
      },
    },
  );
  expect(rejected.status()).toBe(403);
});

const premiumCases = [
  "simple",
  "condition",
  "parallel",
  "approval",
  "error",
  "50 nodes",
  "100 nodes",
  "groups and annotations",
  "variables",
  "invalid connection",
];
for (const scenario of premiumCases)
  test(`premium real application: ${scenario}`, async ({ page }, info) => {
    test.setTimeout(90000);
    const { manifest, actor } = await session(page);
    const headers = { Authorization: "Bearer " + actor.token };
    const catalog = (
      await (
        await page.request.get(
          manifest.api + "/power-apps/automations/node-catalog",
          { headers },
        )
      ).json()
    ).nodes;
    const make = (
      id: string,
      type: string,
      config: Record<string, unknown> = {},
    ) => ({
      id,
      type,
      label: catalog.find((n: any) => n.id === type).name,
      description: "",
      position: { x: 80 + Number(id.replace(/\D/g, "") || 0) * 300, y: 160 },
      config: {
        ...Object.fromEntries(
          catalog
            .find((n: any) => n.id === type)
            .fields.filter((f: any) => "default" in f)
            .map((f: any) => [f.key, f.default]),
        ),
        ...config,
      },
      advanced: {
        retry_attempts: 3,
        error_strategy: "stop",
        timeout_seconds: 60,
      },
      credential_reference: null,
    });
    const link = (
      source: string,
      target: string,
      port = "out",
      target_port = "in",
    ) => ({
      id: `e_${source}_${port}_${target}`,
      source,
      target,
      source_port: port,
      target_port,
      label: port === "out" ? "" : port,
      style: "orthogonal",
    });
    let nodes = [
        make("n0", "manual_trigger"),
        make("n1", "set_variable", { value: "Welcome" }),
      ],
      edges = [link("n0", "n1")];
    if (scenario === "condition") {
      nodes = [
        nodes[0],
        make("n1", "if_else", {
          left: "{{trigger.record.status}}",
          right: "Open",
        }),
        make("n2", "set_variable", { value: "Yes" }),
        make("n3", "set_variable", { value: "No" }),
      ];
      nodes[3].position.y = 400;
      edges = [
        link("n0", "n1"),
        link("n1", "n2", "true"),
        link("n1", "n3", "false"),
      ];
    }
    if (scenario === "parallel") {
      nodes = [
        nodes[0],
        make("n1", "parallel_branch"),
        make("n2", "set_variable", { value: "A" }),
        make("n3", "set_variable", { value: "B" }),
      ];
      nodes[3].position.y = 400;
      edges = [
        link("n0", "n1"),
        link("n1", "n2", "route_1"),
        link("n1", "n3", "route_2"),
      ];
    }
    if (scenario === "approval") {
      const kind = catalog.find((n: any) => n.category === "Approvals").id;
      nodes = [nodes[0], make("n1", kind)];
    }
    if (scenario === "error") {
      nodes.push(make("n2", "error_handler"));
      edges.push(link("n1", "n2", "error", "in"));
    }
    if (scenario === "50 nodes" || scenario === "100 nodes") {
      const count = scenario === "50 nodes" ? 50 : 100;
      nodes = Array.from({ length: count }, (_, i) =>
        make(
          `n${i}`,
          i ? "set_variable" : "manual_trigger",
          i ? { value: String(i) } : {},
        ),
      );
      edges = nodes.slice(1).map((n, i) => link(`n${i}`, n.id));
    }
    if (scenario === "variables")
      nodes[1].config.value = "{{workflow.variables.greeting}} / {{env.name}}";
    const definition: any = {
      schema_version: 2,
      catalog_version: 1,
      nodes,
      edges,
      viewport: { x: 20, y: 15, zoom: 0.8 },
      settings: {
        max_attempts: 4,
        retry_backoff_seconds: 90,
        idempotency: "request_id",
        execution_identity: "owner",
        timezone: "Asia/Kolkata",
        retention_days: 30,
      },
      groups: [],
      annotations: [],
      tags: ["Phase 2.A", scenario],
      variables: { greeting: "Welcome" },
      editor: { snap_to_grid: false, connection_style: "orthogonal" },
    };
    if (scenario === "groups and annotations") {
      definition.groups = [
        {
          id: "group_test",
          label: "Onboarding",
          node_ids: ["n0", "n1"],
          position: { x: 30, y: 100 },
          width: 650,
          height: 300,
          collapsed: true,
        },
      ];
      definition.annotations = [
        {
          id: "note_test",
          kind: "note",
          text: "<b>Plain text</b> — review before Phase 3",
          position: { x: 100, y: 450 },
          width: 240,
        },
      ];
    }
    if (scenario === "invalid connection") {
      const rejected = await page.request.post(
        manifest.api + "/power-apps/automations",
        {
          headers,
          data: {
            name: "Invalid should never save",
            definition: { ...definition, edges: [...edges, link("n1", "n0")] },
          },
        },
      );
      expect(rejected.status()).toBe(422);
    }
    const response = await page.request.post(
      manifest.api + "/power-apps/automations",
      {
        headers,
        data: {
          name: `Premium QA ${scenario}`,
          description: "Isolated design-time test",
          definition,
        },
      },
    );
    expect(response.status(), await response.text()).toBe(201);
    const row = await response.json();
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`/power-apps/automations/${row.id}/edit`);
    await expect(page.getByTestId("graph-count")).toHaveText(
      `${nodes.length} nodes / ${edges.length} connections`,
    );
    if (scenario === "groups and annotations")
      await page
        .getByRole("button", { name: "Expand group Onboarding", exact: true })
        .click();
    await page
      .getByRole("button", { name: "Collapse node library", exact: true })
      .click();
    await page
      .getByLabel("Automation name", { exact: true })
      .fill(`Edited ${scenario}`);
    await page.getByLabel("Automation name", { exact: true }).blur();
    await page.keyboard.press("Control+z");
    await expect(
      page.getByLabel("Automation name", { exact: true }),
    ).toHaveValue(`Premium QA ${scenario}`);
    await page.keyboard.press("Control+Shift+z");
    await expect(
      page.getByLabel("Automation name", { exact: true }),
    ).toHaveValue(`Edited ${scenario}`);
    await page.keyboard.press("Control+f");
    await page.getByLabel("Search workflow nodes", { exact: true }).fill("n1");
    await page.locator(".as-workflow-search>div button").first().click();
    await expect(page.getByLabel("Node name", { exact: true })).toBeVisible();
    await page
      .getByLabel("Node description", { exact: true })
      .fill("Inspected and edited in browser");
    await page.getByRole("button", { name: "Save draft", exact: true }).click();
    await expect(page.locator(".as-save-status")).toContainText("Saved");
    await page.reload();
    await expect(page.getByTestId("graph-count")).toHaveText(
      `${nodes.length} nodes / ${edges.length} connections`,
    );
    const saved = (
      await (
        await page.request.get(
          `${manifest.api}/power-apps/automations/${row.id}`,
          { headers },
        )
      ).json()
    ).definition;
    expect(new Set(saved.nodes.map((n: any) => n.id)).size).toBe(nodes.length);
    expect(saved.nodes.map((n: any) => n.position)).toEqual(
      nodes.map((n) => n.position),
    );
    expect(saved.nodes[1].description).toBe("Inspected and edited in browser");
    expect(saved.edges).toEqual(edges);
    expect(saved.settings).toEqual(definition.settings);
    expect(saved.annotations).toEqual(definition.annotations);
    expect(saved.tags).toEqual(definition.tags);
    expect(saved.variables).toEqual(definition.variables);
    expect(saved.editor).toEqual(definition.editor);
    expect(saved.groups.map((g: any) => ({ ...g, collapsed: false }))).toEqual(
      definition.groups.map((g: any) => ({ ...g, collapsed: false })),
    );
    for (const edge of saved.edges)
      expect(
        saved.nodes.some((n: any) => n.id === edge.source) &&
          saved.nodes.some((n: any) => n.id === edge.target),
      ).toBe(true);
    const readonlyHeaders = {
      Authorization: "Bearer " + manifest.users[1].token,
    };
    const denied = await page.request.put(
      `${manifest.api}/power-apps/automations/${row.id}`,
      {
        headers: readonlyHeaders,
        data: {
          name: "Unauthorized",
          definition: saved,
          expected_version: row.version,
        },
      },
    );
    expect(denied.status()).toBe(403);
    expect(errors).toEqual([]);
    expect(consoleErrors).toEqual([]);
    if (scenario === "groups and annotations") {
      await page
        .getByRole("button", { name: "Collapse node library", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Toggle inspector", exact: true })
        .click();
      await page.screenshot({
        path: info.outputPath("premium-groups.png"),
        fullPage: true,
      });
    }
  });
