const assert = require("node:assert/strict");
const { chromium, expect } = require("playwright/test");
const path = require("node:path");

(async () => {
  process.chdir(path.resolve(__dirname, ".."));
  const { createServer } = await import("vite");
  const server = await createServer({server: {host: "127.0.0.1", port: 0, hmr: false, watch: null}});
  await server.listen();
  let browser;
  try {
    browser = await chromium.launch();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    let disconnected = false;
    let holdReply = false;
    let registerOpen = true;
    let releaseReply;
    const replies = new Map();
    const submissions = [];
    const catalog = {items: [{id: 1, item_name: "Counter product", product_type: "product", sku: "COUNTER",
      barcode: "0123456789", sales_rate: 100, gst_rate: 0, current_quantity: 2, active: true}], total: 1};
    const authority = {checkout_create: true, checkout_collect: true, operational_scope: {
      realm: "legacy", user_id: 77, company_id: 1, branch_id: 1, context_id: null, pack_key: null,
      pack_version: null, context_revision: null, grant_revision: null, activation_revision: null,
    }};
    const access = {companyId: 1, isAccessAdmin: true, grants: {}, businessPacks: {
      state: "ready", contexts: [], hasMore: false, selectorRequired: false, selectedContextId: null, selectionState: "none",
    }};
    await page.route("**/api/v1/**", async route => {
      if (disconnected) return route.abort("internetdisconnected");
      const request = route.request();
      const pathname = new URL(request.url()).pathname;
      const json = data => route.fulfill({json: data});
      if (pathname.endsWith("/auth/me")) return json({id: 77, role: "employee", is_superuser: false});
      if (pathname.endsWith("/access/me")) return json(access);
      if (pathname.endsWith("/industry/capabilities")) return json(authority);
      if (pathname.endsWith("/access/settings/defaults/effective")) return json({values: {}, modules: {}, companyId: 1, branchId: 1});
      if (pathname.endsWith("/anonymous-cash/configuration")) return json({schema_ready: true, configured: true, enabled: true});
      if (pathname.endsWith("/inventory/items")) return json(catalog);
      if (pathname.endsWith("/business/customers")) return json({items: [], next: null});
      if (pathname.endsWith("/pos/sessions/active")) return json({session: registerOpen ? {id: 81, status: "open", session_number: "81"} : null});
      if (pathname.endsWith("/service-checkout") && request.method() === "POST") {
        const sale = request.postDataJSON();
        submissions.push(sale);
        if (!replies.has(sale.request_id)) {
          const id = replies.size + 1;
          replies.set(sale.request_id, {id, state: "committed", sales_order_id: id, invoice: {
            id, number: "INV-" + id, total: sale.expected_total, paid: sale.expected_total, balance: "0.00",
          }, receipts: []});
          catalog.items[0].current_quantity--;
          if (holdReply) {
            holdReply = false;
            await new Promise(resolve => { releaseReply = resolve; });
            return route.abort("connectionreset");
          }
        }
        return json(replies.get(sale.request_id));
      }
      return json({items: [], total: 0});
    });
    await page.route("**/offline-pos-qa", route => route.fulfill({contentType: "text/html", body: `
      <script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div>
      <script type="module">
        import R from "/@react-refresh";
        R.injectIntoGlobalHook(window);
        window.$RefreshReg$=()=>{};
        window.$RefreshSig$=()=>type=>type;
        window.__vite_plugin_react_preamble_installed__=true;
        await import("/scripts/fixtures/anonymous-pos.tsx");
      </script>`}));
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "onLine", {get: () => sessionStorage.getItem("test-offline") !== "1"});
    });
    await page.goto("http://127.0.0.1:" + server.httpServer.address().port + "/offline-pos-qa");
    const ready = page.getByText("Offline cash ready", {exact: false});
    const search = page.getByRole("textbox", {name: "Search or scan items"});
    const openShift = () => page.getByRole("button", {name: "Local shift report"}).click();
    const ringUp = async () => {
      await search.fill("0123456789");
      await search.press("Enter");
      await page.keyboard.press("F7");
      await page.getByRole("button", {name: "Complete Sale", exact: true}).click();
      await expect(page.getByRole("heading", {name: "Cash sale saved", exact: true})).toBeVisible();
      await page.getByRole("button", {name: "New Sale", exact: true}).click();
    };
    const setOffline = offline => page.evaluate(offline => {
      sessionStorage.setItem("test-offline", offline ? "1" : "0");
      window.dispatchEvent(new Event(offline ? "offline" : "online"));
    }, offline);

    await expect(ready).toBeVisible({timeout: 30000});
    await search.fill("counter prod");
    await expect(page.locator(".srm-pos-catalog article").filter({hasText: "Counter product"}).first()).toBeVisible();
    holdReply = true;
    await ringUp();
    await expect.poll(() => submissions.length).toBe(1);
    disconnected = true;
    await setOffline(true);
    releaseReply();
    await ringUp();
    await openShift();
    await expect(page.getByRole("dialog")).toContainText("200");
    await expect(page.getByRole("dialog")).toContainText("Pending");
    assert.equal(submissions.length, 1);
    await page.reload();
    await expect(page.getByText("Offline · Cash sales ready", {exact: false})).toBeVisible();
    await page.setViewportSize({width: 390, height: 840});
    await openShift();
    await expect(page.getByRole("dialog")).toContainText("200");
    disconnected = false;
    await setOffline(false);
    await expect(page.getByRole("dialog").getByText("INV-2")).toBeVisible({timeout: 15000});
    await expect(page.getByRole("dialog").getByText("INV-1")).toBeVisible();
    await expect(page.getByRole("dialog")).toContainText("200");
    assert.equal(replies.size, 2);
    assert.equal(submissions.length, 3);
    assert.deepEqual(submissions[0], submissions[1]);
    assert.ok(submissions.every(sale => sale.captured_at && sale.payments[0].amount === "100.00"));
    registerOpen = false;
    await page.reload();
    await openShift();
    await expect(page.getByRole("dialog")).toContainText("Shift 81");
    await expect(page.getByRole("dialog")).toContainText("200");
    console.log("PASS local cash online and offline, catalog search, reload recovery, shift totals and idempotent reconnect");
  } finally {
    await browser?.close();
    await server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
