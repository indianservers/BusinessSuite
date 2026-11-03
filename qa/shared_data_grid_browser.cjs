// Isolated loopback UI checks. Remote pages never load the full logical dataset.
const {
  chromium,
  expect: raw,
} = require("../frontend/node_modules/playwright/test");
const assert = require("node:assert/strict"),
  fs = require("node:fs");
const expect = raw.configure({ timeout: 15000 }),
  origin = process.env.GRID_QA_ORIGIN || "http://127.0.0.1:5194";
const hash = JSON.parse(
  fs.readFileSync("frontend/node_modules/.vite/deps/_metadata.json"),
).browserHash;
const html = `<!doctype html><html><head><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '/node_modules/.vite/deps/react.js?v=${hash}';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${hash}';import {MemoryRouter} from '/node_modules/.vite/deps/react-router-dom.js?v=${hash}';import {QueryClient,QueryClientProvider} from '/node_modules/.vite/deps/@tanstack_react-query.js?v=${hash}';import DealsGrid from '/src/apps/crm/deals/DealsDataGrid.tsx';import DealsWorkspace from '/src/apps/crm/deals/EnterpriseDealsPage.tsx';import SharedDataGrid from '/src/shared/data-grid/SharedDataGrid.tsx';import {api} from '/src/services/api.ts';import '/src/index.css';
const query=new URLSearchParams(location.search);const wide=query.has('wide');
const columns=Array.from({length:60},(_,i)=>({id:'f'+i,title:'Field '+i,width:150,groupable:false,accessor:row=>row['f'+i]}));
const source={key:'large-demo',load:async(state,signal)=>(await api.get('/grid-qa',{params:{state:JSON.stringify(state)},signal})).data};
function App(){const[selected,setSelected]=React.useState([]),[reload,setReload]=React.useState(0),[result,setResult]=React.useState();React.useEffect(()=>{const changed=()=>setReload(v=>v+1);window.addEventListener('crm:records-changed',changed);return()=>window.removeEventListener('crm:records-changed',changed);},[]);return React.createElement('div',{style:{margin:16,minWidth:0}},query.has('workspace')?React.createElement(DealsWorkspace):wide?React.createElement(SharedDataGrid,{gridId:'large-demo',title:'Large dataset grid',columns,dataSource:source,getRowId:row=>String(row.id),initialQuery:{pageSize:200}}):React.createElement(DealsGrid,{base:{},refreshKey:reload,selected,onSelection:(rows,ids)=>{setSelected(ids);window.qaSelected=rows;},onResult:setResult,onQueryChange:value=>window.qaQuery=value,edit:id=>window.qaEdit=id,move:id=>window.qaMove=id,canManage:true,canArchive:true,owners:[],initialQuery:{pageSize:50}}));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},React.createElement(MemoryRouter,null,React.createElement(App))));
</script></body></html>`;
function row(index) {
  return {
    id: index + 1,
    name: "Deal " + String(index).padStart(5, "0"),
    company_id: 1,
    company_name: "Acme Industries",
    pipeline_id: 1,
    pipeline_name: "Enterprise sales",
    stage_id: (index % 3) + 1,
    stage_name: ["Discovery", "Proposal", "Negotiation"][index % 3],
    stage_color: ["#6366f1", "#d97706", "#0891b2"][index % 3],
    amount: 1000 + index,
    currency: index % 2 ? "USD" : "INR",
    probability: 50,
    weighted: (1000 + index) / 2,
    owner_user_id: 1,
    owner_name: "Alex Morgan",
    priority: index % 3 === 0 ? "High" : "Medium",
    status: index % 5 === 0 ? "Won" : "Open",
    version: 1,
    expected_close_date: "2026-11-20",
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-02T12:00:00Z",
    next_follow_up_at: null,
  };
}
const records = Array.from({ length: 1000 }, (_, i) => row(i));
function matches(row, filter) {
  if (!filter?.rules?.length) return true;
  return (
    filter[filter.logic === "or" ? "some" : "every"]?.(() => false) ??
    (filter.logic === "or" ? filter.rules.some(test) : filter.rules.every(test))
  );
  function test(rule) {
    if (rule.rules) return matches(row, rule);
    const value = row[rule.field];
    switch (rule.operator) {
      case "equals":
        return String(value) === String(rule.value);
      case "contains":
        return String(value || "")
          .toLowerCase()
          .includes(String(rule.value).toLowerCase());
      case "gt":
        return value > Number(rule.value);
      case "between":
        return value >= Number(rule.value) && value <= Number(rule.value2);
      case "in":
        return rule.value.includes(value);
      case "empty":
        return value == null || value === "";
      default:
        return true;
    }
  }
}
function sums(items) {
  return [...new Set(items.map((r) => r.currency))].map((currency) => {
    const values = items
      .filter((r) => r.currency === currency)
      .map((r) => r.amount);
    return {
      currency,
      count: values.length,
      sum: values.reduce((a, b) => a + b, 0),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      min: Math.min(...values),
      max: Math.max(...values),
      weighted: values.reduce((a, b) => a + b, 0) / 2,
    };
  });
}
(async () => {
  const browser = await chromium.launch({ headless: true }),
    requests = [],
    errors = [];
  try {
    const sharedModule = await (
        await fetch(origin + "/src/shared/data-grid/SharedDataGrid.tsx")
      ).text(),
      dealsModule = await (
        await fetch(origin + "/src/apps/crm/deals/DealsDataGrid.tsx")
      ).text();
    const routerImport = dealsModule.match(
        /\/node_modules\/\.vite\/deps\/react-router-dom\.js\?v=[^"]+/,
      )[0],
      queryImport = sharedModule.match(
        /\/node_modules\/\.vite\/deps\/@tanstack_react-query\.js\?v=[^"]+/,
      )[0];
    const testHtml = html
      .replace(
        /\/node_modules\/\.vite\/deps\/react-router-dom\.js\?v=[^']+/g,
        routerImport,
      )
      .replace(
        /\/node_modules\/\.vite\/deps\/@tanstack_react-query\.js\?v=[^']+/g,
        queryImport,
      );
    const context = await browser.newContext({
      viewport: { width: 1480, height: 1050 },
      permissions: ["clipboard-read", "clipboard-write"],
    });
    await context.route("**/__grid_qa*", (route) =>
      route.fulfill({ contentType: "text/html", body: testHtml }),
    );
    await context.route("**/api/v1/**", async (route) => {
      const request = route.request(),
        url = new URL(request.url()),
        path = url.pathname,
        state = JSON.parse(url.searchParams.get("state") || "{}");
      requests.push({
        path,
        method: request.method(),
        state,
        base: JSON.parse(url.searchParams.get("base") || "{}"),
      });
      if (path.endsWith("/grid-qa")) {
        const page = state.page || 1,
          size = state.pageSize || 50;
        const rows = Array.from({ length: size }, (_, i) => {
          const id = (page - 1) * size + i;
          return {
            id: id + 1,
            ...Object.fromEntries(
              Array.from({ length: 60 }, (_, j) => [
                "f" + j,
                `Row ${id} value ${j}`,
              ]),
            ),
          };
        });
        return route.fulfill({
          json: {
            rows,
            groups: [],
            total: 100000,
            pageTotal: 100000,
            page,
            pageSize: size,
            permissions: { export: true },
          },
        });
      }
      if (path.endsWith("/deal-workspace/pipelines"))
        return route.fulfill({
          json: {
            items: [{ id: 1, name: "Enterprise sales" }],
            total: 1,
            pages: 1,
          },
        });
      if (path.endsWith("/deal-workspace/pipeline-stages"))
        return route.fulfill({
          json: {
            items: [
              { id: 1, name: "Discovery", pipeline_id: 1 },
              { id: 2, name: "Proposal", pipeline_id: 1 },
              { id: 3, name: "Negotiation", pipeline_id: 1 },
            ],
            total: 3,
            pages: 1,
          },
        });
      if (path.endsWith("/deal-workspace/assignees"))
        return route.fulfill({
          json: {
            items: [{ id: 1, name: "Alex Morgan", email: "alex@example.com" }],
            total: 1,
            pages: 1,
          },
        });
      if (path.includes("/grid/")) {
        if (path.endsWith("/archive")) {
          const items = request.postDataJSON().records.map((selected) => {
            const record = records.find((r) => r.id === selected.id);
            if (record.version !== selected.version)
              return {
                id: selected.id,
                saved: false,
                message: "This record changed",
              };
            record.deleted = true;
            return { id: selected.id, saved: true };
          });
          return route.fulfill({ json: { items } });
        }
        let filtered = records.filter(
          (r) =>
            !r.deleted &&
            (!state.search ||
              r.name.toLowerCase().includes(state.search.toLowerCase())) &&
            matches(r, state.filters),
        );
        if (path.endsWith("/facets")) {
          const field = url.searchParams.get("field");
          return route.fulfill({
            json: {
              values: [...new Set(filtered.map((r) => r[field]))].map(
                (value) => ({
                  value,
                  label: String(value),
                  count: filtered.filter((r) => r[field] === value).length,
                }),
              ),
            },
          });
        }
        if (path.endsWith("/export")) {
          const ids = JSON.parse(url.searchParams.get("ids") || "[]");
          const chosen =
            url.searchParams.get("scope") === "filtered"
              ? filtered
              : filtered.filter((r) => ids.includes(r.id));
          const columns = JSON.parse(url.searchParams.get("columns") || "[]");
          return route.fulfill({
            contentType: "text/csv",
            body: [
              columns.join(","),
              ...chosen.map((r) => columns.map((c) => r[c] ?? "").join(",")),
            ].join("\n"),
          });
        }
        const base = JSON.parse(url.searchParams.get("base") || "{}");
        for (const field of [
          "priority",
          "status",
          "currency",
          "stage_id",
          "pipeline_id",
        ])
          if (base[field])
            filtered = filtered.filter(
              (r) => String(r[field]) === String(base[field]),
            );
        const total = filtered.length;
        for (const key of state.path || [])
          filtered = filtered.filter((r) => r[key.field] === key.value);
        const grouping = state.grouping || [],
          page = state.page || 1,
          size = state.pageSize || 50;
        assert.ok(size <= 200);
        let groups = [],
          rows = [],
          pageTotal = filtered.length;
        if ((state.path || []).length < grouping.length) {
          const field = grouping[(state.path || []).length],
            keys = [...new Set(filtered.map((r) => r[field]))];
          pageTotal = keys.length;
          groups = keys.slice((page - 1) * size, page * size).map((value) => {
            const items = filtered.filter((r) => r[field] === value);
            return {
              field,
              value,
              label:
                field === "stage_id"
                  ? ["Discovery", "Proposal", "Negotiation"][value - 1]
                  : String(value),
              count: items.length,
              aggregates: sums(items),
              path: [...(state.path || []), { field, value }],
            };
          });
        } else {
          for (const sort of [...(state.sorting || [])].reverse())
            filtered.sort(
              (a, b) =>
                (a[sort.id] > b[sort.id]
                  ? 1
                  : a[sort.id] < b[sort.id]
                    ? -1
                    : 0) * (sort.desc ? -1 : 1),
            );
          rows = filtered.slice((page - 1) * size, page * size);
        }
        return route.fulfill({
          json: {
            rows,
            groups,
            total,
            pageTotal,
            page,
            pageSize: size,
            aggregates: sums(filtered),
            permissions: {
              edit: true,
              export: true,
              archive: true,
              assign: true,
            },
            context: { summary: { counts: { open: total }, currencies: [] } },
          },
        });
      }
      const record = path.match(/\/crm\/deals\/(\d+)$/);
      if (record) {
        const found = records.find((r) => r.id === Number(record[1]));
        if (request.method() === "PATCH") {
          const data = request.postDataJSON();
          if (data.expected_version !== found.version)
            return route.fulfill({
              status: 409,
              json: { detail: "This deal changed" },
            });
          Object.assign(found, data, { version: found.version + 1 });
        }
        if (request.method() === "DELETE") found.deleted = true;
        return route.fulfill({ json: found });
      }
      return route.fulfill({ json: { items: [] } });
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => {
      errors.push(e.message);
      console.error(e.message);
    });
    await page.goto(origin + "/__grid_qa");
    await expect(
      page.getByRole("grid", { name: "Deals data grid", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".udg-row").first()).toBeVisible();
    assert.ok(
      (await page.locator(".udg-row").count()) < 40,
      "Rows must be virtualized",
    );
    const drag = page.getByRole("button", {
        name: "Drag Currency column",
        exact: true,
      }),
      target = page.getByRole("button", {
        name: "Drag Deal value column",
        exact: true,
      });
    const dragBox = await drag.boundingBox(),
      targetBox = await page.locator("[data-column=amount]").boundingBox();
    await page.mouse.move(dragBox.x + 5, dragBox.y + 12);
    await page.mouse.down();
    await page.mouse.move(dragBox.x - 10, dragBox.y + 12, { steps: 3 });
    await page.mouse.move(
      targetBox.x + targetBox.width / 2,
      targetBox.y + targetBox.height / 2,
      { steps: 15 },
    );
    await page.waitForTimeout(150);
    await page.mouse.up();
    await expect
      .poll(() =>
        page.evaluate(() =>
          JSON.parse(
            localStorage.getItem("suite-grid:v1:0:0:organization:crm-deals"),
          ).layout.order.indexOf("currency"),
        ),
      )
      .toBe(2);
    const resize = page.getByRole("separator", {
      name: "Resize Deal value",
      exact: true,
    });
    await resize.scrollIntoViewIfNeeded();
    const box = await resize.boundingBox();
    await page.mouse.move(box.x + 3, box.y + 15);
    await page.mouse.down();
    await page.mouse.move(box.x + 75, box.y + 15, { steps: 8 });
    await page.mouse.up();
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            JSON.parse(
              localStorage.getItem("suite-grid:v1:0:0:organization:crm-deals"),
            ).layout.sizes.amount || 0,
        ),
      )
      .toBeGreaterThan(160);
    await page.getByRole("button", { name: "Columns", exact: true }).click();
    await page.getByLabel("Pin Stage", { exact: true }).selectOption("right");
    await page
      .getByRole("checkbox", { name: "Currency", exact: true })
      .uncheck();
    await page
      .getByRole("button", { name: "Move Owner left", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Close column manager", exact: true })
      .click();
    assert.equal(
      await page.locator("[role=columnheader][data-column=currency]").count(),
      0,
    );
    assert.equal(
      await page
        .locator("[role=columnheader][data-column=stage_id]")
        .evaluate((el) => getComputedStyle(el).position),
      "sticky",
    );
    await page
      .getByLabel("Add grouping column", { exact: true })
      .selectOption("stage_id");
    await expect(page.locator(".udg-group-row")).toHaveCount(3);
    assert.ok(
      (await page.locator(".udg-group-row").first().innerText()).includes(
        "334",
      ),
    );
    await page.locator(".udg-group-row>button").first().click();
    await expect(page.locator(".udg-row").first()).toBeVisible();
    assert.ok(requests.some((r) => r.state.path?.length === 1));
    await page
      .getByRole("button", { name: "Remove grouping Stage", exact: true })
      .click();
    await expect(page.locator(".udg-row").first()).toBeVisible();
    await page
      .getByRole("button", { name: "Filter Priority", exact: true })
      .click();
    await expect(page.getByRole("checkbox", { name: /High/ })).toBeVisible();
    await page.getByRole("checkbox", { name: /High/ }).check();
    await page.getByRole("button", { name: "Apply", exact: true }).click();
    await expect(page.locator(".udg-summary-footer")).toContainText(
      "334 matching records",
    );
    await page
      .getByRole("button", { name: "Filters", exact: false })
      .filter({ has: page.locator("svg") })
      .first()
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Condition", exact: true })
      .click();
    const rule = page.getByRole("dialog").locator(".udg-filter-rule").last();
    await rule.locator("select").first().selectOption("amount");
    await rule.locator("select").nth(1).selectOption("gt");
    await rule.locator("input").fill("1100");
    await page
      .getByRole("button", { name: "Apply filters", exact: true })
      .click();
    await expect(page.locator(".udg-summary-footer")).toContainText(
      "300 matching records",
    );
    await page.locator("[data-column=amount] .udg-sort-button").click();
    await page
      .locator("[data-column=name] .udg-sort-button")
      .click({ modifiers: ["Shift"] });
    await expect
      .poll(() => page.evaluate(() => window.qaQuery.sorting.length))
      .toBe(2);
    const checks = page.locator(".udg-row .udg-select-cell input");
    await checks.nth(0).check();
    await checks.nth(4).click({ modifiers: ["Shift"] });
    await expect(page.locator(".udg-selection-bar")).toContainText(
      "5 selected",
    );
    assert.equal(await page.evaluate(() => window.qaSelected.length), 5);
    const cell = page.locator(".udg-row [data-cell-id=name]").first();
    const old = await cell.innerText();
    await cell.dblclick();
    await page
      .getByLabel("Edit Deal name", { exact: true })
      .fill("Canceled name");
    await page.getByLabel("Edit Deal name", { exact: true }).press("Escape");
    await expect(cell).toContainText(old);
    await cell.focus();
    await cell.press("F2");
    await page
      .getByLabel("Edit Deal name", { exact: true })
      .fill("Renamed enterprise opportunity");
    await page.getByLabel("Edit Deal name", { exact: true }).press("Enter");
    await expect(
      page.locator(".udg-row [data-cell-id=name]").first(),
    ).toContainText("Renamed enterprise opportunity");
    const valueCell = page.locator(".udg-row [data-cell-id=amount]").first();
    await valueCell.focus();
    await valueCell.press("ArrowRight");
    assert.notEqual(
      await page.evaluate(() => document.activeElement.dataset.cellId),
      "amount",
    );
    await page.keyboard.press("Shift+ArrowRight");
    await page.keyboard.press("Control+C");
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain("Enterprise sales");
    await page.locator(".udg-row").first().click({ button: "right" });
    await page.getByRole("menuitem", { name: "Copy row", exact: true }).click();
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain("Renamed enterprise opportunity");
    await page
      .getByRole("button", { name: "Saved views", exact: true })
      .click();
    await page
      .getByLabel("Saved view name", { exact: true })
      .fill("High value opportunities");
    await page
      .getByRole("button", { name: "Save current view", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Close saved views", exact: true })
      .click();
    await page.getByRole("button", { name: "Export", exact: true }).click();
    await page
      .getByLabel("Export rows", { exact: true })
      .selectOption("selected");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "CSV", exact: true }).click();
    const downloaded = await download;
    const file = await downloaded.path();
    assert.equal(fs.readFileSync(file, "utf8").trim().split("\n").length, 6);
    await page.keyboard.press("Escape");
    fs.mkdirSync("docs/qa/shared-data-grid", { recursive: true });
    await page.screenshot({
      path: "docs/qa/shared-data-grid/deals-desktop.png",
      fullPage: true,
    });
    await page.reload();
    await expect(page.locator(".udg-summary-footer")).toContainText(
      "300 matching records",
    );
    assert.equal(
      await page.locator("[role=columnheader][data-column=currency]").count(),
      0,
    );
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "Mobile page must not overflow; scrolling stays inside grid",
    );
    await page.screenshot({
      path: "docs/qa/shared-data-grid/deals-mobile.png",
      fullPage: true,
    });
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await page.screenshot({
      path: "docs/qa/shared-data-grid/deals-dark.png",
      fullPage: true,
    });
    const workspacePage = await context.newPage();
    workspacePage.on("pageerror", (e) => {
      errors.push(e.message);
      console.error(e.message);
    });
    await workspacePage.goto(origin + "/__grid_qa?workspace=1");
    await expect(
      workspacePage.getByRole("heading", { name: "Deals", exact: true }),
    ).toBeVisible();
    await expect(workspacePage.locator(".udg-row").first()).toBeVisible();
    for (const [mode, selector] of [
      ["Cards", ".ed-shared-cards .ed-card"],
      ["Pipeline", ".ed-board>section"],
      ["List", ".ed-list>details"],
      ["Timeline", ".ed-timeline>article"],
    ]) {
      await workspacePage
        .getByRole("button", { name: mode, exact: true })
        .click();
      await expect(workspacePage.locator(selector).first()).toBeVisible();
    }
    await workspacePage
      .getByRole("button", { name: "Forecast", exact: true })
      .click();
    await expect(
      workspacePage.getByRole("heading", {
        name: "Revenue forecast",
        exact: true,
      }),
    ).toBeVisible();
    await workspacePage
      .getByRole("button", { name: "Data grid", exact: true })
      .click();
    await expect(workspacePage.locator(".udg-row").first()).toBeVisible();
    await workspacePage
      .getByLabel("Priority", { exact: true })
      .selectOption("High");
    await expect(workspacePage.locator(".udg-filter-chips")).toContainText(
      "Priority: High",
    );
    await workspacePage
      .locator(".udg-filter-chips")
      .getByRole("button", { name: "Clear all", exact: true })
      .click();
    await expect(
      workspacePage.getByLabel("Priority", { exact: true }),
    ).toHaveValue("");
    await expect(workspacePage.locator(".udg-summary-footer")).toContainText(
      "1,000 matching records",
    );
    await workspacePage.screenshot({
      path: "docs/qa/shared-data-grid/deals-workspace.png",
      fullPage: true,
    });
    const wide = await context.newPage();
    wide.on("pageerror", (e) => errors.push(e.message));
    await wide.goto(origin + "/__grid_qa?wide=1");
    await expect(
      wide.getByRole("grid", { name: "Large dataset grid", exact: true }),
    ).toBeVisible();
    await expect(wide.locator(".udg-row").first()).toBeVisible();
    assert.ok((await wide.locator(".udg-row").count()) < 45);
    assert.ok(
      (await wide.locator("[role=columnheader][data-column]").count()) < 25,
      "Wide grids must virtualize columns",
    );
    await wide.locator(".udg-scroll").evaluate((el) => {
      el.scrollTop = 6500;
      el.scrollLeft = 5500;
    });
    await expect
      .poll(() =>
        wide
          .locator(".udg-row [data-cell-id]")
          .first()
          .getAttribute("data-row-id"),
      )
      .not.toBe("1");
    assert.ok(
      requests
        .filter((r) => r.path.endsWith("/grid-qa"))
        .every((r) => r.state.pageSize <= 200),
    );
    assert.deepEqual(errors, []);
    console.log(
      "PASS: drag/resize, pin/hide/reorder, full-data grouping/filtering, selection/ranges, inline edit, keyboard, saved layout, exports, responsive themes and 100,000-record remote/60-column virtualization",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
