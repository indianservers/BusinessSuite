import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";
import { getOperationWorkspace, navigationOperationPath, isStandaloneSrmOperation } from "../frontend/src/lib/navigation-workspaces";
import {commonRouteContext,isCommercialEntity} from '../frontend/src/lib/common-routes';

test("every registered SRM page and legacy URL renders or enforces its pack restriction", async ({ page }, testInfo) => {
  test.setTimeout(360_000);
  await authenticate(page, "admin");
  await page.goto("/srm/dashboard");
  const inventory = await page.evaluate(async () => {
    const source = "/src/apps/srm/routes.tsx";
    const { srmRoutes } = await import(/* @vite-ignore */ source);
    return srmRoutes.map((route: {path:string}) => "/" + route.path);
  });
  expect(new Set(inventory).size).toBe(inventory.length);
  const results: {route:string;url:string;errors:string[];status:string}[] = [];
  let active: typeof results[number] | undefined;
  page.on("pageerror", error => active?.errors.push((error.stack || error.message).split("\n").slice(0,4).join("\n")));
  for (const pattern of inventory as string[]) {
    const id = pattern.includes("billing-plans") ? "4" : pattern.includes("engagements") ? "2" : "1";
    const route = pattern.replace(/:id\b/g, id);
    active = {route,url:"",errors:[],status:"pending"};
    results.push(active);
    try {
      await page.evaluate(destination => new Promise<void>(resolve => {
        window.history.pushState({}, "", destination);
        window.dispatchEvent(new PopStateEvent("popstate"));
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }), route);
      await page.waitForLoadState("networkidle", {timeout:10_000});
      const main = page.locator("#suite-main");
      if (["/srm/restaurant-kitchen", "/srm/accounts-periods"].includes(route)) {
        await expect(page.getByText("403 Access Denied", {exact:false})).toBeVisible();
        active.status = "pack-restricted";
      } else {
        const workspace = getOperationWorkspace(route);
        if (workspace) {
          await expect.poll(() => {
            const current = new URL(page.url());
            return navigationOperationPath(current.searchParams.get("operation") || current.pathname + current.search);
          }).toBe(navigationOperationPath(route));
          const current=new URL(page.url()),shared=commonRouteContext(current.pathname,current.search);
          await expect(main.locator('[id^="operation-panel-"]:visible')).toHaveCount((shared&&isCommercialEntity(shared.entity))||isStandaloneSrmOperation(route)?0:1);
        }
        await expect(main).not.toBeEmpty();
        expect(await main.innerText()).not.toMatch(/Something went wrong|This commercial page is unavailable|The module providing this shared page is not installed|403 Access Denied/);
        await expect(page.locator("vite-error-overlay")).toHaveCount(0);
        active.status = "rendered";
      }
      expect(active.errors).toEqual([]);
    } catch (error) {
      active.status = "failed";
      active.errors.push(String(error).slice(0,1800));
      console.log("SRM route failed:", route, active.errors.join("; ").slice(0,600));
      await page.reload({waitUntil:"domcontentloaded"});
    }
    active.url = page.url();
    if (results.length % 20 === 0) console.log(`Checked ${results.length}/${inventory.length} SRM routes`);
  }
  await testInfo.attach("SRM route audit", {body:JSON.stringify(results,null,2),contentType:"application/json"});
  expect(results.filter(result => result.status === "failed")).toEqual([]);
});

test("stock tabs remain usable on mobile with one selected panel", async ({ page }, testInfo) => {
  await page.setViewportSize({width:390,height:844});
  await authenticate(page,"srm_admin");
  await page.goto("/srm/inventory");
  const tabs = page.getByRole("tablist", {name:"Stock & warehouses operations"});
  await expect(tabs).toBeVisible();
  for (const label of ["Warehouses","Reorder Alerts","Stock Summary","Stock overview"]) {
    await tabs.getByRole("tab", {name:label,exact:true}).click();
    await expect(tabs.getByRole("tab", {name:label,exact:true})).toHaveAttribute("aria-selected","true");
    await expect(page.locator('[id^="operation-panel-"]:visible')).toHaveCount(1);
  }
  expect(await tabs.evaluate(element => element.getBoundingClientRect().right <= window.innerWidth)).toBe(true);
  await page.screenshot({path:testInfo.outputPath("stock-mobile.png"),fullPage:true});
});
