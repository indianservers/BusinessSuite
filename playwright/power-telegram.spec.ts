import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
import { setupPowerApps, fixtureRow, makeGraph, nodeCatalog } from "./power-apps-fixtures";
import type { NodeDefinition } from "../frontend/src/apps/power-apps/applications/automations/builder/types";
import type { Connection } from "../frontend/src/apps/power-apps/applications/integrations/integrationApi";

test.use({ viewport: { width: 1600, height: 1000 } });
const telegram: NodeDefinition = {
  ...nodeCatalog[0], id: "connector_telegram", name: "Telegram Bot", category: "Integrations", icon: "Send",
  description: "Send Telegram messages with your bot. Configure its token in Module settings.",
  trigger: false, executable: true, requires_credential: true,
  fields: [{ key: "action", label: "Action", kind: "select", required: true, allow_expression: false, default: "send_message", options: ["test", "send_message"] }],
  inputs: [{ id: "in", label: "In", data_type: "flow", max_connections: 1 }],
  outputs: [{ id: "out", label: "Next", data_type: "flow", max_connections: 1 }],
};
async function setup(page: Page, failure = false, readOnly = false) {
  const graph = makeGraph(1);
  if (readOnly) graph.nodes.push({ ...graph.nodes[0], id: "telegram_fixture", type: "connector_telegram", label: "Telegram Bot", position: { x: 420, y: 220 }, config: { action: "send_message", input: {} } });
  const state = await setupPowerApps(page, { records: [fixtureRow(41, graph)], readOnly });
  let saved: Connection | undefined;
  const creates: Record<string, any>[] = [], probes: Record<string, any>[] = [];
  await page.route("**/power-apps/automations/node-catalog*", (route) => route.fulfill({ json: { version: 1, nodes: [...nodeCatalog, telegram] } }));
  await page.route("**/power-apps/integrations/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/catalog")) return route.fulfill({ json: { items: [{
      id: "telegram", name: "Telegram Bot", category: "Communication", authentication: ["bearer"], setup: [],
      actions: [
        { id: "test", name: "Verify bot", mutates: false, scopes: [], input_schema: { type: "object", properties: {} } },
        { id: "send_message", name: "Send message", mutates: true, scopes: [], input_schema: { type: "object", properties: { chat_id: { type: "string" }, text: { type: "string", maxLength: 4096 } }, required: ["chat_id", "text"] } },
      ],
    }] } });
    if (path.endsWith("/connections")) {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON(); creates.push(body);
        saved = { id: 91, connector_id: "telegram", name: body.name, enabled: true, writes_enabled: body.writes_enabled, health: "pending", revision: 1, scopes: [] };
        return route.fulfill({ status: 201, json: saved });
      }
      return route.fulfill({ json: { items: saved ? [saved] : [] } });
    }
    if (path.endsWith("/connections/91") && route.request().method() === "PUT" && saved) {
      const body = route.request().postDataJSON();
      expect(body.expected_revision).toBe(saved.revision);
      saved = { ...saved, writes_enabled: body.writes_enabled, revision: saved.revision + 1 };
      return route.fulfill({ json: saved });
    }
    if (path.endsWith("/execute")) {
      const body = route.request().postDataJSON(); probes.push(body);
      if (failure) return route.fulfill({ status: 422, json: { detail: { message: "Provider authentication failed" } } });
      if (saved) saved.health = "healthy";
      return route.fulfill({ json: { output: { data: { ok: true, result: body.action_id === "test" ? { username: "fixture_bot", is_bot: true } : { message_id: 42 } } } } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/power-apps/automations/41/edit?environment=development");
  await expect(page.getByTestId("graph-count")).toHaveText(`${graph.nodes.length} nodes / 0 connections`);
  return { state, creates, probes };
}

test("Telegram module saves a secret reference, verifies the bot and explicitly tests a message", async ({ page }, info) => {
  const { state, creates, probes } = await setup(page);
  await page.getByLabel("Search node library", { exact: true }).fill("Telegram");
  await page.getByRole("button", { name: "Add Telegram Bot", exact: true }).click();
  await page.getByRole("tab", { name: "Module settings", exact: true }).click();
  const token = "123456789:fixture_token_for_browser_only";
  await expect(page.getByLabel("Telegram bot token", { exact: true })).toHaveAttribute("type", "password");
  await page.getByLabel("Telegram bot token", { exact: true }).fill(token);
  await page.getByRole("button", { name: "Save & verify connection", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Bot verified: @fixture_bot" })).toBeVisible();
  await expect(page.getByLabel("Telegram bot token", { exact: true })).toHaveValue("");
  expect(creates).toHaveLength(1);
  expect(creates[0].secrets).toEqual({ access_token: token });
  expect(probes[0]).toMatchObject({ action_id: "test", input: {}, confirm_side_effect: false });
  await page.getByLabel("Enable writes for saved module connection", { exact: true }).check();
  await expect(page.getByRole("status").filter({ hasText: "Sending enabled for this connection" })).toBeVisible();
  await page.screenshot({ path: info.outputPath("telegram-module-settings.png"), fullPage: true });
  await page.getByRole("tab", { name: "Parameters", exact: true }).click();
  await expect(page.getByLabel("Integration connection", { exact: true })).toHaveValue("91");
  await page.getByLabel("Chat ID", { exact: true }).fill("-1001234");
  await page.getByLabel("Message", { exact: true }).fill("Hello from Business Suite");
  await expect(page.getByRole("button", { name: "Send test message", exact: true })).toBeDisabled();
  await page.getByLabel("Send this test message to the specified chat now", { exact: true }).check();
  await page.getByRole("button", { name: "Send test message", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Test message sent successfully" })).toBeVisible();
  expect(probes[1]).toMatchObject({ action_id: "send_message", input: { chat_id: "-1001234", text: "Hello from Business Suite" }, confirm_side_effect: true });
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  expect(JSON.stringify(state.records())).not.toContain(token);
  expect(state.records()[0].definition.nodes.find((n: any) => n.type === "connector_telegram")?.credential_reference).toBe("91");
});

test("Telegram verification failures keep secrets out of the workflow", async ({ page }) => {
  const { state } = await setup(page, true);
  await page.getByRole("button", { name: "Add Telegram Bot", exact: true }).click();
  await page.getByRole("tab", { name: "Module settings", exact: true }).click();
  await page.getByLabel("Telegram bot token", { exact: true }).fill("123456789:fixture_invalid_token");
  await page.getByRole("button", { name: "Save & verify connection", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Provider authentication failed" })).toBeVisible();
  await expect(page.getByLabel("Telegram bot token", { exact: true })).toHaveValue("");
  expect(JSON.stringify(state.records())).not.toContain("fixture_invalid_token");
});

test("read-only Telegram settings hide token entry and disable test sends", async ({ page }) => {
  const { creates, probes } = await setup(page, false, true);
  await page.getByTestId("node-telegram_fixture").click();
  await expect(page.getByRole("button", { name: "Send test message", exact: true })).toBeDisabled();
  await page.getByRole("tab", { name: "Module settings", exact: true }).click();
  await expect(page.getByLabel("Telegram bot token", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save & verify connection", exact: true })).toHaveCount(0);
  expect(creates).toHaveLength(0);
  expect(probes).toHaveLength(0);
});
