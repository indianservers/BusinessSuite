import {
  test,
  expect,
  type Page,
} from "../frontend/node_modules/playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
async function setup(page: Page) {
  const manifest = JSON.parse(
    await fs.readFile(
      path.resolve(__dirname, "../.tmp/power-approvals-live-session.json"),
      "utf8",
    ),
  );
  const actor = manifest.users[0];
  const headers = { Authorization: `Bearer ${actor.token}` };
  const access = await (
    await page.request.get(manifest.api + "/access/me", { headers })
  ).json();
  await page.addInitScript(
    ({ actor, access }) => {
      sessionStorage.setItem(
        "hrms-auth",
        JSON.stringify({
          state: {
            accessToken: actor.token,
            refreshToken: "isolated-browser-session",
            isAuthenticated: true,
            user: {
              id: actor.id,
              email: actor.email,
              role: actor.role,
              is_superuser: false,
              access,
            },
          },
          version: 0,
        }),
      );
    },
    { actor, access },
  );
  return { manifest, headers };
}

test("forty-plus integrations, encrypted connection setup and mobile gallery", async ({
  page,
}) => {
  const { manifest, headers } = await setup(page);
  const catalog = await (
    await page.request.get(manifest.api + "/power-apps/integrations/catalog", {
      headers,
    })
  ).json();
  expect(catalog.items.length).toBeGreaterThanOrEqual(40);
  await page.goto("/power-apps/connectors");
  await expect(
    page.getByRole("heading", { name: "Integration Studio", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".ic-card")).toHaveCount(catalog.items.length);
  await page.screenshot({ path: "../docs/qa/integrations-desktop.png" });
  for (const provider of ["Google Sheets", "Google Forms", "Groq"]) {
    await page
      .getByRole("textbox", { name: "Search integrations" })
      .fill(provider);
    await expect(page.locator(".ic-card")).toHaveCount(1);
  }
  await page
    .locator(".ic-card")
    .getByRole("button", { name: "Connect account" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Connect account" });
  await dialog
    .getByLabel("Connection name")
    .fill("QA Groq account - no live credential");
  await dialog
    .getByLabel("access token", { exact: true })
    .fill("qa-only-placeholder-not-live");
  await dialog.getByRole("button", { name: "Save connection" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .locator(".ic-connections")
      .getByText("QA Groq account - no live credential"),
  ).toBeVisible();
  const connections = await (
    await page.request.get(
      manifest.api + "/power-apps/integrations/connections",
      { headers },
    )
  ).json();
  expect(JSON.stringify(connections)).not.toContain(
    "qa-only-placeholder-not-live",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: "../docs/qa/integrations-mobile.png" });
});

test("webhook starter adds provider modules and guided account fields to canvas", async ({
  page,
}) => {
  const { manifest, headers } = await setup(page);
  await page.goto("/power-apps/connectors");
  await page
    .getByRole("button", { name: "Webhook > Groq > Slack", exact: true })
    .click();
  await expect(page).toHaveURL(/\/power-apps\/automations\/\d+\/edit/);
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await page.locator(".react-flow__node").filter({ hasText: "Groq" }).click();
  await expect(
    page.getByRole("combobox", { name: "Integration action" }),
  ).toBeVisible();
  await expect(page.locator(".as-runtime-label")).toHaveText(
    "Runtime executor available",
  );
  await page
    .getByRole("combobox", { name: "Integration action" })
    .selectOption("generate_text");
  await expect(page.getByLabel("Prompt", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Manage connections / add account" }),
  ).toBeVisible();
  await page.getByLabel("Model ID", { exact: true }).fill("qa-fixture-model");
  await page
    .getByLabel("Prompt", { exact: true })
    .fill("{{trigger.input.message}}");
  const connections = await (
    await page.request.get(
      manifest.api + "/power-apps/integrations/connections",
      { headers },
    )
  ).json();
  const connection = connections.items.find(
    (c: { connector_id: string }) => c.connector_id === "groq",
  );
  await page
    .getByRole("combobox", { name: "Integration connection" })
    .selectOption(String(connection.id));
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  const id = page.url().match(/automations\/(\d+)\/edit/)?.[1];
  await expect
    .poll(async () => {
      const row = await (
        await page.request.get(manifest.api + "/power-apps/automations/" + id, {
          headers,
        })
      ).json();
      const n = row.definition.nodes.find(
        (n: { id: string }) => n.id === "action_1",
      );
      return {
        connection: n.credential_reference,
        model: n.config.input.model,
      };
    })
    .toEqual({ connection: String(connection.id), model: "qa-fixture-model" });
  await page.screenshot({ path: "../docs/qa/integrations-canvas.png" });
  const nodeCatalog = await (
    await page.request.get(
      manifest.api + "/power-apps/automations/node-catalog",
      { headers },
    )
  ).json();
  expect(
    nodeCatalog.nodes.filter((n: { id: string }) =>
      n.id.startsWith("connector_"),
    ).length,
  ).toBeGreaterThanOrEqual(40);
});

test("incoming webhooks card opens the signed receiver starter", async ({
  page,
}) => {
  await setup(page);
  await page.goto("/power-apps/connectors");
  await page
    .getByRole("textbox", { name: "Search integrations" })
    .fill("Incoming Webhooks");
  await page
    .getByRole("button", { name: "Configure webhook", exact: true })
    .click();
  await expect(page).toHaveURL(/\/power-apps\/automations\/\d+\/edit/);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(
    page
      .locator(".react-flow__node")
      .getByText("Incoming webhook", { exact: true }),
  ).toBeVisible();
});
