import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { setupPowerApps, fixtureRow, makeGraph } from "./power-apps-fixtures";
import type { Connector, Connection } from "../frontend/src/apps/power-apps/applications/integrations/integrationApi";
import type { NodeDefinition } from "../frontend/src/apps/power-apps/applications/automations/builder/types";

const backend = path.resolve(__dirname, "../backend");
const venv = path.join(backend, "venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.POWER_TEST_PYTHON || (existsSync(venv) ? venv : process.platform === "win32" ? "python" : "python3");
// Import pure registry metadata. This starts no server and makes no provider calls.
const contracts: { nodes: NodeDefinition[]; connectors: Connector[] } = JSON.parse(execFileSync(python, ["-c",
  "import json; from app.apps.power_apps.node_registry import NODES; from app.apps.power_apps.integrations.registry import catalog; print(json.dumps(dict(nodes=list(NODES.values()),connectors=catalog())))",
], { cwd: backend, encoding: "utf8" }));
test.use({ viewport: { width: 1600, height: 1000 } });

async function setup(page: Page) {
  await setupPowerApps(page, { records: [fixtureRow(41, makeGraph(1))] });
  const creates: Record<string, any>[] = [], probes: Record<string, any>[] = [];
  const connections: Connection[] = [];
  await page.route("**/power-apps/automations/node-catalog*", (route) => route.fulfill({ json: { version: 1, nodes: contracts.nodes } }));
  await page.route("**/power-apps/integrations/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/catalog")) return route.fulfill({ json: { items: contracts.connectors } });
    if (url.pathname.endsWith("/connections")) {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON(); creates.push(body);
        const saved = { id: 91 + connections.length, connector_id: body.connector_id, name: body.name, enabled: true, writes_enabled: body.writes_enabled, health: "pending", revision: 1, scopes: body.scopes, config: body.config };
        connections.push(saved);
        return route.fulfill({ status: 201, json: saved });
      }
      return route.fulfill({ json: { items: connections } });
    }
    if (url.pathname.endsWith("/execute")) {
      probes.push(route.request().postDataJSON());
      return route.fulfill({ json: { output: { data: { ok: true, result: {} } } } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/power-apps/automations/41/edit?environment=development");
  await expect(page.getByTestId("graph-count")).toHaveText("1 nodes / 0 connections");
  return { creates, probes };
}
async function addModule(page: Page, connector: string) {
  const definition = contracts.nodes.find((node) => node.id === "connector_" + connector)!;
  await page.getByLabel("Search node library", { exact: true }).fill(definition.name);
  await page.getByRole("button", { name: "Add " + definition.name, exact: true }).click();
  await expect(page.getByLabel("Integration action", { exact: true })).toBeVisible();
}

test("all registered modules and actions render only their catalog options", async ({ page }) => {
  await setup(page);
  for (const connector of contracts.connectors.filter((c) => c.actions.length)) {
    await addModule(page, connector.id);
    for (const action of connector.actions) {
      await page.getByLabel("Integration action", { exact: true }).selectOption(action.id);
      const fields = Object.values(action.input_schema.properties || {}).filter((schema) => schema.const === undefined);
      const editor = page.getByRole("region", { name: "Integration configuration", exact: true });
      await expect(editor.locator(".ic-field")).toHaveCount(fields.length);
    }
    await page.getByRole("tab", { name: "Module settings", exact: true }).click();
    const settings = page.getByRole("region", { name: connector.name + " module settings", exact: true });
    await expect(settings).toBeVisible();
    const auth = connector.authentication.find((a) => a !== "oauth2") || connector.authentication[0];
    const credentialFields = connector.editor_options!.credentials[auth];
    await expect(settings.locator('input[type="password"],textarea[autocomplete="off"]')).toHaveCount(Object.keys(credentialFields).length);
    if (connector.authentication.length > 1) {
      const select = page.getByLabel("Module authentication", { exact: true });
      await expect(select.locator("option")).toHaveCount(connector.authentication.length);
      await expect(select).toHaveValue(auth);
    } else {
      await expect(page.getByLabel("Module authentication", { exact: true })).toHaveCount(0);
    }
    const properties = connector.editor_options!.config_schema.properties || {};
    await expect(settings.locator(".ic-field")).toHaveCount(Object.keys(properties).filter((key) => key !== "header_name" || auth === "api_key").length);
    const writes = connector.actions.some((a) => a.mutates) || connector.id === "http";
    await expect(settings.locator('input[type="checkbox"]')).toHaveCount(writes ? 1 : 0);
    await page.getByRole("button", { name: "Close configuration", exact: true }).click();
  }
});

test("Razorpay, database and AI connection forms submit module-specific settings", async ({ page }) => {
  const { creates } = await setup(page);
  await addModule(page, "razorpay");
  await page.getByRole("tab", { name: "Module settings", exact: true }).click();
  await page.getByLabel("Razorpay key ID", { exact: true }).fill("fixture_key_id");
  await page.getByLabel("Razorpay key secret", { exact: true }).fill("fixture_secret");
  await page.getByRole("button", { name: "Save connection", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Connection saved securely" })).toBeVisible();
  expect(creates[0].auth_type).toBe("basic");
  expect(creates[0].secrets).toEqual({ username: "fixture_key_id", password: "fixture_secret" });
  await page.getByRole("button", { name: "Close configuration", exact: true }).click();

  await addModule(page, "postgresql");
  await page.getByRole("tab", { name: "Module settings", exact: true }).click();
  await page.getByLabel("Database username", { exact: true }).fill("integration_reader");
  await page.getByLabel("Database password", { exact: true }).fill("fixture_database_password");
  await page.getByLabel("Allowed hostnames", { exact: true }).fill('["db.example.test"]');
  await page.getByLabel("Database name", { exact: true }).fill("external_reporting");
  await page.getByLabel("Approved tables (schema.table)", { exact: true }).fill('["public.events"]');
  await page.getByRole("button", { name: "Save & verify connection", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Connection check completed" })).toBeVisible();
  expect(creates[1].config).toEqual({ hosts: ["db.example.test"], database: "external_reporting", port: 5432, tables: ["public.events"] });
  expect(creates[1].auth_type).toBe("database");
  await page.getByRole("button", { name: "Close configuration", exact: true }).click();

  await addModule(page, "ai_gateway");
  await page.getByRole("tab", { name: "Module settings", exact: true }).click();
  await expect(page.locator('.ic-module-settings input[type="password"]')).toHaveCount(0);
  await expect(page.locator('.ic-module-settings input[type="checkbox"]')).toHaveCount(0);
  await page.getByRole("button", { name: "Save connection", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Connection saved securely" })).toBeVisible();
  expect(creates[2]).toMatchObject({ auth_type: "gateway", secrets: {}, config: { provider: "openai" }, writes_enabled: false });
});

test("HTTP write consent follows the method and native triggers have no credentials", async ({ page }) => {
  await setup(page);
  await page.locator(".as-node").first().click();
  await expect(page.getByText("Credentials / connections", { exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "Settings", exact: true }).click();
  await expect(page.getByRole("option", { name: "Use error branch", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Close configuration", exact: true }).click();
  await addModule(page, "http");
  await expect(page.getByLabel("Authorize this external write when the published workflow runs")).toHaveCount(0);
  await page.getByLabel("Method", { exact: true }).selectOption("POST");
  await expect(page.getByLabel("Authorize this external write when the published workflow runs")).toBeVisible();
  await page.getByLabel("Method", { exact: true }).selectOption("GET");
  await expect(page.getByLabel("Authorize this external write when the published workflow runs")).toHaveCount(0);
});
