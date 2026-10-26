import { test, expect, type Page } from "../frontend/node_modules/playwright/test";

async function setup(page: Page) {
  await page.route("**/config.js", route => route.fulfill({ contentType: "application/javascript", body: `window.__INTERNHUB_CONFIG__ = { apiBaseUrl: "/api/v1", firebaseConfig: { projectId: "signup-test", apiKey: "public-test", authDomain: "signup-test.firebaseapp.com", appId: "public-app" } };` }));
  await page.route("**/api/v1/**", route => route.fulfill({ json: [] }));
}
const enabled = { project_id: "signup-test", providers: [{ provider: "google", enabled: true }] };
const url = "http://127.0.0.1:5178/login";

test("Google signup explains loading and enables after availability loads", async ({ page }) => {
  await setup(page);
  let release: (() => void) | undefined;
  await page.route("**/signup/providers", async route => {
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ json: enabled });
  });
  await page.goto(url);
  await expect(page.getByRole("button", { name: "Loading Google sign-in…" })).toBeDisabled();
  await expect(page.getByRole("status", { name: "" }).filter({ hasText: "Checking Google signup availability" })).toBeVisible();
  await expect.poll(() => !!release).toBe(true);
  release!();
  await expect(page.getByRole("button", { name: "Sign up with Google" })).toBeEnabled();
});

test("failed availability checks can be retried without reloading", async ({ page }) => {
  await setup(page);
  let attempts = 0;
  await page.route("**/signup/providers", route => { attempts++; return route.fulfill(attempts === 1 ? { status: 503, json: { detail: "unavailable" } } : { json: enabled }); });
  await page.goto(url);
  await expect(page.getByRole("alert")).toContainText("Could not load Google signup");
  await page.getByRole("button", { name: "Retry Google signup" }).click();
  await expect(page.getByRole("button", { name: "Sign up with Google" })).toBeEnabled();
  expect(attempts).toBe(2);
});

test("a timed out availability check can recover through retry", async ({ page }) => {
  await setup(page);
  await page.clock.install();
  let attempts = 0;
  await page.route("**/signup/providers", route => { attempts++; if (attempts > 1) return route.fulfill({ json: enabled }); });
  await page.goto(url);
  await expect.poll(() => attempts).toBe(1);
  await page.clock.fastForward(20_001);
  await expect(page.getByRole("alert")).toContainText("took too long");
  await page.getByRole("button", { name: "Retry Google signup" }).click();
  await expect(page.getByRole("button", { name: "Sign up with Google" })).toBeEnabled();
});

test("a Firebase project mismatch is explained and cannot enable signup", async ({ page }) => {
  await setup(page);
  await page.route("**/signup/providers", route => route.fulfill({ json: { ...enabled, project_id: "different-project" } }));
  await page.goto(url);
  await expect(page.getByRole("alert")).toContainText("different Google configurations");
  await expect(page.getByRole("button", { name: "Sign up with Google" })).toBeDisabled();
});
