const { build } = require("esbuild"),
  { chromium } = require("playwright"),
  fs = require("node:fs"),
  path = require("node:path"),
  assert = require("node:assert/strict");
(async () => {
  const root = path.resolve(__dirname, "..");
  const baseline = fs.readFileSync(path.join(root,"scripts/fixtures/branding-before-navigation.ts"),"utf8");
  const results = {};
  for (const mode of ["before", "after"]) {
    const hook =
      mode === "before"
        ? baseline
        : fs.readFileSync(
            path.join(root, "src/features/access/useCompanyBranding.ts"),
            "utf8",
          );
    const source = `import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter,useLocation,useNavigate}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import{useCompanyBranding}from'branding-hook';import{api}from'./src/services/api';import{useAuthStore}from'./src/store/authStore';import{accessQueryOptions}from'./src/features/access/access-query';const client=new QueryClient();window.client=client;window.access=accessQueryOptions;window.requests=0;window.accessReads=0;api.defaults.adapter=async config=>{if(config.url==='/access/me')window.accessReads++;else window.requests++;await new Promise(r=>setTimeout(r,8));return{data:config.url==='/access/me'?{managed:true}:{values:{appName:'Company '+sessionStorage.getItem('suite-organization'),primary:'#6633ee'}},status:200,statusText:'OK',headers:{},config}};useAuthStore.setState({isAuthenticated:true,accessToken:'fixture',user:{id:1,email:'qa@test.invalid',role:'admin',is_superuser:true,access:{companyId:1}}});sessionStorage.setItem('suite-organization','1');function App(){const location=useLocation(),navigate=useNavigate();window.navigate=navigate;const brand=useCompanyBranding(location.pathname);return <header><h1>{brand.name}</h1></header>}createRoot(document.getElementById('root')).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/crm/deals']}><App/></MemoryRouter></QueryClientProvider>);`;
    const built = await build({
      stdin: { contents: source, loader: "tsx", resolveDir: root },
      bundle: true,
      write: false,
      format: "iife",
      platform: "browser",
      alias: { "@": path.join(root, "src") },
      define: { "import.meta.env": "{}" },
      plugins: [
        {
          name: "branding-source",
          setup(b) {
            b.onResolve({ filter: /^branding-hook$/ }, () => ({
              path: "branding-hook",
              namespace: "test",
            }));
            b.onLoad({ filter: /.*/, namespace: "test" }, () => ({
              contents: hook,
              loader: "tsx",
              resolveDir: root,
            }));
          },
        },
      ],
    });
    const browser = await chromium.launch();
    try {
      const page = await browser.newPage();
      await page.route("http://branding.test/**", (r) =>
        r.fulfill({ contentType: "text/html", body: '<div id="root"></div>' }),
      );
      await page.goto("http://branding.test");
      await page.addScriptTag({ content: built.outputFiles[0].text });
      await page.getByRole("heading", { name: "Company 1" }).waitFor();
      for (const route of [
        "/crm/contacts",
        "/pms/projects",
        "/pms/tasks",
        "/hrms/employees",
        "/srm/inventory",
      ]) {
        await page.evaluate((route) => window.navigate(route), route);
        await page.waitForTimeout(35);
      }
      results[mode] = {
        brandingRequests: await page.evaluate(() => window.requests),
        pages: 6,
      };
      if (mode === "after") {
        assert.equal(results.after.brandingRequests, 1);
        await page.evaluate(() =>
          Promise.all([
            window.client.fetchQuery(window.access()),
            window.client.fetchQuery(window.access()),
          ]),
        );
        assert.equal(await page.evaluate(() => window.accessReads), 1);
        await page.evaluate(() => window.client.fetchQuery(window.access()));
        assert.equal(await page.evaluate(() => window.accessReads), 2);
        await page.evaluate(() => {
          sessionStorage.setItem("suite-organization", "2");
          window.navigate("/fam");
        });
        await page.getByRole("heading", { name: "Company 2" }).waitFor();
        assert.equal(await page.evaluate(() => window.requests), 2);
      }
    } finally {
      await browser.close();
    }
  }
  assert.equal(results.before.brandingRequests, 6);
  console.log(
    "PASS: actual branding hook before/after, company isolation, concurrent permission reads deduplicate without a permission TTL",
  );
  console.log("MEASURED local navigation fixture: " + JSON.stringify(results));
  fs.mkdirSync(path.join(root, "../outputs"), { recursive: true });
  fs.writeFileSync(
    path.join(root, "../outputs/navigation-branding-results.json"),
    JSON.stringify(results, null, 2),
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
