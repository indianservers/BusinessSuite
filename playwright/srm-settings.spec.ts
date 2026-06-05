import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied } from "./srm-test-utils";

const settings = [
  "invoice numbering prefix",
  "sales order numbering prefix",
  "contract numbering prefix",
  "default payment terms",
  "default tax/VAT settings",
  "default billing plan rules",
  "collection reminder templates",
  "escalation thresholds",
  "write-off approval requirement",
  "dashboard visibility preferences",
];

test.describe("SRM settings", () => {
  test("SRM Admin edits and saves settings", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    for (const label of settings) await expect(page.getByLabel(label)).toBeVisible();

    await page.getByLabel("invoice numbering prefix").fill("SRM-INV");
    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("SRM settings saved");
  });

  test("shows validation messages for missing required settings", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await page.getByLabel("invoice numbering prefix").fill("");
    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("invoice numbering prefix is required");
  });

  test("viewer and sales roles see read-only settings; non-SRM is blocked", async ({ page }) => {
    await authenticate(page, "srm_viewer");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save Settings" })).toHaveCount(0);

    await authenticate(page, "srm_sales_executive");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
    await expect(page.getByLabel("invoice numbering prefix")).toBeDisabled();

    await authenticate(page, "employee");
    await expectDenied(page, "/srm/settings");
  });
});
