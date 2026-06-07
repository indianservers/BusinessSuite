import { test, expect } from "../frontend/node_modules/playwright/test";
import { installPhase10ApiStubs } from "./phase10-test-utils";

test.describe("partner portal", () => {
  test("opens partner dashboard and submits partner lead", async ({ page }) => {
    await installPhase10ApiStubs(page);
    await page.goto("/portal/partner/login", { waitUntil: "domcontentloaded" });
    await page.getByPlaceholder("Paste session token").fill("partner-token");
    await page.getByRole("button", { name: /Open portal/ }).click();
    await expect(page.getByRole("heading", { name: "Partner Portal" })).toBeVisible();
    await expect(page.getByText("Commission status")).toBeVisible();
    await page.getByRole("link", { name: "Leads" }).click();
    await page.getByPlaceholder("Company").fill("Partner Co");
    await page.getByPlaceholder("Contact").fill("Priya Partner");
    await page.getByPlaceholder("Email").fill("lead@example.com");
    await page.getByRole("button", { name: "Submit lead" }).click();
    await expect(page.getByText("Partner Co").first()).toBeVisible();
  });
});
