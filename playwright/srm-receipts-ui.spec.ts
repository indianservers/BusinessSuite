import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM receipts UI", () => {
  test("creates, confirms, partially allocates, and fully allocates receipts", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });

    await page.getByRole("button", { name: "Create Receipt" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Receipt created completed");

    await page.getByRole("button", { name: "Confirm Receipt" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Receipt confirmed completed");

    await page.getByRole("button", { name: "Allocate Partial Payment" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Partial allocation completed");

    await page.getByRole("button", { name: "Allocate Full Payment" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Full allocation completed");

    await expect(page.getByRole("heading", { name: "Receipts", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Customer Outstanding" })).toBeVisible();
  });

  test("shows allocation validation errors", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await page.route("**/api/v1/srm/receipts/1/allocate", async (route) => {
      await route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "Allocation amount exceeds invoice balance" }) });
    });
    await page.goto("/srm/collections", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Allocate Partial Payment" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Allocation amount exceeds invoice balance");
  });
});
