import { test, expect, type Page } from "../frontend/node_modules/playwright/test";

async function harness(page: Page) {
  const source = await (await page.request.get("/src/main.tsx")).text();
  const dependency = (name: string) => {
    const found = source.match(new RegExp(`from ["']([^"']*/${name}\\.js[^"']*)["']`));
    if (!found) throw new Error(`Missing Vite dependency ${name}`);
    return found[1];
  };
  await page.route("**/__qa/loading", route => route.fulfill({ contentType: "text/html", body: `
    <html><head><script type="module">
      import RefreshRuntime from '/@react-refresh';
      RefreshRuntime.injectIntoGlobalHook(window);
      window.$RefreshReg$ = () => {};
      window.$RefreshSig$ = () => (type) => type;
      window.__vite_plugin_react_preamble_installed__ = true;
    </script></head><body><div id="root"></div><script type="module">
      import React from ${JSON.stringify(dependency("react"))};
      import ReactDOM from ${JSON.stringify(dependency("react-dom_client"))};
      import {QueryClient,QueryClientProvider} from ${JSON.stringify(dependency("@tanstack_react-query"))};
      import {NativeSelect} from '/src/components/ui/native-select.tsx';
      import {ChoiceStatus} from '/src/components/ui/choice-status.tsx';
      import {Select,SelectTrigger,SelectValue,SelectContent,SelectItem} from '/src/components/ui/select.tsx';
      import {Dialog,DialogContent,DialogTitle} from '/src/components/ui/dialog.tsx';
      import DealRecordSelect from '/src/apps/crm/deals/DealRecordSelect.tsx';
      import DealCatalogSelect from '/src/apps/crm/deals/DealCatalogSelect.tsx';
      import AsyncProgress from '/src/components/app/AsyncProgress.tsx';
      import {beginProgress} from '/src/lib/async-progress.ts';
      import '/src/index.css';
      const h=React.createElement, root=ReactDOM.createRoot(document.getElementById('root'));
      const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
      window.beginProgress=beginProgress;
      window.queryClient=client;
      window.startQuery=(silent=false)=> { void client.fetchQuery({queryKey:['qa-loading',silent],queryFn:()=>new Promise(resolve=>window.finishQuery=resolve),meta:{progress:!silent}}); };
      window.renderGrouped=(loading)=>root.render(h(NativeSelect,{'aria-label':'Grouped customer',loading,defaultValue:''},
        h(React.Fragment,null,h('optgroup',{label:'Customers'},h('option',{value:''},'Choose customer'),h('option',{value:'acme'},'Acme')))));
      window.renderDialog=()=>root.render(h(Dialog,{open:true},h(DialogContent,{className:'z-[111]',overlayClassName:'z-[110]'},h(DialogTitle,null,'Lookup dialog'),
        h(Select,{loading:true,error:true},h(SelectTrigger,{'aria-label':'Dialog project'},h(SelectValue,{placeholder:'Choose project'})),h(SelectContent,null)))));
      window.renderLookup=(catalog)=>root.render(catalog ? h(DealCatalogSelect,{initial:[{id:7,name:'Saved customer item',catalogKind:'product'}],value:'product:7',onSelect:()=>{}})
        : h(DealRecordSelect,{resource:'companies',initial:[{id:7,name:'Saved customer'}],value:'7',onChange:()=>{},name:'Company'}));
      window.renderChoices=(loading=false,rows=[],error=false)=>root.render(h(QueryClientProvider,{client},
        h(React.Fragment,null,h(AsyncProgress),h('main',{style:{padding:'20px',maxWidth:'320px'}},
          h('form',{id:'choices'},h('label',null,'Customer',h(NativeSelect,{'aria-label':'Customer',name:'customer',required:true,loading,error,defaultValue:'',style:{width:'100%',height:'40px'}},
            h('option',{value:''},'Choose customer'),rows.map(r=>h('option',{key:r,value:r},r)))),
            h(ChoiceStatus,{loading,empty:!rows.length,error}),h('button',{type:'button',id:'save'},'Save')),
          h(Select,{loading,error},h(SelectTrigger,{'aria-label':'Project'},h(SelectValue,{placeholder:'Choose project'})),
            h(SelectContent,null,rows.map(r=>h(SelectItem,{key:r,value:r},r))))))));
      window.renderChoices();
    </script></body></html>` }));
  await page.goto("/__qa/loading");
  await expect(page.getByRole("combobox", { name: "Customer" })).toBeVisible();
}

test("nested option groups have a single loading placeholder and retain values", async ({ page }) => {
  await harness(page);
  await page.evaluate(() => (window as any).renderGrouped(true));
  const grouped = page.getByRole("combobox", { name: "Grouped customer" });
  await expect(grouped.locator('option').filter({ hasText: "Loading choices…" })).toHaveCount(1);
  await expect(grouped.locator('option').filter({ hasText: "Choose customer" })).toHaveCount(0);
  await page.evaluate(() => (window as any).renderGrouped(false));
  await grouped.selectOption("acme");
  await expect(grouped).toHaveValue("acme");
});

for (const catalog of [false, true]) {
  test(`${catalog ? "Catalog" : "Record"} lookup shows no matches while retaining a saved selection`, async ({ page }) => {
    await page.route("**/api/v1/crm/**", route => route.fulfill({ json: { items: [], pages: 1, total: 0 } }));
    await harness(page);
    await page.evaluate(value => (window as any).renderLookup(value), catalog);
    await expect(page.getByRole("status")).toHaveText("No data found");
    const select = page.getByRole("combobox", { name: catalog ? "Catalog item" : "Company", exact: true });
    await expect(select).toHaveValue(catalog ? "product:7" : "7");
  });
}

test("loading popup stays above a dialog and inside the mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await harness(page);
  await page.evaluate(() => (window as any).renderDialog());
  await page.getByRole("combobox", { name: "Dialog project" }).click();
  const list = page.getByRole("listbox");
  await expect(list).toContainText("Loading choices…");
  await expect(list.getByRole("status")).toBeVisible();
  expect(await list.evaluate(el => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return { onTop: !!top && el.contains(top), fits: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight };
  })).toEqual({ onTop: true, fits: true });
});

for (const width of [320, 1440]) {
  test(`loading, empty, populated and error choices fit at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await harness(page);
    const customer = page.getByRole("combobox", { name: "Customer" });
    await expect(customer.locator('option:disabled')).toHaveText("No data found");
    expect(await customer.evaluate((el: HTMLSelectElement) => el.checkValidity())).toBe(false);
    await page.evaluate(() => (window as any).renderChoices(true));
    await expect(customer).toHaveAttribute("aria-busy", "true");
    await expect(customer.locator('option').filter({ hasText: "Loading choices…" })).toHaveCount(1);
    await expect(page.getByRole("status").filter({ hasText: "Loading choices…" })).toBeVisible();
    await expect(customer.locator("option")).not.toContainText(["No data found"]);
    const status = await page.getByRole("status").boundingBox();
    const button = await page.locator("#save").boundingBox();
    expect(status!.y + status!.height).toBeLessThanOrEqual(button!.y);
    await page.getByRole("combobox", { name: "Project" }).click();
    await expect(page.getByRole("listbox")).toContainText("Loading choices…");
    const popup = await page.getByRole("listbox").boundingBox();
    expect(popup!.x).toBeGreaterThanOrEqual(0);
    expect(popup!.x + popup!.width).toBeLessThanOrEqual(width);
    await page.keyboard.press("Escape");
    await page.evaluate(() => (window as any).renderChoices(false, ["Acme"]));
    await customer.selectOption("Acme");
    expect(await customer.evaluate((el: HTMLSelectElement) => new FormData(el.form!).get("customer"))).toBe("Acme");
    await expect(customer.locator('option:disabled')).toHaveCount(0);
    await page.evaluate(() => (window as any).renderChoices(false, [], true));
    await expect(customer.locator('option:disabled')).toHaveText("Could not load choices");
    await expect(page.getByRole("status")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("global progress tracks concurrent work and never blocks controls", async ({ page }) => {
  await harness(page);
  await page.evaluate(() => { (window as any).finishFirst = (window as any).beginProgress("Loading records"); (window as any).finishSecond = (window as any).beginProgress("Loading options"); });
  await expect(page.getByRole("progressbar")).toBeVisible();
  expect(await page.getByRole("progressbar").evaluate(el => getComputedStyle(el).pointerEvents)).toBe("none");
  const bar = await page.getByRole("progressbar").boundingBox();
  const button = await page.locator("#save").boundingBox();
  expect(bar!.y + bar!.height).toBeLessThan(button!.y);
  await page.locator("#save").click();
  await page.evaluate(() => (window as any).finishFirst());
  await expect(page.getByRole("progressbar")).toBeVisible();
  await page.evaluate(() => (window as any).finishSecond(false, "Unavailable"));
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await page.evaluate(() => (window as any).startQuery());
  await expect(page.getByRole("progressbar")).toBeVisible();
  await page.evaluate(() => (window as any).finishQuery([]));
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await page.evaluate(() => (window as any).startQuery(true));
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await page.evaluate(() => (window as any).finishQuery([]));
});
