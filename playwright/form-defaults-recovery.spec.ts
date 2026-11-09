import { test, expect } from "../frontend/node_modules/playwright/test";
test("invalid preferences show Retry and recover without an endless loading screen", async ({page}) => {
  let valid=false;
  await page.route("**/api/v1/access/settings/defaults/effective",route=>route.fulfill({json:valid?{values:{},modules:{},companyId:1,branchId:null}:""}));
  await page.route("**/__defaults_recovery",route=>route.fulfill({contentType:"text/html",body:`<html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/form-defaults-recovery-qa.tsx"></script></body></html>`}));
  await page.goto("/__defaults_recovery");
  await expect(page.getByRole("alert")).toContainText("Could not load form defaults");
  await expect(page.getByLabel("New record title")).toHaveCount(0);
  valid=true;
  await page.getByRole("button",{name:"Retry",exact:true}).click();
  await expect(page.getByLabel("New record title")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
