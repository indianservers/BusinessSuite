import { test, expect } from "../frontend/node_modules/playwright/test";
import { setupPowerApps } from "./power-apps-fixtures";
import { productivityReferences } from "../frontend/src/shared/productivity/references";

for (const reference of productivityReferences) {
  test(`${reference.name}: authorized PMS link points to existing integration`, async ({ page }) => {
    await setupPowerApps(page, { pmsAccess: true });
    await page.route("**/power-apps/catalog", route => route.fulfill({ json: {
      applications: [{ ...reference, route: `/power-apps/${reference.id}`, status: "reference" }],
      permissions: ["power_apps_view"], templates: [], execution_enabled: false,
    } }));
    await page.goto(`/power-apps/${reference.id}`);
    await expect(page.getByRole("link", { name: `Open integrated PMS ${reference.name}` })).toHaveAttribute("href", reference.route);
  });
  test(`${reference.name}: reference opens without environment or PMS data access`, async ({ page }) => {
    await setupPowerApps(page, { readOnly: true });
    await page.route("**/power-apps/catalog", route => route.fulfill({ json: {
      applications: productivityReferences.map(item => ({
        ...item, route: `/power-apps/${item.id}`, status: "reference",
        required_permissions: ["power_apps_view"], feature_flags: [], environments: [],
      })),
      permissions: ["power_apps_view"], templates: [], execution_enabled: false,
    } }));
    const requests: string[] = [];
    const writes: string[] = [];
    page.on("request", req => {
      if (req.url().includes("/api/")) {
        requests.push(req.url());
        if (req.method() !== "GET") writes.push(req.url());
      }
    });
    await page.goto(`/power-apps/${reference.id}?environment=testing`);
    await expect(page.locator(".pa-panel h2")).toHaveText(reference.name);
    await expect(page.locator(".pa-panel")).toContainText(reference.preserve);
    await expect(page.locator(".pa-panel li")).toHaveText([...reference.integration]);
    await expect(page.getByText("Set up your first environment", { exact: true })).toHaveCount(0);
    await expect(page.locator(".pa-panel a[href^='/pms']")).toHaveCount(0);
    expect(requests.filter(url => /\/power-apps\/(environments|overview|activity)/.test(url))).toEqual([]);
    expect(requests.filter(url => /\/api\/v1\/(pms|project-management)/.test(url))).toEqual([]);
    expect(writes).toEqual([]);
    await page.reload();
    await expect(page.locator(".pa-panel h2")).toHaveText(reference.name);
  });

  test(`${reference.name}: revoked Power Apps access stays blocked`, async ({ page }) => {
    await setupPowerApps(page, { allowed: false });
    await page.goto(`/power-apps/${reference.id}`);
    await expect(page.locator(".pa-shell")).toHaveCount(0);
    await expect(page.getByText(/Access denied|Access restricted|don't have access|permission/i).first()).toBeVisible();
  });
}
