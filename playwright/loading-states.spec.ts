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
      import AsyncProgress from '/src/components/app/AsyncProgress.tsx';
      import {beginProgress} from '/src/lib/async-progress.ts';
      import '/src/index.css';
      const h=React.createElement, root=ReactDOM.createRoot(document.getElementById('root'));
      const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
      window.beginProgress=beginProgress;
      window.queryClient=client;
      window.startQuery=(silent=false)=> { void client.fetchQuery({queryKey:['qa-loading',silent],queryFn:()=>new Promise(resolve=>window.finishQuery=resolve),meta:{progress:!silent}}); };
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

for (const width of [320, 1440]) {
  test(`loading, empty, populated and error choices fit at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await harness(page);
    const customer = page.getByRole("combobox", { name: "Customer" });
    await expect(customer.locator('option:disabled')).toHaveText("No data found");
    expect(await customer.evaluate((el: HTMLSelectElement) => el.checkValidity())).toBe(false);
    await page.evaluate(() => (window as any).renderChoices(true));
    await expect(customer).toHaveAttribute("aria-busy", "true");
    await expect(page.getByRole("status").filter({ hasText: "Loading choices…" })).toBeVisible();
    await expect(customer.locator("option")).not.toContainText(["No data found"]);
    const status = await page.getByRole("status").boundingBox();
    const button = await page.locator("#save").boundingBox();
    expect(status!.y + status!.height).toBeLessThanOrEqual(button!.y);
    await page.getByRole("combobox", { name: "Project" }).click();
    await expect(page.getByRole("listbox")).toContainText("Loading choices…");
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
