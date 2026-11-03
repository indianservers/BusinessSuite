import { test, expect, type Page, type Locator } from "../frontend/node_modules/playwright/test";
import fs from "node:fs";
import path from "node:path";

test.beforeEach(async ({ page, request }) => {
  const response = await request.post("http://127.0.0.1:1551/api/v1/auth/login", {
    data: { email: "admin@suiteqa.example.com", password: "SuiteQA@12345" },
  });
  expect(response.ok()).toBeTruthy();
  const tokens = await response.json();
  const access = await request.get("http://127.0.0.1:1551/api/v1/access/me", { headers: { Authorization: `Bearer ${tokens.access_token}` } });
  const user = { id: tokens.user_id, email: tokens.email, role: tokens.role, is_superuser: tokens.is_superuser, access: await access.json() };
  await page.addInitScript(({ tokens, user }) => {
    sessionStorage.setItem("hrms-auth", JSON.stringify({ state: { accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user, isAuthenticated: true }, version: 0 }));
  }, { tokens, user });
});

async function withinViewport(page: Page, element: Locator) {
  const box = await element.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
}

async function responsivePage(page: Page) {
  const layout = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth <= innerWidth + 1,
    main: [...document.querySelectorAll("main")].every(main => main.scrollWidth <= main.clientWidth + 1),
    clippedControls: [...document.querySelectorAll(".kf-topbar button,.kf-topbar select,.ws-topbar button,.ws-topbar select,.tr-topbar button,.tr-topbar select")].filter(el => {
      const rect = el.getBoundingClientRect();
      return rect.width && rect.height && getComputedStyle(el).visibility !== "hidden" && (rect.x < -1 || rect.right > innerWidth + 1);
    }).map(el => el.getAttribute("aria-label") || el.textContent),
  }));
  const details = await page.evaluate(() => JSON.stringify({
    path: location.pathname, width: innerWidth,
    overflowing: [...document.querySelectorAll("main *")].filter(el => {
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.right > innerWidth + 1;
    }).slice(0, 6).map(el => ({ class: el.className, text: el.textContent?.slice(0, 40), width: el.getBoundingClientRect().width })),
  }));
  expect(layout, details).toEqual({ document: true, main: true, clippedControls: [] });
}

for (const app of ["srm", "crm", "project-management"]) {
  test(`${app} route inventory fits mobile`, async ({ page }, info) => {
    test.skip(info.project.name === "tablet", "Full route sweep runs at both phone widths.");
    test.setTimeout(600_000);
    const source = fs.readFileSync(path.resolve(__dirname, `../frontend/src/apps/${app}/routes.tsx`), "utf8");
    const routes = [...new Set([...source.matchAll(/(?:path\s*:\s*|(?:route|inventoryRoute|inventorySourceRoute)\()\s*["']((?:srm|crm|pms)[^"']*)["']/g)].map(match => "/" + match[1].replace(/:[\w]+/g, "1")))];
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    for (const route of routes) {
      await test.step(route, async () => {
        await page.goto(route);
        await expect(page.locator("#root")).not.toBeEmpty();
        await page.waitForLoadState("networkidle", { timeout: 2_000 }).catch(() => undefined);
        await expect(page.getByText("Something went wrong", { exact: true })).toHaveCount(0);
        await responsivePage(page);
        expect(errors).toEqual([]);
      });
    }
  });
}

test("POS products, cart and checkout dialogs stay usable", async ({ page }) => {
  await page.route("**/api/v1/srm/inventory/items?**", route => route.fulfill({ json: {
    total: 1, items: [{ id: 9001, item_name: "Mobile test product with a long descriptive name for narrow screens", sku: "MOB-01-LONG-PRODUCT-CODE", sales_rate: 123456789.99, current_quantity: 20, gst_rate: 18, active: true, unit_code: "PCS" }],
  } }));
  await page.goto("/srm/pos");
  await page.getByRole("button", { name: "Session & actions", exact: true }).click();
  await page.getByRole("button", { name: "Cash drawer", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Cash Drawer Movement" })).toBeVisible();
  await withinViewport(page, page.getByRole("dialog"));
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Session & actions", exact: true }).click();
  await page.getByRole("button", { name: /Mobile test product/ }).first().click();
  await page.getByRole("button", { name: "Cart (1)", exact: true }).click();
  await expect(page.locator("aside.srm-pos-cart")).toBeVisible();
  await expect(page.locator(".srm-pos-catalog")).toBeHidden();
  await page.locator(".srm-pos-checkout").getByRole("button", { name: "Payment", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await withinViewport(page, dialog);
  await expect(page.locator(".pms-ai-launcher")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "Quick add", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await withinViewport(page, page.getByRole("dialog"));
  await page.getByRole("button", { name: "Close quick add customer" }).click();
  await responsivePage(page);
});

test("CRM lead form and navigation drawer fit phones", async ({ page }) => {
  await page.goto("/crm/leads");
  await page.getByRole("button", { name: "Add lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await withinViewport(page, page.getByRole("dialog"));
  await expect(page.locator(".pms-ai-launcher")).toBeHidden();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  const navigation = page.getByRole("dialog", { name: "Application navigation" });
  await expect(navigation).toBeVisible();
  await withinViewport(page, navigation);
  await page.getByRole("button", { name: "Close navigation", exact: true }).click();
  await responsivePage(page);
});

test("PMS workspace and task headers keep controls on screen", async ({ page }) => {
  await page.goto("/pms/workspaces");
  await expect(page.locator(".ws-topbar")).toBeVisible();
  await responsivePage(page);
  await page.getByRole("button", { name: "Create workspace", exact: true }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await withinViewport(page, page.getByRole("dialog"));
  await page.keyboard.press("Escape");
  await page.goto("/pms/tasks");
  await expect(page.getByRole("heading", { name: "Tasks", exact: true })).toBeVisible();
  await responsivePage(page);
});

test("headers fit intermediate and desktop widths", async ({ page }, info) => {
  test.skip(info.project.name !== "tablet", "Run this viewport matrix once.");
  for (const width of [1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of ["/srm/pos", "/crm/leads", "/pms/tasks", "/pms/workspaces"]) {
      await page.goto(route);
      await page.waitForLoadState("networkidle", { timeout: 2_000 }).catch(() => undefined);
      await responsivePage(page);
    }
  }
});

test("SRM catalog and inventory source aliases fit mobile", async ({ page }, info) => {
  test.skip(info.project.name !== "phone-small", "Aliases use the same page components; check the narrowest viewport.");
  test.setTimeout(300_000);
  const source = fs.readFileSync(path.resolve(__dirname, "../frontend/src/apps/inventory/sourceCatalog.ts"), "utf8");
  const routes = [...new Set([
    "/srm/products-services", "/srm/products", "/srm/services", "/srm/pos/products",
    ...[...source.matchAll(/appPath:\s*["']([^"']+)["']/g)].map(match => match[1]),
  ])];
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const route of routes) {
    await test.step(route, async () => {
      await page.goto(route);
      await page.waitForLoadState("networkidle", { timeout: 2_000 }).catch(() => undefined);
      await responsivePage(page);
      expect(errors).toEqual([]);
    });
  }
});
