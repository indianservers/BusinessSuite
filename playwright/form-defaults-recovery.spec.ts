import { test, expect } from "../frontend/node_modules/playwright/test";
test.beforeEach(async ({page}) => {
  await page.route("**/__defaults_recovery",route=>route.fulfill({contentType:"text/html",body:`<html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/form-defaults-recovery-qa.tsx"></script></body></html>`}));
});

test("invalid preferences show Retry and recover without an endless loading screen", async ({page}) => {
  let valid=false;
  await page.route("**/api/v1/access/settings/defaults/effective",route=>route.fulfill({json:valid?{values:{},modules:{},companyId:1,branchId:null}:""}));
  await page.goto("/__defaults_recovery");
  await expect(page.getByRole("alert")).toContainText("Could not load form defaults");
  await expect(page.getByLabel("New record title")).toHaveCount(0);
  valid=true;
  await page.getByRole("button",{name:"Retry",exact:true}).click();
  await expect(page.getByLabel("New record title")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("preserves drafts during access refresh and gates forms when switching branch", async ({page}) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("hrms-auth", JSON.stringify({
      state: { user: { id: 100, email: "qa@example.com", role: "admin", is_superuser: true } },
      version: 0,
    }));
  });
  let pending = Promise.resolve();
  let release: () => void = () => {};
  await page.route("**/api/v1/access/settings/defaults/effective", async route => {
    const branchId = Number(route.request().headers()["x-suite-branch"]) || 1;
    await pending;
    await route.fulfill({ json: { values: {}, modules: {}, companyId: 1, branchId } });
  });
  await page.goto("/__defaults_recovery");
  const title = page.getByLabel("New record title");
  await title.fill("Unsaved draft");

  pending = new Promise<void>(resolve => { release = resolve; });
  const refresh = page.waitForRequest("**/api/v1/access/settings/defaults/effective");
  await page.getByRole("button", { name: "Refresh access" }).click();
  await refresh;
  await expect(title).toHaveValue("Unsaved draft");
  const refreshed = page.waitForResponse("**/api/v1/access/settings/defaults/effective");
  release();
  await refreshed;
  await expect(title).toHaveValue("Unsaved draft");

  pending = new Promise<void>(resolve => { release = resolve; });
  const changed = page.waitForRequest("**/api/v1/access/settings/defaults/effective");
  await page.getByRole("button", { name: "Switch branch" }).click();
  await changed;
  await expect(title).toHaveCount(0);
  release();
  await expect(title).toHaveValue("");
});
