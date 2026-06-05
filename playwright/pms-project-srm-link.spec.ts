import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("PMS project SRM link UI", () => {
  test("shows SRM engagement linkage on project dashboard", async ({ page }) => {
    await authenticate(page, "admin");
    await page.goto("/pms/projects/301", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "SRM Engagement Link" })).toBeVisible();
    await expect(page.getByText("ENG-000001")).toBeVisible();
    await expect(page.getByText("SO-000001")).toBeVisible();
    await expect(page.getByText("CTR-000001")).toBeVisible();
    await expect(page.getByText("Milestone billing")).toBeVisible();
  });
});
