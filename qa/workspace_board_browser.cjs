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
  page.on("pageerror", (e) => {errors.push(e.message);console.error("PAGE ERROR",e.message,e.stack)});
  page.on("response", async (r) => {
    if (r.status() >= 400 && r.url().includes("people-workspace"))
      console.error("HTTP", r.status(), (await r.text()).slice(0, 300));
  });

  const headers={Authorization:"Bearer "+login.access_token,"Content-Type":"application/json"};
  const created=await fetch("http://127.0.0.1:1552/api/v1/project-management/workspaces",{method:"POST",headers,body:JSON.stringify({name:"Testing gnasai"})});
  if(!created.ok)throw Error(await created.text());const second=await created.json();
  await page.goto(`http://127.0.0.1:5187/pms?workspace=${second.id}`);
  await expect(page.locator(".wb-hero h1")).toContainText("Testing gnasai");
  await expect(page.getByRole("heading",{name:"No tasks match this view"})).toBeVisible();
  await page.getByRole("button",{name:"Switch workspace",exact:true}).click();
  await expect(page.getByRole("dialog",{name:"Workspace switcher"})).toBeVisible();
  await expect(page.getByRole("dialog",{name:"Workspace switcher"})).toHaveCSS("opacity","1");
  await page.screenshot({path:".local/workspace-board-desktop.png",fullPage:true});
  await page.getByRole("button",{name:"Use workspace color #22c98d",exact:true}).click();
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(page.locator(".wb-hero h1")).toContainText("Testing gnasai");
  await expect(page.locator(".ws-app")).toHaveCSS("--wb-accent","#22c98d");
  await page.getByRole("button",{name:"Switch workspace",exact:true}).click();
  await page.getByLabel("Search workspaces",{exact:true}).fill("Indian");
  const first=page.locator(".wb-workspace-options button").first();
  await first.click();
  await expect(page).not.toHaveURL(new RegExp(`workspace=${second.id}(?:&|$)`));
  await expect(page.locator(".wb-hero h1")).not.toContainText("Testing gnasai");
  await page.getByLabel("Search tasks in workspace",{exact:true}).fill("No matching QA title");
  await page.getByRole("button",{name:"Save view",exact:true}).click();
  await page.getByRole("button",{name:/Clear filters/}).click();
  await page.getByRole("button",{name:"Load view",exact:true}).click();
  await expect(page.getByLabel("Search tasks in workspace",{exact:true})).toHaveValue("No matching QA title");
  await page.goBack();
  await expect(page.locator(".wb-hero h1")).toContainText("Testing gnasai");
  await expect(page.locator(".ws-loading")).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});
  await expect.poll(async()=>{const b=await page.locator(".ws-main").boundingBox();return !!b&&b.x>=0&&b.width<=390}).toBe(true);
  await page.getByRole("button",{name:"Switch workspace",exact:true}).click();
  await expect(page.getByRole("dialog",{name:"Workspace switcher"})).toHaveCSS("opacity","1");
  await page.screenshot({path:".local/workspace-board-mobile.png",fullPage:true});
  await page.getByRole("button",{name:"Create new workspace",exact:true}).click();
  const workspaceName="Picker created workspace "+Date.now();
  await page.getByLabel("Workspace name",{exact:true}).fill(workspaceName);
  await page.getByRole("button",{name:"Create workspace",exact:true}).click();
  await expect(page.locator(".wb-hero h1")).toContainText(workspaceName);
  const createdURL=page.url();
  await page.reload();
  await expect(page.locator(".wb-hero h1")).toContainText(workspaceName);
  await expect(page).toHaveURL(createdURL);
  if(errors.length)throw Error(errors.join("; "));
  console.log("PASS: searchable workspace switching, URL and back navigation, empty view, saved filters, color persistence, creation/reload, desktop/mobile and no browser exceptions");
  await browser.close();
})().catch(async error=>{console.error(error);if(globalThis.browser)await globalThis.browser.close();process.exit(1)});
