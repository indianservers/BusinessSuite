import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM billing plans commercial UI", () => {
  test("lists, opens detail, verifies plan types, milestones, and billing actions", async ({ page }) => {
    await authenticate(page, "srm_admin");

    await page.goto("/srm/billing-plans", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Billing Plans" })).toBeVisible();
    await expect(page.getByText("Milestone billing")).toBeVisible();
    await expect(page.getByText(/fixed fee, milestone, T&M, recurring, and hybrid/i)).toBeVisible();

    await page.goto("/srm/billing-plans/4", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Billing Plan Detail" })).toBeVisible();
    await expect(page.getByText("Milestone billing")).toBeVisible();
    await expect(page.getByText("sales order id")).toBeVisible();
    await expect(page.getByText("engagement id")).toBeVisible();
    await expect(page.getByText("total amount")).toBeVisible();

    const result = await page.evaluate(async () => {
      const post = (path: string) => fetch(`/api/v1${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then((res) => res.json());
      const created = await post("/srm/billing-plans");
      const fromSalesOrder = await post("/srm/sales-orders/1/billing-plan");
      const milestone = await post("/srm/billing-plans/4/milestones");
      const activated = await post("/srm/billing-plans/4/activate");
      const paused = await post("/srm/billing-plans/4/pause");
      const completed = await post("/srm/billing-plans/4/complete");
      const cancelled = await post("/srm/billing-plans/4/cancel");
      const draft = await post("/srm/invoices/draft-from-billing-milestone/1");
      return { created, fromSalesOrder, milestone, activated, paused, completed, cancelled, draft };
    });

    expect(result.created.name).toBe("Milestone billing");
    expect(result.fromSalesOrder.total_amount).toBe(250000);
    expect(result.milestone.name).toBe("Go-live milestone");
    expect(result.activated.status).toBe("updated");
    expect(result.paused.status).toBe("updated");
    expect(result.completed.status).toBe("updated");
    expect(result.cancelled.status).toBe("updated");
    expect(result.draft.source_type).toBe("billing_milestone");
  });
});
