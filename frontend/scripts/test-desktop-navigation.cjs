const { build } = require("esbuild"),
  { chromium } = require("playwright"),
  assert = require("node:assert/strict"),
  path = require("node:path"),
  fs = require("node:fs");
(async () => {
  const root = path.resolve(__dirname, "..");
  const source = `import React,{Suspense,useEffect,useState}from'react';import{createRoot}from'react-dom/client';import{BrowserRouter,Routes,Route,Outlet,Link,useNavigate,useLocation}from'react-router-dom';import RouteContent from './src/components/app/RouteContent';import ErrorBoundary from './src/components/app/ErrorBoundary';import RoutePrefetch from './src/components/app/RoutePrefetch';import{lazyRoute}from'./src/lib/lazy-route';import{navigationViews,presentationSearch}from'./src/lib/navigation-views';import{useRouteViewState}from'./src/hooks/use-route-view-state';import{useAuthStore}from'./src/store/authStore';window.loads=0;window.mounts=0;window.views=navigationViews;window.presentation=presentationSearch;useAuthStore.setState({isAuthenticated:true,user:{id:1,email:'fixture@test.invalid',role:'admin',is_superuser:true}});function Page({name}){const location=useLocation();const[view,setView]=useRouteViewState("view","table");return <article style={{height:2400}}><h1>{name}</h1><button onClick={()=>setView("board")}>Choose board view</button><p id="retained-view">{view}</p><p id="query">{location.search}</p></article>};const deferred=name=>lazyRoute(()=>{window.loads++;return new Promise(resolve=>setTimeout(()=>resolve({default:()=> <Page name={name}/>}),600))});const Projects=deferred('Projects'),Contacts=deferred('Contacts'),Employees=deferred('Employees');let tries=0;const Recover=lazyRoute(()=>++tries===1?Promise.reject(Error('Failed to fetch dynamically imported module')):Promise.resolve({default:()=> <Page name='Recovered page'/>}));const routes=[{path:'crm/retry',element:<Recover/>},{path:'pms/projects',element:<Projects/>},{path:'crm/contacts',element:<Contacts/>},{path:'hrms/employees',element:<Employees/>}];function Shell(){const nav=useNavigate();window.navigate=nav;const[collapsed,setCollapsed]=useState(false);useEffect(()=>{window.mounts++;},[]);return <><header data-header>Persistent header</header><aside data-sidebar><button onClick={()=>setCollapsed(v=>!v)}>{collapsed?'Expand sidebar':'Collapse sidebar'}</button><Link to="/crm/deals">Deals</Link><Link to="/pms/projects">Projects</Link><Link to="/crm/contacts">Contacts</Link><Link to="/hrms/employees">Employees</Link><a href="https://example.com" target="_blank" rel="noreferrer">External</a></aside><main id="suite-main" data-navigation-scroll style={{height:500,overflow:'auto'}}>{window.baseline?<Outlet/>:<ErrorBoundary><RouteContent><Suspense fallback={<p role="status">Loading content</p>}><Outlet/></Suspense></RouteContent></ErrorBoundary>}</main></>};createRoot(document.getElementById('root')).render(<BrowserRouter>{!window.baseline&&<RoutePrefetch routes={routes}/>}<Suspense fallback={<p role="status">Loading content</p>}><Routes><Route element={<Shell/>}><Route path="/crm/deals" element={<Page name="Deals"/>}/>{routes.map(r=><Route key={r.path} path={r.path} element={r.element}/>)}</Route></Routes></Suspense></BrowserRouter>);`;
  const built = await build({
    stdin: { contents: source, resolveDir: root, loader: "tsx" },
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    alias: { "@": path.join(root, "src") },
    define: { "import.meta.env": "{}" },
    loader: { ".css": "empty" },
  });
  const browser = await chromium.launch();
  const result = {};
  try {
    for (const mode of ["before", "after"]) {
      const page = await browser.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.route("http://navigation.test/**", (route) =>
        route.fulfill({
          contentType: "text/html",
          body:
            '<!doctype html><div id="root"></div><script>window.baseline=' +
            String(mode === "before") +
            ";" +
            built.outputFiles[0].text +
            "</script>",
        }),
      );
      await page.goto("http://navigation.test/crm/deals");
      await page.getByRole("heading", { name: "Deals", exact: true }).waitFor();
      await page.getByRole("button", { name: "Collapse sidebar" }).click();
      await page.evaluate(() => window.navigate("/pms/projects"));
      await page.waitForTimeout(300);
      const headerVisible = await page.locator("[data-header]").isVisible();
      await page
        .getByRole("heading", { name: "Projects", exact: true })
        .waitFor();
      result[mode] = {
        headerVisibleDuringColdLoad: headerVisible,
        shellMounts: await page.evaluate(() => window.mounts),
      };
      if (mode === "after") {
        assert.equal(headerVisible, true);
        await page.getByRole("button", { name: "Expand sidebar" }).waitFor();
        await page.evaluate(() =>
          Object.defineProperty(navigator, "connection", {
            configurable: true,
            value: { saveData: true, effectiveType: "4g" },
          }),
        );
        const loadsBefore = await page.evaluate(() => window.loads);
        await page
          .getByRole("link", { name: "Employees", exact: true })
          .hover();
        await page.waitForTimeout(150);
        assert.equal(await page.evaluate(() => window.loads), loadsBefore);
        await page.evaluate(() => (navigator.connection.saveData = false));
        await page
          .getByRole("link", { name: "Employees", exact: true })
          .focus();
        await page.waitForTimeout(750);
        const started = await page.evaluate(() => performance.now());
        await page
          .getByRole("link", { name: "Employees", exact: true })
          .click();
        await page
          .getByRole("heading", { name: "Employees", exact: true })
          .waitFor();
        result.after.prefetchedClickToContentMs = Number(
          ((await page.evaluate(() => performance.now())) - started).toFixed(1),
        );
        await page.evaluate(() => window.navigate("/crm/deals?view=board"));
        await page
          .getByRole("heading", { name: "Deals", exact: true })
          .waitFor();
        await page.getByRole("button", { name: "Choose board view" }).click();
        await page.locator("#suite-main").evaluate((e) => (e.scrollTop = 400));
        await page.waitForTimeout(30);
        await page.evaluate(() => window.navigate("/crm/contacts"));
        await page
          .getByRole("heading", { name: "Contacts", exact: true })
          .waitFor();
        await page.evaluate(() => window.navigate("/crm/deals"));
        await page.waitForFunction(() => location.search === "?view=board");
        assert.equal(await page.locator("#retained-view").innerText(), "board");
        await page.waitForFunction(
          () => document.querySelector("#suite-main").scrollTop === 400,
        );
        await page.goBack();
        await page
          .getByRole("heading", { name: "Contacts", exact: true })
          .waitFor();
        await page.goForward();
        await page
          .getByRole("heading", { name: "Deals", exact: true })
          .waitFor();
        assert.equal(await page.evaluate(() => window.mounts), 1);
        assert.equal(
          await page.evaluate(
            () => performance.getEntriesByType("navigation").length,
          ),
          1,
        );
        await page.evaluate(() => {
          if (
            window.presentation("?new=deal&token=secret&view=board") !==
            "?view=board"
          )
            throw Error("Action replay");
          for (let i = 0; i < 50; i++)
            window.views.save("/p" + i, {
              search: "?page=2",
              scrollTop: 0,
              scrollLeft: 0,
            });
          if (window.views.size() !== 40) throw Error("Unbounded state");
          window.views.scope("another-company");
          if (window.views.size()) throw Error("Cross-company view leak");
        });
        await page.evaluate(() => window.navigate("/crm/retry"));
        await page
          .getByRole("button", { name: "Retry page", exact: true })
          .click();
        await page.getByRole("heading", { name: "Recovered page" }).waitFor();
        assert(await page.locator("[data-header]").isVisible());
        await page.evaluate(() => window.navigate("/crm/deals"));
        await page
          .getByRole("heading", { name: "Deals", exact: true })
          .waitFor();
        await page.reload();
        await page
          .getByRole("heading", { name: "Deals", exact: true })
          .waitFor();
      }
      assert.deepEqual(
        errors.filter(
          (message) =>
            message !== "Failed to fetch dynamically imported module",
        ),
        [],
      );
      await page.close();
    }
    assert.equal(result.after.shellMounts, 1);
    console.log(
      "PASS: persistent header/sidebar during delayed routes, no shell remount, hover prefetch, filter/scroll restoration, Back/Forward/deep refresh, bounded and scoped UI state",
    );
    console.log("MEASURED controlled route fixture: " + JSON.stringify(result));
    fs.mkdirSync(path.join(root, "../outputs"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "../outputs/navigation-shell-results.json"),
      JSON.stringify(result, null, 2),
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
