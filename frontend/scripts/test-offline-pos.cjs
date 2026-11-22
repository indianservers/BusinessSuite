const assert = require("node:assert/strict");
const { chromium, expect } = require("playwright/test");
const path = require("node:path");
const { benchmarkPOS, benchmarkCatalog } = require("./pos-benchmark.cjs");

(async () => {
  process.chdir(path.resolve(__dirname, ".."));
  const { createServer } = await import("vite");
  const server = await createServer({server: {host: "127.0.0.1", port: 0, hmr: false, watch: null}});
  await server.listen();
  let browser;
  try {
    browser = await chromium.launch();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const benchmark = process.argv.includes("--benchmark");
    let uploadDelay = 0;
    let inFlight = 0;
    let disconnected = false;
    let holdReply = false;
    let registerOpen = true;
    let releaseReply;
    const replies = new Map();
    const submissions = [];
    const products = [
      {id: 1, name: "House Blend Coffee", barcode: "8901000000101", price: 100},
      {id: 2, name: "Whole Wheat Crackers", barcode: "8901000000102", price: 40},
      {id: 3, name: "Sparkling Water", barcode: "8901000000103", price: 25},
    ];
    const catalog = benchmark ? benchmarkCatalog() : {items: products.map(product => ({
      id: product.id, item_name: product.name, product_type: "product", sku: "SKU-" + product.id,
      barcode: product.barcode, sales_rate: product.price, gst_rate: 0, current_quantity: 20, active: true,
    })), total: products.length};
    const postedSales = new Map();
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
      if (pathname.endsWith("/inventory/items")) {
        const offset = (Number(new URL(request.url()).searchParams.get("page") || 1) - 1) * 200;
        return json({items: catalog.items.slice(offset, offset + 200), total: catalog.total});
      }
      if (pathname.endsWith("/business/customers")) return json({items: [], next: null});
      if (pathname.endsWith("/pos/sessions/active")) return json({session: registerOpen ? {id: 81, status: "open", session_number: "81"} : null});
      if (pathname.endsWith("/service-checkout") && request.method() === "POST") {
        const sale = request.postDataJSON();
        submissions.push(sale);
        if (!replies.has(sale.request_id)) {
          const id = replies.size + 1;
          postedSales.set(sale.request_id, sale);
          replies.set(sale.request_id, {id, state: "committed", sales_order_id: id, invoice: {
            id, number: "INV-" + id, total: sale.expected_total, paid: sale.expected_total, balance: "0.00",
          }, receipts: []});
          for (const line of sale.lines) catalog.items[line.product_id - 1].current_quantity -= Number(line.quantity);
          if (holdReply) {
            holdReply = false;
            await new Promise(resolve => { releaseReply = resolve; });
            return route.abort("connectionreset");
          }
        }
        inFlight++;
        try {
          if (uploadDelay) await new Promise(resolve => setTimeout(resolve, uploadDelay));
          return await json(replies.get(sale.request_id));
        } finally { inFlight--; }
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
    const scan = async (...ids) => {
      await search.focus();
      for (const id of ids) {
        await page.keyboard.type(products[id - 1].barcode);
        await page.keyboard.press("Enter");
        await expect(search).toHaveValue("");
      }
    };
    const checkout = async (total, printedLines) => {
      await page.keyboard.press("F7");
      await page.getByRole("button", {name: "Complete Sale", exact: true}).click();
      await expect(page.getByRole("heading", {name: "Cash sale saved", exact: true})).toBeVisible();
      if (printedLines) {
        await page.evaluate(() => { window.print = () => document.body.setAttribute("data-print-requested", "true"); });
        await page.getByRole("button", {name: "Print Receipt", exact: true}).click();
        await expect(page.locator("body")).toHaveAttribute("data-print-requested", "true");
        await page.emulateMedia({media: "print"});
        const receipt = page.getByRole("article", {name: "Local cash acknowledgement"});
        await expect(receipt).toBeVisible();
        for (const [id, quantity] of printedLines) {
          const item = products[id - 1];
          const line = receipt.locator("div").filter({hasText: item.name});
          await expect(line).toContainText(quantity + " x");
        }
        await expect(receipt).toContainText("Total: ₹" + total + ".00");
        await expect(receipt).toContainText("Paid: ₹" + total + ".00");
        const pdf = await page.pdf({width: "80mm", height: "160mm"});
        assert.equal(pdf.subarray(0, 4).toString(), "%PDF");
        await page.emulateMedia({media: "screen"});
      }
      await page.getByRole("button", {name: "New Sale", exact: true}).click();
    };
    const verifyShift = async (awaiting, synced) => {
      const report = page.getByRole("dialog");
      for (const [label, value] of [["Sales", "3"], ["Units sold", "11"], ["Cash collected", "₹620.00"], ["Awaiting posting", awaiting]]) {
        const row = report.getByText(label, {exact: true}).locator("..");
        await expect(row.getByText(value, {exact: true})).toBeVisible();
      }
      if (synced) {
        for (const invoice of ["INV-1", "INV-2", "INV-3"]) await expect(report.getByText(invoice, {exact: true})).toBeVisible();
      }
    };
    const setOffline = offline => page.evaluate(offline => {
      sessionStorage.setItem("test-offline", offline ? "1" : "0");
      window.dispatchEvent(new Event(offline ? "offline" : "online"));
    }, offline);

    await expect(ready).toBeVisible({timeout: 30000});
    if (benchmark) {
      await benchmarkPOS(page, {
        setOffline: async offline => { disconnected = offline; await setOffline(offline); },
        setUploadDelay: delay => { uploadDelay = delay; },
        isUploading: () => inFlight > 0,
      });
      return;
    }
    holdReply = true;
    await scan(1, 2, 3, 3);
    await checkout(190);
    await expect.poll(() => submissions.length).toBe(1);
    // Cut the register's connection with the first response in flight and
    // a second basket already started.
    await scan(1, 1);
    disconnected = true;
    await setOffline(true);
    releaseReply();
    await scan(2, 3);
    await checkout(265, [[1, 2], [2, 1], [3, 1]]);
    await scan(1, 2, 3);
    await checkout(165);
    await openShift();
    await verifyShift("₹620.00", false);
    assert.equal(submissions.length, 1);
    await page.reload();
    await expect(page.getByText("Offline · Cash sales ready", {exact: false})).toBeVisible();
    await page.setViewportSize({width: 390, height: 840});
    await openShift();
    await verifyShift("₹620.00", false);
    disconnected = false;
    await setOffline(false);
    await verifyShift("₹0.00", true);

    assert.equal(postedSales.size, 3);
    assert.equal(submissions.length, 4);
    assert.deepEqual(submissions[0], submissions[1]);
    const posted = [...postedSales.values()];
    assert.deepEqual(posted.map(sale => sale.expected_total), ["190.00", "265.00", "165.00"]);
    assert.deepEqual(posted.map(sale => sale.lines.length), [3, 3, 3]);
    assert.ok(posted.every(sale => sale.captured_at && sale.payments.length === 1
      && sale.payments[0].amount === sale.expected_total && sale.pos_session_id === 81));
    assert.deepEqual(catalog.items.map(item => item.current_quantity), [16, 17, 16]);
    registerOpen = false;
    await page.reload();
    await openShift();
    await expect(page.getByRole("dialog")).toContainText("Shift 81");
    await verifyShift("₹0.00", true);
    console.log("PASS register 81: 3 multi-item bills, 11 units, ₹620.00, printable 80 mm receipt, offline reload, 4 attempts and 3 posted sales");
  } finally {
    await browser?.close();
    await server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
