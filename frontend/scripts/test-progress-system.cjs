const assert = require("node:assert/strict"),
  { build } = require("esbuild"),
  { chromium } = require("playwright"),
  fs = require("node:fs"),
  path = require("node:path");
(async () => {
  const root = path.resolve(__dirname, "..");
  const source = `import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter,useNavigate}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Host from './src/components/app/AsyncProgress';import{progress,getOperations,beginProgress}from './src/lib/async-progress';import{LoadingState}from './src/components/ui/state';import{Button}from './src/components/ui/button';import{useLoadingContext}from './src/hooks/use-loading-context';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});window.progress=progress;window.state=getOperations;window.legacy=beginProgress;function App(){const navigate=useNavigate(),context=useLoadingContext();window.navigate=navigate;return <><Host/><h1>{context.resource}</h1><button onClick={()=>progress.start({id:'keyboard',title:'Generating Sales Report',mode:'modal',cancellable:true,onCancel:()=>{window.cancelled=true}})}>Generate report</button><LoadingState/><Button loading loadingLabel="Saving Changes">Save</Button></>};createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/crm/deals']}><App/></MemoryRouter></QueryClientProvider>);`;
  const built = await build({
    stdin: { contents: source, loader: "tsx", resolveDir: root },
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    alias: { "@": path.join(root, "src") },
    define: { "import.meta.env": "{}" },
    loader: { ".css": "empty" },
  });
  const browser = await chromium.launch({ headless: true }),
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("http://loading.test/**", (r) =>
    r.fulfill({
      contentType: "text/html",
      body: '<html><body><div id="root"></div></body></html>',
    }),
  );
  await page.goto("http://loading.test");
  await page.addStyleTag({
    content:
      ":root{--card:0 0% 100%;--card-foreground:240 20% 12%;--background:0 0% 100%;--foreground:240 20% 12%;--border:250 25% 88%;--muted:250 25% 95%;--muted-foreground:245 10% 45%}body{font-family:Arial;margin:30px;background:#f5f4fb}button{cursor:pointer}*{box-sizing:border-box}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.dark{--card:246 25% 13%;--card-foreground:250 40% 95%;--background:246 25% 10%;--foreground:250 40% 95%;--border:246 20% 28%;--muted-foreground:245 15% 70%}" +
      fs.readFileSync(
        path.join(root, "src/components/app/async-progress.css"),
        "utf8",
      ),
  });
  await page.addScriptTag({ content: built.outputFiles[0].text });
  await page.getByRole("heading", { name: "Deals", exact: true }).waitFor();
  const clear = () =>
    page.evaluate(() => {
      for (const op of [...window.state().active, ...window.state().settled])
        window.progress.dismiss(op.id);
    });
  await page.evaluate(
    () => (window.finish = window.legacy("Saving Employee Records")),
  );
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page
    .getByRole("progressbar", { name: "Saving Employee Records" })
    .waitFor();
  await page.evaluate(() => {
    window.finish();
    window.finish(false);
  });
  assert.equal(await page.getByRole("progressbar").count(), 0);
  for (const route of [
    "/crm/contacts",
    "/pms/projects",
    "/hrms/employees",
    "/srm/invoices",
    "/srm/inventory",
    "/fam/settings",
    "/settings",
  ]) {
    await page.evaluate((r) => window.navigate(r), route);
    await page.waitForTimeout(30);
    const label = await page
      .locator("[aria-busy=true]")
      .first()
      .getAttribute("aria-label");
    assert(
      label && label !== "Loading data" && !label.includes("/"),
      `${route}: ${label}`,
    );
  }
  await page.evaluate(() => window.navigate("/crm/deals"));
  await page.waitForTimeout(30);
  await page.evaluate(
    () =>
      (window.handle = window.progress.start({
        id: "form",
        title: "Preparing New Deal",
        mode: "modal",
        steps: [
          { id: "fields", label: "Loading custom fields", status: "active" },
          { id: "layout", label: "Preparing form layout", status: "pending" },
        ],
      })),
  );
  await page.getByRole("dialog").waitFor();
  assert.equal(await page.getByRole("dialog").count(), 1);
  assert.equal(
    await page
      .getByRole("dialog")
      .getByRole("progressbar")
      .getAttribute("aria-valuenow"),
    null,
  );
  assert.equal(
    await page.getByRole("button", { name: "Cancel", exact: true }).count(),
    0,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Run in background", exact: true })
      .count(),
    0,
  );
  await page.waitForTimeout(300);
  assert.equal(
    await page
      .getByRole("dialog")
      .getByRole("progressbar")
      .getAttribute("aria-valuenow"),
    null,
  );
  await page.evaluate(() =>
    window.handle.update({
      progress: 45,
      steps: [
        { id: "fields", label: "Loading custom fields", status: "completed" },
        { id: "layout", label: "Preparing form layout", status: "active" },
      ],
    }),
  );
  await page.getByText("45%", { exact: true }).waitFor();
  await page.evaluate(() =>
    window.progress.start({
      id: "second",
      title: "Generating Invoice",
      mode: "modal",
    }),
  );
  assert.equal(await page.getByRole("dialog").count(), 1);
  await page.evaluate(() => window.progress.dismiss("second"));
  fs.mkdirSync(path.join(root, "../outputs"), { recursive: true });
  await page.screenshot({
    path: path.join(root, "../outputs/smart-progress-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await page.screenshot({
    path: path.join(root, "../outputs/smart-progress-mobile.png"),
  });
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await page.screenshot({
    path: path.join(root, "../outputs/smart-progress-dark.png"),
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await page
      .locator(".smart-progress-steps [data-state=active] svg")
      .evaluate((e) => getComputedStyle(e).animationName),
    "none",
  );
  await clear();
  await page
    .getByRole("button", { name: "Generate report", exact: true })
    .click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  assert(await page.evaluate(() => window.cancelled));
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.evaluate(() =>
    window.progress.start({
      id: "job",
      title: "Exporting Customer Records",
      mode: "modal",
      backgroundable: true,
      successTitle: "Customer Export Ready",
    }),
  );
  await page.getByRole("button", { name: "Run in background" }).click();
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.evaluate(() => window.navigate("/pms/projects"));
  await page.waitForTimeout(30);
  assert.equal(await page.evaluate(() => window.state().active.length), 1);
  await page.evaluate(() => window.progress.complete("job"));
  await page.getByRole("button", { name: /Customer Export Ready/ }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByRole("button", { name: "Dismiss", exact: true }).click();
  await page.evaluate(() => {
    const old = window.progress.start({
      id: "reuse",
      title: "Loading Old Record",
    });
    old.dispose();
    const next = window.progress.start({
      id: "reuse",
      title: "Loading New Record",
    });
    old.complete();
    old.update({ title: "Wrong title" });
    if (window.state().active[0].title !== "Loading New Record")
      throw Error("stale handle");
    next.dispose();
  });
  await page.evaluate(() =>
    window.progress.start({
      id: "failure",
      title: "Importing Customers",
      mode: "modal",
      errorTitle: "Customer Import Failed",
    }),
  );
  await page.evaluate(() =>
    window.progress.fail("failure", "Server rejected invalid rows"),
  );
  await page.getByText("Customer Import Failed", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Dismiss", exact: true }).click();
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.evaluate(() =>
    window.progress.start({
      id: "orphan",
      title: "Preparing New Deal",
      mode: "modal",
    }),
  );
  await page.evaluate(() => window.navigate("/hrms/employees"));
  await page.waitForTimeout(50);
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.deepEqual(errors, []);
  console.log(
    "PASS: titles across 7 module routes, micro/legacy lifecycle, determinate/indeterminate progress, concurrency, cancellation, background continuation, stale handles, failures, route cleanup, responsive/dark/reduced-motion",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
