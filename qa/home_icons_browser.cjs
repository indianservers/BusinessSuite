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

  await page.goto("http://127.0.0.1:5187/dashboard");
  await expect(page.locator(".md-card")).toHaveCount(6);
  await expect.poll(()=>page.locator(".md-module-art img").evaluateAll(images=>images.every(i=>i.complete&&i.naturalWidth>0))).toBe(true);
  await page.locator("#md-applications").scrollIntoViewIfNeeded();
  await page.screenshot({path:".local/home-icons-desktop.png",fullPage:true});
  const first=page.locator(".md-card").first();
  await first.getByRole("button",{name:/Pin Power Apps/}).click();
  await expect(first.getByRole("button",{name:/Unpin Power Apps/})).toHaveAttribute("aria-pressed","true");
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.locator(".md-grid").evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(" ").length)).toBe(1);
  await page.locator("#md-applications").scrollIntoViewIfNeeded();
  await page.screenshot({path:".local/home-icons-mobile.png",fullPage:true});
  if(errors.length)throw Error(errors.join("; "));
  console.log("PASS six module illustrations load, pinning works, desktop/mobile layouts, no browser exceptions");
  await browser.close();
})().catch(async error=>{console.error(error);if(globalThis.browser)await globalThis.browser.close();process.exit(1)});
