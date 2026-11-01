import { test, expect } from "../frontend/node_modules/playwright/test";

test("Google same-tab sign-in exchanges the result through the existing MFA gate", async ({ page }) => {
  const exchanges: unknown[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/firebase/config")) return route.fulfill({ json: { enabled: true, modules: ["crm"], firebase_config: { apiKey: "fixture-public-key", projectId: "fixture", authDomain: "fixture.firebaseapp.com", googleAuthDomain: "app.fixture.example" } } });
    if (path.endsWith("/firebase/login")) {
      exchanges.push(route.request().postDataJSON());
      return route.fulfill({ json: { mfa_required: true, mfa_token: "fixture-mfa" } });
    }
    if (path.endsWith("/branding")) return route.fulfill({ json: { company_name: "Fixture company" } });
    if (path.includes("providers")) return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
  await page.route("**/node_modules/.vite/deps/firebase_app.js*", (route) => route.fulfill({ contentType: "application/javascript", body: `export const getApps=()=>[]; export const initializeApp=(config,name)=>{sessionStorage.setItem('fixture-auth-domain',config.authDomain);return {config,name}};` }));
  await page.route("**/node_modules/.vite/deps/firebase_auth.js*", (route) => route.fulfill({ contentType: "application/javascript", body: `
    export const getAuth=()=>({});
    export class GoogleAuthProvider { setCustomParameters(){} }
    export class OAuthProvider { setCustomParameters(){} }
    export const inMemoryPersistence={};
    export const setPersistence=async()=>{};
    export const signInWithPopup=async()=>{throw {code:'auth/popup-closed-by-user'}};
    export const signInWithRedirect=async()=>{sessionStorage.setItem('fixture-redirect-result','yes');location.assign(location.href)};
    export const getRedirectResult=async()=>sessionStorage.getItem('fixture-redirect-result')?{user:{getIdToken:async()=>'fixture-provider-token'}}:null;
    export const signOut=async()=>{sessionStorage.removeItem('fixture-redirect-result')};
  ` }));
  await page.goto("/login?next=%2Fpower-apps%2Fautomations%2F1%2Fedit");
  await page.getByRole("button", { name: "Continue with Google", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("popup closed");
  await page.getByRole("button", { name: "Continue with Google in this tab", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Verify your identity", exact: true })).toBeVisible();
  expect(exchanges).toEqual([{ token: "fixture-provider-token", provider: "google" }]);
  expect(await page.evaluate(() => sessionStorage.getItem("suite-social-redirect-provider"))).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem("suite-social-redirect-remember"))).toBeNull();
  expect(page.url()).not.toContain("fixture-provider-token");
  expect(await page.evaluate(() => sessionStorage.getItem("fixture-auth-domain"))).toBe("app.fixture.example");
  await page.getByRole("button", { name: "Back to login", exact: true }).click();
  await page.getByRole("button", { name: "Continue with Microsoft", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("popup closed");
  expect(await page.evaluate(() => sessionStorage.getItem("fixture-auth-domain"))).toBe("fixture.firebaseapp.com");
});
