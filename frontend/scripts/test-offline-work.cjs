const assert = require("node:assert/strict");
const { chromium, expect } = require("playwright/test");
const path = require("node:path");

(async () => {
  process.chdir(path.resolve(__dirname, ".."));
  const server = await (await import("vite")).createServer({server: {host: "127.0.0.1", hmr: false, watch: null}});
  await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    let offline = false;
    let rejectStatus = false;
    const writes = [];
    const attempts = [];
    const receipts = new Map();
    let loseReply = true;
    const tasks = Array.from({length: 600}, (_, i) => ({
      id: i + 7, task_key: "OPS-" + (i + 7), title: i === 0 ? "Existing task" : ["Review purchase order", "Check store inventory", "Prepare member onboarding"][i % 3] + " " + i,
      project_id: 1 + i % 12, status: i === 0 ? "To Do" : ["To Do", "In Progress", "Done"][i % 3],
      description: "Confirm the details with the branch team and record follow-up actions.", updated_at: "2026-11-21T10:00:00Z",
    }));
    const kinds = ["product", "service", "membership"];
    const items = Array.from({length: 1800}, (_, i) => ({
      id: i + 11, kind: kinds[i % 3], code: "SKU-" + (i + 11),
      name: i === 0 ? "Coffee" : ["Wholegrain grocery pack", "Equipment maintenance service", "Wellness membership"][i % 3] + " " + i,
      description: "Branch catalog offering with standard terms and available options.",
      price: 99 + i * 13 % 5000, tax: [0,5,12,18][i % 4], currency: "INR", category: ["Retail", "Maintenance", "Wellness"][i % 3],
      status: "Active", version: 1,
    }));
    await page.route("**/api/v1/**", route => {
      if (offline) return route.abort("internetdisconnected");
      const request = route.request();
      const url = new URL(request.url());
      if (request.method() !== "GET") {
        const body = request.postDataJSON();
        if (rejectStatus && request.method() === "PATCH") return route.fulfill({status: 409, json: {detail: "Another user updated this task."}});
        const key = request.headers()["x-offline-operation"];
        assert.ok(key, "Every replay must carry its original operation ID");
        attempts.push(key);
        if (receipts.has(key)) return route.fulfill({json: receipts.get(key)});
        const collection = url.pathname.includes("/catalog/") ? items : tasks;
        const create = request.method() === "POST";
        const id = create ? 10000 + writes.length : Number(url.pathname.split("/").at(-1));
        const index = collection.findIndex(row => row.id === id);
        const previous = collection[index];
        const result = {...previous, ...body, id, updated_at: "2026-11-22T10:00:00Z", version: (previous?.version || 0) + 1};
        if (create) collection.unshift(result); else collection[index] = result;
        writes.push({path: url.pathname, method: request.method(), body});
        receipts.set(key, result);
        if (loseReply) { loseReply = false; return route.abort("connectionreset"); }
        return route.fulfill({json: result});
      }
      if (url.pathname.endsWith("/project-management/tasks")) {
        const size = Number(url.searchParams.get("pageSize") || 30);
        return route.fulfill({json: {items: tasks.slice(0, size), total: tasks.length}});
      }
      if (url.pathname.endsWith("/catalog/items")) {
        const size = Number(url.searchParams.get("per_page") || 24);
        const offset = (Number(url.searchParams.get("page") || 1) - 1) * size;
        const term = url.searchParams.get("search")?.toLowerCase() || "";
        const found = items.filter(item => (!url.searchParams.has("kind") || item.kind === url.searchParams.get("kind")) &&
          (!term || [item.name, item.code, item.description].some(value => value?.toLowerCase().includes(term))));
        return route.fulfill({json: {items: found.slice(offset, offset + size), total: found.length,
          pages: Math.ceil(found.length / size), permissions: {product: true, service: true, membership: true}}});
      }
      const detail = url.pathname.match(/\/catalog\/items\/[^/]+\/(\d+)$/);
      if (detail) return route.fulfill({json: items.find(item => item.id === Number(detail[1]))});
      return route.fulfill({json: {}});
    });
    await page.route("**/offline-work-qa", route => route.fulfill({contentType: "text/html", body: '<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"}</script>'}));
    await page.addInitScript(() => Object.defineProperty(navigator, "onLine", {get: () => sessionStorage.getItem("offline-qa") !== "1"}));
    const origin = "http://127.0.0.1:" + server.httpServer.address().port;
    await page.goto(origin + "/offline-work-qa");
    const boot = () => page.evaluate(async () => {
      const {useAuthStore} = await import("/src/store/authStore.ts");
      sessionStorage.setItem("suite-branch", "1");
      useAuthStore.setState({isAuthenticated: true, isHydrated: true, accessToken: "fixture", user: {id: 7, role: "admin", access: {companyId: 1}}});
      window.testOffline = await import("/src/lib/offline-work.ts");
      window.testTasks = (await import("/src/apps/project-management/services/api.ts")).tasksAPI;
      window.testCatalog = (await import("/src/shared/catalog/api.ts")).catalogApi;
      window.testOffline.installOfflineWork();
    });
    await boot();
    await page.evaluate(async () => {
      await window.testTasks.listAll();
      await window.testCatalog.list("srm", {include_facets: true});
    });
    await expect.poll(() => page.evaluate(async () => {
      const db = await new Promise(resolve => { const r = indexedDB.open("suite-offline-work", 1); r.onsuccess = () => resolve(r.result); });
      return new Promise(resolve => { const r = db.transaction("reads").objectStore("reads").getAllKeys(); r.onsuccess = () => { resolve(r.result.some(key => key.includes("catalog:srm:index"))); db.close(); }; });
    }), {timeout: 20000}).toBe(true);

    const measure = () => page.evaluate(async () => {
      const runs = {};
      for (const [label, run] of Object.entries({
        tasks: () => window.testTasks.listAll(),
        catalog: () => window.testCatalog.list("srm", {kind: "product", search: "grocery"}),
      })) {
        const samples = [];
        for (let i = 0; i < 30; i++) { const start = performance.now(); await run(); samples.push(performance.now() - start); }
        runs[label] = Number(samples.sort((a,b) => a-b)[28].toFixed(2));
      }
      return runs;
    });
    await measure();
    console.log("Online warm reads p95 ms", await measure());
    offline = true;
    await page.evaluate(() => { sessionStorage.setItem("offline-qa", "1"); window.dispatchEvent(new Event("offline")); });
    console.log("Offline reads p95 ms", await measure());
    const local = await page.evaluate(async () => {
      const times = [];
      const timed = async operation => { const t = performance.now(); const value = await operation(); times.push(performance.now() - t); return value; };
      const base = (await window.testTasks.listAll()).items[0];
      await timed(() => window.testTasks.saveStatusOffline(base, "In Progress"));
      await timed(() => window.testTasks.createOffline(1, {title: "Offline task", task_key: "OFFLINE-1", status: "To Do", priority: "Medium"}, "Project"));
      for (const kind of ["product", "service", "membership"]) {
        await timed(() => window.testCatalog.save("srm", {
          kind, name: "New " + kind, code: "OFFLINE-" + kind, description: "Available from the main branch",
          currency: "INR", price: kind === "product" ? 299 : 1499, tax: 18, status: "Active", version: 0,
          ...(kind === "membership" ? {plan: {duration: {unit: "month", count: 6}, activation: "purchase", benefits: []}} : {}),
        }));
      }
      for (const [kind, id, name] of [["product",11,"Coffee beans"],["service",12,"Annual equipment service"],["membership",13,"Family wellness membership"]]) {
        const {data} = await window.testCatalog.get("srm", kind, id);
        await timed(() => window.testCatalog.save("srm", {...data, name}));
      }
      return {times, rows: (await window.testTasks.listAll()).items.map(task => [task.title, task.status])};
    });
    console.log("Offline durable saves ms", local.times.map(value => Number(value.toFixed(2))));
    assert.deepEqual(local.rows.slice(0, 2), [["Offline task", "To Do"], ["Existing task", "In Progress"]]);
    assert.equal(writes.length, 0);
    await page.reload();
    await boot();
    const recovered = await page.evaluate(async () => ({
      count: (await window.testOffline.offlineChanges()).length,
      products: (await window.testCatalog.list("srm", {kind: "product", search: "coffee"})).data.items.map(item => item.name),
      editedService: (await window.testCatalog.get("srm", "service", 12)).data.name,
      editedMembership: (await window.testCatalog.get("srm", "membership", 13)).data.name,
      memberships: (await window.testCatalog.list("srm", {kind: "membership", search: "New membership"})).data.items.map(item => item.name),
    }));
    assert.deepEqual(recovered, {count: 8, products: ["Coffee beans"], memberships: ["New membership"], editedService: "Annual equipment service", editedMembership: "Family wellness membership"});
    console.log("Offline after reload, reads p95 ms", await measure());
    offline = false;
    await page.evaluate(() => { sessionStorage.removeItem("offline-qa"); window.dispatchEvent(new Event("online")); });
    await expect.poll(() => page.evaluate(async () => (await window.testOffline.offlineChanges()).filter(change => change.confirmed).length), {timeout: 20000}).toBe(8);
    assert.equal(writes.length, 8);
    assert.equal(attempts.length, 9);
    assert.equal(attempts[0], attempts[1]);
    assert.equal(new Set(attempts).size, 8);
    assert.equal(tasks.filter(task => task.task_key === "OFFLINE-1").length, 1);
    assert.equal(tasks.find(task => task.id === 7).status, "In Progress");
    for (const [offset, kind, name] of [[0, "product", "Coffee beans"], [1, "service", "Annual equipment service"], [2, "membership", "Family wellness membership"]]) {
      assert.equal(items.filter(item => item.code === "OFFLINE-" + kind).length, 1);
      const edited = items.find(item => item.id === 11 + offset);
      assert.equal(edited.name, name);
      assert.equal(edited.version, 2);
    }
    assert.equal(writes[0].body.expected_updated_at, "2026-11-21T10:00:00Z");
    rejectStatus = true;
    await page.evaluate(async () => {
      const task = (await window.testTasks.listAll()).items.find(row => row.id === 7);
      await window.testTasks.saveStatusOffline(task, "Done");
    });
    await expect.poll(() => page.evaluate(async () => (await window.testOffline.offlineChanges("tasks")).find(row => row.error)?.error))
      .toBe("Another user updated this task.");
    await page.evaluate(async () => {
      const conflict = (await window.testOffline.offlineChanges("tasks")).find(row => row.error);
      await window.testOffline.discardOfflineChange(conflict.id);
    });
    assert.equal(writes.length, 8);
    console.log("PASS offline task list, create and status, catalog search and creates, reload recovery and automatic replay");
  } finally { await browser.close(); await server.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
