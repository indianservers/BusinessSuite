// Disposable loopback-only QA: never point this script at a deployed service.
const fs = require("fs");
fs.mkdirSync(".local", { recursive: true });
const {
  chromium,
  expect: raw,
} = require("../frontend/node_modules/playwright/test");
const expect = raw.configure({ timeout: 45000 });
(async () => {
  const r = await fetch("http://127.0.0.1:1552/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "admin@suiteqa.example.com",
      password: "SuiteQA@12345",
    }),
  });
  if (!r.ok) throw Error("Login " + r.status);
  const login = await r.json();
  const access = await (
    await fetch("http://127.0.0.1:1552/api/v1/access/me", {
      headers: { Authorization: "Bearer " + login.access_token },
    })
  ).json();
  const browser = await chromium.launch({ headless: true });
  globalThis.browser = browser;
  const context = await browser.newContext({
    viewport: { width: 1672, height: 941 },
  });
  await context.addInitScript(
    ({ login, access }) =>
      sessionStorage.setItem(
        "hrms-auth",
        JSON.stringify({
          state: {
            accessToken: login.access_token,
            refreshToken: login.refresh_token,
            isAuthenticated: true,
            user: {
              id: login.user_id,
              email: login.email,
              role: "admin",
              is_superuser: true,
              access,
            },
          },
          version: 0,
        }),
      ),
    { login, access },
  );
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", async (r) => {
    if (r.status() >= 400 && r.url().includes("people-workspace"))
      console.error("HTTP", r.status(), (await r.text()).slice(0, 300));
  });

  await page.goto("http://127.0.0.1:5187/admin/control/statistics");
  await expect(page.getByRole("heading",{name:"Statistics Audit",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Run Audit",exact:true}).click();
  await expect(page.getByText("Master Suite / access/statistics",{exact:true}).first()).toBeVisible();
  await expect(page.getByText("HRMS / employees/count",{exact:true}).first()).toBeVisible();
  await expect(page.getByText("InternHub / management/dashboard",{exact:true}).first()).toBeVisible();
  await expect(page.getByText("calculation mismatch",{exact:true})).toHaveCount(0);
  await page.screenshot({path:".local/statistics-audit-desktop.png",fullPage:true});
  await page.getByRole("button",{name:"Metric Definitions",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Registered users",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Source Inventory",exact:true}).click();
  await expect(page.getByText(/source locations discovered/)).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(async()=>{const b=await page.locator("main").boundingBox();return !!b&&b.x<30&&b.width>340}).toBe(true);
  await page.screenshot({path:".local/statistics-audit-mobile.png",fullPage:true});
  let metricRequests=0;
  page.on("request",r=>{if(r.url().includes("/api/v1/crm/dashboard"))metricRequests++});
  await page.setViewportSize({width:1672,height:941});
  await page.goto("http://127.0.0.1:5187/crm/dashboard");
  await expect(page.getByText("Full permitted query; before pagination")).toBeVisible();
  await expect.poll(()=>metricRequests).toBeGreaterThan(0);
  const before=metricRequests;
  await page.evaluate(()=>window.dispatchEvent(new Event("suite:metrics-changed")));
  await expect.poll(()=>metricRequests).toBeGreaterThan(before);
  await page.route("**/api/v1/metrics/definitions",route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"QA statistics source unavailable"})}));
  await page.goto("http://127.0.0.1:5187/admin/control/statistics");
  await expect(page.getByRole("alert").filter({hasText:"QA statistics source unavailable"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Run Audit",exact:true})).toBeDisabled();
  if(errors.length)throw Error(errors.join("; "));
  console.log("PASS: audit reconciliation, definitions, inventory, desktop and mobile; no browser exceptions");
  await browser.close();
})().catch(async error=>{console.error(error);if(globalThis.browser)await globalThis.browser.close();process.exit(1)});
