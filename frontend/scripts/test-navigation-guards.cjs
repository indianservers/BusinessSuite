const { build } = require("esbuild"),
  { chromium } = require("playwright"),
  fs = require("node:fs"),
  path = require("node:path"),
  assert = require("node:assert/strict");
(async () => {
  const root = path.resolve(__dirname, ".."),
    app = fs.readFileSync(path.join(root, "src/App.tsx"), "utf8"),
    guard = app.slice(
      app.indexOf("function ProtectedRoute("),
      app.indexOf("export default function App()"),
    );
  const source = `import React,{useEffect,useState}from'react';import{createRoot}from'react-dom/client';import{BrowserRouter,Routes,Route,Outlet,Navigate,useNavigate,useLocation}from'react-router-dom';import{useAuthStore}from'./src/store/authStore';const canAccessRoute=path=>!path.includes('/projects/');const LoadingFallback=()=> <p role="status">Checking access</p>;const AccessDeniedPage=()=> <p role="alert">Access denied</p>;const api={get:()=>{window.reads++;return new Promise(resolve=>window.release=()=>resolve({data:[]}))}};window.reads=0;${guard}function Shell(){const navigate=useNavigate();window.navigate=navigate;return <><header>Persistent header</header><Outlet/></>};useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,email:'qa@test.invalid',role:'member'}});window.logout=()=>useAuthStore.setState({isAuthenticated:false});createRoot(document.getElementById('root')).render(<BrowserRouter><Routes><Route path="/login" element={<h1>Login</h1>}/><Route path="/*" element={<ProtectedRoute sessionOnly><Shell/></ProtectedRoute>}><Route path="pms/tasks" element={<ProtectedRoute><h1>Tasks</h1></ProtectedRoute>}/><Route path="pms/projects/:id" element={<ProtectedRoute><h1>Private project</h1></ProtectedRoute>}/></Route></Routes></BrowserRouter>);`;
  const built = await build({
    stdin: { contents: source, resolveDir: root, loader: "tsx" },
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    alias: { "@": path.join(root, "src") },
    define: { "import.meta.env": "{}" },
  });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.route("http://guard.test/**", (r) =>
      r.fulfill({ contentType: "text/html", body: '<div id="root"></div>' }),
    );
    await page.goto("http://guard.test/pms/tasks");
    await page.addScriptTag({ content: built.outputFiles[0].text });
    await page.getByRole("heading", { name: "Tasks" }).waitFor();
    await page.evaluate(() => window.navigate("/pms/projects/7"));
    await page.getByRole("status").waitFor();
    assert(await page.getByText("Persistent header").isVisible());
    assert.equal(await page.evaluate(() => window.reads), 1);
    assert.equal(
      await page.getByRole("heading", { name: "Private project" }).count(),
      0,
    );
    await page.evaluate(() => window.release());
    await page.getByRole("alert").waitFor();
    assert(await page.getByText("Persistent header").isVisible());
    await page.evaluate(() => window.navigate("/pms/tasks"));
    await page.getByRole("heading", { name: "Tasks" }).waitFor();
    await page.evaluate(() => window.logout());
    await page.getByRole("heading", { name: "Login" }).waitFor();
    assert.equal(await page.getByText("Persistent header").count(), 0);
    console.log(
      "PASS: actual route guard preserves shell during membership check/denial, never renders denied content, makes one membership request, and removes private shell on logout",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
