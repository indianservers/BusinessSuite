const {
  chromium,
  expect,
} = require("../frontend/node_modules/playwright/test");
const assert = require("node:assert/strict"),
  fs = require("node:fs");
const origin = process.env.GRID_QA_ORIGIN || "http://127.0.0.1:5194";
const hash = JSON.parse(
  fs.readFileSync("frontend/node_modules/.vite/deps/_metadata.json"),
).browserHash;
const html = `<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '/node_modules/.vite/deps/react.js?v=${hash}';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${hash}';import {ImportWizard,DataExportButton} from '/src/shared/data-transfer/index.ts';import {employeeImportFields} from '/src/shared/data-transfer/fields.ts';import {PeopleDialog} from '/src/apps/project-management/components/people/DirectoryDialogs.tsx';import '/src/apps/project-management/pages/PeopleWorkspace.css';import '/src/index.css';
window.commits=[];const rows=[{Name:'Ada',Amount:125,Private:'hidden'}];
function App(){return React.createElement(location.search.includes('nested')?PeopleDialog:'main',location.search.includes('nested')?{open:true,onClose:()=>{},title:'Import people',description:'Prepare invitations for your workspace.'}:{style:{padding:32}},React.createElement(TransferContent));}function TransferContent(){return React.createElement('main',{style:{padding:32}},React.createElement('h1',null,'Business Suite data transfer'),React.createElement('div',{style:{display:'flex',gap:12,marginTop:24}},React.createElement(ImportWizard,{title:'Import employees',fields:employeeImportFields,maxRows:100,onImport:async data=>{window.commits.push(data.rows);return window.rejectImport?{created:0,errors:[{row:1,error:'Employee ID already exists'}]}:{created:data.rows.length,message:'Employees saved successfully'};}}),React.createElement(DataExportButton,{filename:'employees',load:async()=>rows})));}ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
</script></body></html>`;
const table = {
  headers: ["Given Name", "Start Date", "Email Address", "Private"],
  rows: [
    ["Ada", "2026-01-01", "ada@example.com", "Do not import"],
    ["Grace", "2026-01-02", "grace@example.com", "Ignore"],
  ],
  rowNumbers: [3, 4],
  sheets: ["Instructions", "People"],
  sheet: "People",
  headerRow: 2,
  total: 2,
};
(async () => {
  const browser = await chromium.launch({
    args: ["--disable-features=LocalNetworkAccessChecks"],
  });
  const page = await browser.newPage({
    viewport: { width: 1360, height: 1000 },
    acceptDownloads: true,
  });
  const errors = [],
    requests = [];
  page.on("pageerror", (e) => {
    errors.push(e.message);
    console.error("PAGE", e.message);
  });
  page.on("console", (m) => {
    if (m.type() === "error") console.error("BROWSER", m.text());
  });
  page.setDefaultTimeout(15000);
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route("**/__transfer_qa*", (route) =>
    route.fulfill({ contentType: "text/html", body: html }),
  );
  await page.route("**/api/v1/data-transfer/**", async (route) => {
    const url = route.request().url(),
      body = route.request().postData() || "";
    requests.push({ url, body });
    if (url.endsWith("/export/inspect"))
      return route.fulfill({
        json: {
          headers: ["Name", "Amount", "Private"],
          rows: [["Ada", 125, "hidden"]],
          rowNumbers: [2],
          sheets: [],
          sheet: "",
          headerRow: 1,
          total: 1,
        },
      });
    if (url.endsWith("/export/convert"))
      return route.fulfill({
        contentType: "application/octet-stream",
        body: "export fixture",
      });
    if (body.includes("instructions.xlsx") && !body.includes("\r\nPeople\r\n"))
      return route.fulfill({
        status: 422,
        json: {
          detail: {
            message: "The selected sheet has no data below the header",
            sheets: ["Instructions", "People"],
          },
        },
      });
    const bad = body.includes("bad.xlsx");
    return route.fulfill({
      json: bad
        ? {
            ...table,
            rows: [["Ada", "31/12/2026", "invalid-email", "hidden"]],
            rowNumbers: [3],
            total: 1,
          }
        : table,
    });
  });
  try {
    await page.goto(origin + "/__transfer_qa");
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await page
      .getByLabel("Choose import file")
      .setInputFiles({
        name: "staff.xlsx",
        mimeType:
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        buffer: Buffer.from("fixture"),
      });
    await expect(page.locator("#dt-map-first_name")).toHaveValue("Given Name");
    await expect(page.locator("#dt-map-date_of_joining")).toHaveValue(
      "Start Date",
    );
    await expect(page.locator("#dt-map-personal_email")).toHaveValue(
      "Email Address",
    );
    assert.equal(await page.evaluate(() => commits.length), 0);
    await page.locator("#dt-map-first_name").selectOption("");
    await expect(
      page.getByRole("button", { name: "Review data" }),
    ).toBeDisabled();
    await page.locator("#dt-map-first_name").selectOption("Given Name");
    await page.getByRole("button", { name: "Review data" }).click();
    await expect(
      page.getByText("Review 2 rows", { exact: true }),
    ).toBeVisible();
    assert.equal(await page.evaluate(() => commits.length), 0);
    fs.mkdirSync("docs/qa/data-transfer", { recursive: true });
    await page.screenshot({ path: "docs/qa/data-transfer/import-review.png" });
    await page.evaluate(() => (window.rejectImport = true));
    await page.getByRole("button", { name: "Import rows (2)" }).click();
    await expect(
      page.getByText("Row 3: Employee ID already exists"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Back to mapping" }).click();
    await page.evaluate(() => (window.rejectImport = false));
    await page.getByRole("button", { name: "Review data" }).click();
    await page.getByRole("button", { name: "Import rows (2)" }).click();
    await expect(page.getByText("Employees saved successfully")).toBeVisible();
    const rows = await page.evaluate(() => commits.at(-1));
    assert.deepEqual(Object.keys(rows[0]).sort(), [
      "date_of_joining",
      "first_name",
      "personal_email",
    ]);
    await expect(
      page.getByRole("button", { name: "Import rows (2)" }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await page
      .getByLabel("Choose import file")
      .setInputFiles({
        name: "bad.xlsx",
        mimeType: "application/octet-stream",
        buffer: Buffer.from("fixture"),
      });
    await page.getByRole("button", { name: "Review data" }).click();
    await expect(
      page.getByRole("button", { name: "Import rows (1)" }),
    ).toBeDisabled();
    await expect(page.getByText(/Use YYYY-MM-DD/)).toBeVisible();
    const errorDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download errors" }).click();
    assert.equal(
      (await errorDownload).suggestedFilename(),
      "import-row-errors.csv",
    );
    await page.getByRole("button", { name: "Close import" }).click();
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await page
      .getByLabel("Choose import file")
      .setInputFiles({
        name: "instructions.xlsx",
        mimeType: "application/octet-stream",
        buffer: Buffer.from("fixture"),
      });
    await page.getByLabel("Choose worksheet").selectOption("People");
    await expect(page.locator("#dt-map-first_name")).toHaveValue("Given Name");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "docs/qa/data-transfer/import-mobile.png" });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    );
    await page.getByRole("button", { name: "Close import" }).click();
    await page.setViewportSize({ width: 1360, height: 1000 });
    await page.getByRole("button", { name: "Export", exact: true }).click();
    await expect(
      page.getByText("1 row available", { exact: false }),
    ).toBeVisible();
    await page.getByLabel("Private", { exact: true }).uncheck();
    await page.screenshot({ path: "docs/qa/data-transfer/export.png" });
    const exported = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download XLSX" }).click();
    assert.equal((await exported).suggestedFilename(), "employees.xlsx");
    const conversion = requests
      .filter((r) => r.url.endsWith("/export/convert"))
      .at(-1);
    assert.ok(conversion.body.includes('["Name","Amount"]'));
    assert.ok(conversion.body.includes("xlsx"));
    await page
      .getByRole("button", { name: /Copy Paste into a spreadsheet/ })
      .click();
    await page.getByRole("button", { name: "Copy data" }).click();
    await expect(page.getByText("Copied to clipboard")).toBeVisible();
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await page.screenshot({ path: "docs/qa/data-transfer/export-dark.png" });
    await page.goto(origin + "/__transfer_qa?nested");
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await page
      .getByLabel("Choose import file")
      .setInputFiles({
        name: "staff.xlsx",
        mimeType: "application/octet-stream",
        buffer: Buffer.from("fixture"),
      });
    await page.getByRole("button", { name: "Review data" }).click();
    await expect(
      page.getByText("Review 2 rows", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: "docs/qa/data-transfer/import-nested-dialog.png",
    });
    assert.deepEqual(errors, []);
    console.log(
      "PASS: auto/manual mapping, required columns, ignored columns, review before save, row validation/errors, server rejection, completion receipt, worksheet retry, mobile, selected export columns/formats, clipboard and dark theme",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
