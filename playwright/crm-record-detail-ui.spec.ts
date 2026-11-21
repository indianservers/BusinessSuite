import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

for (const [width, height] of [[320, 510], [1440, 900]]) {
  test(`contact detail editor at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await authenticateCrm(page);
    await page.route("**/api/v1/access/setup", route => route.fulfill({ json: { companyId: 1, ready: true, items: [] } }));
    await page.route("**/api/v1/crm/contacts/1", async route => {
      if (["PUT", "PATCH"].includes(route.request().method())) {
        await route.fulfill({ status: 422, json: { detail: "QA rejected this edit" } });
      } else {
        await route.fallback();
      }
    });
    await page.goto("/crm/contacts/1", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: "Nisha Rao", level: 1 })).toBeVisible();
    if (width < 768) await expect(page.getByRole("navigation", { name: "Record navigation" }).getByRole("link", { name: "Contacts" })).toBeVisible();
    const actions = page.getByRole("group", { name: "Contact actions" });
    const edit = actions.getByRole("button", { name: "Edit", exact: true });
    if (width < 768) {
      await edit.click();
    } else {
      const more = actions.getByRole("button", { name: "More actions", exact: true });
      await more.press("Enter");
      await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
    }
    const dialog = page.getByRole("dialog", { name: "Edit Contact" });
    await expect(dialog).toBeVisible();
    const save = dialog.getByRole("button", { name: "Save changes" });
    await expect(save).toBeInViewport({ ratio: 1 });
    const body = dialog.locator(".crm-detail-dialog-body");
    if (width < 768) {
      await body.evaluate(node => node.scrollTop = node.scrollHeight);
      await expect(dialog.getByRole("button", { name: "Close dialog" })).toBeInViewport({ ratio: 1 });
      await expect(save).toBeInViewport({ ratio: 1 });
    }
    await save.click();
    await expect(dialog.getByRole("alert")).toHaveText("QA rejected this edit");
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });
}
