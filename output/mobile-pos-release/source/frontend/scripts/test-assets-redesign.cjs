const path = require("node:path");
const { chromium, expect: base } = require("playwright/test");
const expect = base.configure({ timeout: 30000 });
(async () => {
  process.chdir(path.resolve(__dirname, ".."));
  const { createServer } = await import("vite");
  const server = await createServer({
    root: process.cwd(),
    server: { host: "127.0.0.1", port: 0, hmr: false, watch: null },
  });
  await server.listen();
  const browser = await chromium.launch();
  let checks = 0;
  try {
    const page = await browser.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/api/v1/**", async (route) => {
      const u = new URL(route.request().url()),
        p = u.pathname;
      let data = [];
      if (p.endsWith("/capabilities")) data = { can_manage: true };
      else if (p.endsWith("/categories"))
        data = [
          { id: 1, name: "Equipment" },
          { id: 2, name: "Vehicles" },
        ];
      else if (p.endsWith("/summary"))
        data = {
          total: 31,
          statuses: { Available: 30, Assigned: 1 },
          categories: [
            { category_id: 1, count: 30 },
            { category_id: 2, count: 1 },
          ],
        };
      else if (/\/assets\/\d+$/.test(p))
        data = {
          id: 1,
          name: "Honda bike",
          asset_tag: "AST-0",
          serial_number: "SER-0",
          status: "Available",
          assignments: [],
          documents: [],
          approvals: [],
          timeline: [],
        };
      else if (p.endsWith("/policy"))
        data = { values: {}, can_configure: false };
      else if (p.endsWith("/assets/")) {
        data = Array.from({ length: 31 }, (_, i) => ({
          id: i + 1,
          name: i === 0 ? "Honda bike" : "Office equipment " + i,
          asset_tag: "AST-" + i,
          status: "Available",
          category_id: i === 0 ? 2 : 1,
          serial_number: "SER-" + i,
        })).filter(
          (a) =>
            (!u.searchParams.get("category_id") ||
              a.category_id === Number(u.searchParams.get("category_id"))) &&
            (!u.searchParams.get("search") ||
              a.name
                .toLowerCase()
                .includes(u.searchParams.get("search").toLowerCase())),
        );
        const start = Number(u.searchParams.get("offset") || 0);
        data = data.slice(
          start,
          start + Number(u.searchParams.get("limit") || 200),
        );
      } else if (p.endsWith("/assignments"))
        data = [
          {
            id: 1,
            asset_id: 1,
            asset_name: "Honda bike",
            asset_tag: "AST-0",
            employee_name: "Team Member",
            employee_id: 2,
            assigned_date: "2026-11-01",
            returned_date:
              u.searchParams.get("active") === "false" ? "2026-11-09" : null,
            condition_at_return: "Good",
            acknowledged: false,
          },
        ];
      else if (p.endsWith("/exit-clearance"))
        data = [
          {
            exit_id: 1,
            employee_name: "Team Member",
            last_working_date: "2026-11-15",
            cleared: false,
            outstanding_assets: [
              { assignment_id: 1, name: "Honda bike", asset_tag: "AST-0" },
            ],
          },
        ];
      if (p.endsWith("/assignments") && u.searchParams.get("paged") === "true")
        data = {
          items: data,
          total: data.length,
          summary: [{ label: "Records", value: data.length }],
        };
      await route.fulfill({ json: data });
    });
    await page.route("**/assets-qa*", (r) =>
      r.fulfill({
        contentType: "text/html",
        body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-assets.tsx");</script>',
      }),
    );
    const check = async (f) => {
      await f();
      checks++;
    };
    for (const width of [390, 768, 1280, 1720]) {
      await page.setViewportSize({ width, height: 1100 });
      await page.goto(
        "http://127.0.0.1:" + server.httpServer.address().port + "/assets-qa",
      );
      await check(() =>
        expect(
          page.getByRole("heading", { name: "Company Assets", exact: true }),
        ).toBeVisible(),
      );
      await check(() =>
        expect(
          page.getByRole("button", { name: /Total assets/ }),
        ).toContainText("31"),
      );
      await check(() =>
        expect(page.locator(".asset-table tbody tr")).toHaveCount(25),
      );
      await check(async () => {
        await page.getByLabel("Filter category").selectOption("2");
        await expect(page.locator(".asset-table tbody tr")).toHaveCount(1);
      });
      await page.getByLabel("Filter category").selectOption("");
      await check(async () => {
        await page
          .getByRole("button", { name: "Next page", exact: true })
          .click();
        await expect(page.locator(".asset-table tbody tr")).toHaveCount(6);
      });
      await page
        .getByRole("button", { name: "Previous page", exact: true })
        .click();
      await check(async () => {
        await page
          .getByRole("button", { name: "Card view", exact: true })
          .click();
        await expect(page.locator(".asset-item-card")).toHaveCount(25);
      });
      await page
        .getByRole("button", { name: "Table view", exact: true })
        .click();
      await check(async () => {
        await page
          .getByRole("button", { name: "Honda bike AST-0", exact: true })
          .click();
        await expect(page.getByRole("dialog")).toContainText("SER-0");
        await page
          .getByRole("button", { name: "Close dialog", exact: true })
          .click();
      });
      await check(async () => {
        await page.getByLabel("Search asset register").fill("Honda");
        await expect(page.locator(".asset-table tbody tr")).toHaveCount(1);
      });
      await check(async () => {
        await page.getByLabel("Search asset register").fill("nonexistent");
        await expect(
          page.getByText("No assets found", { exact: true }),
        ).toBeVisible();
      });
      await check(async () => {
        await page
          .getByRole("button", { name: "Employee custody", exact: true })
          .click();
        await expect(page.locator(".asset-table")).toContainText(
          "Acknowledgment pending",
        );
      });
      await check(async () => {
        await page
          .getByRole("button", { name: "Return history", exact: true })
          .click();
        await expect(page.locator(".asset-table")).toContainText("Good");
      });
      await check(async () => {
        await page
          .getByRole("button", { name: "Exit clearance", exact: true })
          .click();
        await expect(page.locator(".asset-table")).toContainText(
          "Awaiting return",
        );
      });
      await check(async () => {
        await page
          .getByRole("button", { name: "View details", exact: true })
          .click();
        await expect(page.getByRole("dialog")).toContainText(
          "department approvals",
        );
        await page
          .getByRole("button", { name: "Close dialog", exact: true })
          .click();
      });
      await check(async () => {
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
        ).toBe(true);
      });
    }
    await page.getByRole("button", { name: "Inventory", exact: true }).click();
    await page.getByLabel("Search asset register").fill("");
    await page.screenshot({
      path: path.resolve(
        __dirname,
        "../../outputs/assets-redesign-desktop.png",
      ),
      fullPage: true,
    });
    expect(errors).toEqual([]);
    console.log(
      "PASS: " + checks + " browser checks across four viewport sizes.",
    );
  } finally {
    await browser.close();
    await server.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
