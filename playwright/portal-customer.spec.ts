import { test, expect } from "../frontend/node_modules/playwright/test";
import { installPhase10ApiStubs } from "./phase10-test-utils";

test.describe("customer portal", () => {
  test("opens customer-safe profile, quotes, invoices, and projects with portal session", async ({ page }) => {
    await installPhase10ApiStubs(page);
    await page.goto("/portal/customer/login", { waitUntil: "domcontentloaded" });
    await page.getByPlaceholder("Paste session token").fill("portal-token");
    await page.getByRole("button", { name: /Open portal/ }).click();
    await expect(page.getByRole("heading", { name: "Customer Portal" })).toBeVisible();
    await expect(page.getByText("Only linked customer-safe records")).toBeVisible();
    await page.getByRole("link", { name: "Quotes" }).click();
    await expect(page.getByText("QT-001").first()).toBeVisible();
    await page.getByRole("link", { name: "Invoices" }).click();
    await expect(page.getByText("INV-001").first()).toBeVisible();
    await page.getByRole("link", { name: "Projects" }).click();
    await expect(page.getByText("Implementation").first()).toBeVisible();
  });
});
