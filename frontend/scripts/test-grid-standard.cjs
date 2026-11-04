const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const { chromium } = require("playwright");
function loadTypescript(relative) {
  const filename = path.resolve(__dirname, relative);
  const output = ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const mod = new Module(filename, module); mod.filename = filename; mod.paths = module.paths; mod._compile(output, filename); return mod.exports;
}
async function sourceTests() {
  const { localGridSource } = loadTypescript("../src/shared/data-grid/local-source.ts");
  const { emptyQuery } = loadTypescript("../src/shared/data-grid/types.ts");
  const rows = [{ id: "1", name: "Alpha", status: "Open", amount: 2 }, { id: "2", name: "Beta", status: "Done", amount: 20 }, { id: "3", name: "Gamma", status: "Open", amount: 100 }];
  const source = localGridSource("test", rows, ["name", "status", "amount"].map(id => ({ id, title: id })), r => r.id);
  assert.equal((await source.load({ ...emptyQuery(), search: "ALPHA" })).rows[0].id, "1");
  assert.deepEqual((await source.load({ ...emptyQuery(), sorting: [{ id: "amount", desc: true }] })).rows.map(r => r.id), ["3", "2", "1"]);
  assert.equal((await source.load({ ...emptyQuery(), filters: { logic: "or", rules: [{ field: "amount", operator: "gt", value: 20 }, { field: "name", operator: "equals", value: "Beta" }] } })).total, 2);
  assert.equal((await source.load({ ...emptyQuery(), filters: { logic: "and", rules: [{ field: "status", operator: "equals", value: "Open" }, { logic: "or", rules: [{ field: "amount", operator: "gt", value: 50 }, { field: "name", operator: "equals", value: "Beta" }] }] } })).total, 1);
  const grouped = await source.load({ ...emptyQuery(), grouping: ["status"] });
  assert.equal(grouped.groups.find(g => g.value === "Open").count, 2);
  const branch = await source.load({ ...emptyQuery(), grouping: ["status"], path: [{ field: "status", value: "Open" }] });
  assert.deepEqual(branch.rows.map(r => r.id), ["1", "3"]);
  const exported = await source.export({ format: "csv", scope: "selected", ids: ["2"], columns: ["name"], query: emptyQuery() });
  assert.match(await exported.text(), /Beta/); assert.doesNotMatch(await exported.text(), /Alpha/);
  const injection = localGridSource("csv", [{ id: "x", name: "=SUM(A1)" }], [{ id: "name", title: "name" }], r => r.id);
  assert.match(await (await injection.export({ format: "csv", scope: "filtered", ids: [], columns: ["name"], query: emptyQuery() })).text(), /'=SUM/);
  console.log("PASS local search, numeric sort, nested filters, group expansion, selected exports, spreadsheet formula escaping");
}
async function browserTests() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on("pageerror", error => errors.push(error.message));
  const base = process.env.GRID_TEST_URL || "http://127.0.0.1:5174";
  await page.route("**/qa-grid-standard", route => route.fulfill({ contentType: "text/html", body: `<!doctype html><html><head><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/grid-standard.tsx"></script></body></html>` }));
  try {
    await page.goto(`${base}/qa-grid-standard`);
    const shared = page.getByTestId("shared"), adapter = page.getByTestId("adapter");
    await shared.getByRole("checkbox", { name: "Select row Record 1", exact: true }).waitFor();
    await shared.getByLabel("Search grid", { exact: true }).fill("Record 35");
    await shared.getByRole("checkbox", { name: "Select row Record 35", exact: true }).waitFor();
    assert.equal(await shared.getByRole("checkbox", { name: /^Select row/ }).count(), 1);
    await shared.getByLabel("Clear grid search").click();
    await shared.getByRole("checkbox", { name: "Select row Record 1", exact: true }).waitFor();
    await shared.getByRole("button", { name: "Preview record Record 1", exact: true }).click();
    await shared.getByRole("complementary", { name: "Record details: Record 1", exact: true }).waitFor();
    await page.keyboard.press("Escape");
    assert.equal(await shared.getByRole("complementary").count(), 0);
    await shared.getByLabel("Add grouping column").selectOption("status");
    await shared.getByRole("button", { name: /Open.*17/ }).waitFor();
    await shared.getByRole("button", { name: /Open.*17/ }).click();
    await shared.getByRole("checkbox", { name: "Select row Record 2", exact: true }).waitFor();
    await shared.getByRole("checkbox", { name: "Select row Record 2", exact: true }).click();
    await shared.getByRole("button", { name: "Fail update", exact: true }).click();
    await shared.getByRole("alert").filter({ hasText: "Update denied by record permission" }).waitFor();
    assert.equal(await shared.getByRole("checkbox", { name: "Select row Record 2", exact: true }).isChecked(), true);
    await shared.getByRole("button", { name: "Mark done", exact: true }).click();
    await shared.getByRole("button", { name: /Done.*19/ }).waitFor();
    await adapter.getByLabel("Existing select a", { exact: true }).check();
    await page.getByRole("button", { name: "Existing bulk action (1)", exact: true }).waitFor();
    assert.equal(await adapter.getByLabel("Select all loaded rows").count(), 0);
    await adapter.getByRole("button", { name: "Edit a", exact: true }).click();
    assert.equal(await page.getByLabel("Action count").textContent(), "1");
    assert.equal(await page.getByTestId("matrix").getByRole("grid").count(), 0);
    await page.getByLabel("Amount editor").fill("42");
    assert.equal(await page.getByLabel("Amount editor").inputValue(), "42");
    await page.setViewportSize({ width: 390, height: 844 });
    await adapter.getByRole("button", { name: "Preview record", exact: false }).first().click();
    await page.getByRole("dialog").waitFor();
    await page.keyboard.press("Escape");
    assert.equal(await page.getByRole("dialog").count(), 0);
    assert.deepEqual(errors, []);
    console.log("PASS browser search, preview/Escape, grouping, real bulk mutation, existing selection/actions, editable matrix, mobile details dialog");
    if (process.env.GRID_SCREENSHOT) await page.screenshot({ path: process.env.GRID_SCREENSHOT, fullPage: true });
  } finally { await browser.close(); }
}
(async () => { await sourceTests(); if (!process.argv.includes("--unit")) await browserTests(); })().catch(error => { console.error(error); process.exitCode = 1; });
