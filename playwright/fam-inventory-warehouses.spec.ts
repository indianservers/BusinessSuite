import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

for (const module of ["fam", "srm"]) {
  test(`${module} warehouse stays open on failure and closes on save before the list refresh`, async ({ page }) => {
    await authenticate(page, "admin");
    let attempts = 0;
    let saved: Record<string, unknown> | undefined;
    let releaseRefresh!: () => void;
    const refresh = new Promise<void>(resolve => { releaseRefresh = resolve; });
    await page.route(`**/api/v1/${module}/inventory/warehouses`, async route => {
      if (route.request().method() === "POST") {
        attempts++;
        if (attempts === 1) return route.fulfill({ status: 409, json: { detail: "Warehouse code is already in use" } });
        await new Promise(resolve => setTimeout(resolve, 300));
        saved = { ...route.request().postDataJSON(), id: 123, active: true };
        return route.fulfill({ status: 201, json: saved });
      }
      if (saved) await refresh;
      return route.fulfill({ json: { items: saved ? [saved] : [], total: saved ? 1 : 0 } });
    });
    await page.goto(`/${module}/inventory/warehouses`);
    await page.getByRole("button", { name: "Create warehouse", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Create warehouse" });
    await dialog.getByRole("textbox").nth(0).fill("QA-WH");
    await dialog.getByRole("textbox").nth(1).fill("QA Warehouse");
    const save = dialog.locator("[data-smart-create-footer]").getByRole("button", { name: "Save", exact: true });
    try {
      await save.click();
      await expect(dialog.getByRole("alert")).toContainText("Warehouse code is already in use");
      await expect(dialog.getByRole("textbox").nth(1)).toHaveValue("QA Warehouse");
      const confirmed = page.waitForResponse(response => response.url().endsWith(`/api/v1/${module}/inventory/warehouses`) && response.request().method() === "POST" && response.status() === 201);
      await save.click();
      await confirmed;
      await expect(page.locator("[data-smart-create]")).toHaveCount(0);
      expect(attempts).toBe(2);
    } finally {
      releaseRefresh();
    }
    await expect(page.getByText("QA Warehouse", { exact: true })).toBeVisible();
  });
}
