import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM sales orders commercial UI", () => {
  test("lists, opens detail, manages lines, and verifies sales order status guards", async ({ page }) => {
    await authenticate(page, "srm_admin");

    await page.goto("/srm/sales-orders", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Sales Orders" })).toBeVisible();
    await expect(page.getByText("Implementation order")).toBeVisible();
    await expect(page.getByText("confirmed")).toBeVisible();
    await expect(page.getByRole("button", { name: "Submit" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Draft" })).toBeVisible();

    await page.goto("/srm/sales-orders/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Sales Order Detail" })).toBeVisible();
    await expect(page.getByText("SO-000001")).toBeVisible();
    await expect(page.getByText("customer id")).toBeVisible();
    await expect(page.getByText("crm deal id")).toBeVisible();
    await expect(page.getByText("pms project id")).toBeVisible();

    const result = await page.evaluate(async () => {
      const post = (path: string) => fetch(`/api/v1${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then((res) => res.json());
      const addLine = await post("/srm/sales-orders/1/lines");
      const submit = await post("/srm/sales-orders/1/submit");
      const approve = await post("/srm/sales-orders/1/approve");
      const confirm = await post("/srm/sales-orders/1/confirm");
      const duplicateDraft = await post("/srm/invoices/draft-from-sales-order/1");
      return { addLine, submit, approve, confirm, duplicateDraft };
    });

    expect(result.addLine.line_total).toBe(250000);
    expect(result.submit.status).toBe("pending_approval");
    expect(result.approve.status).toBe("approved");
    expect(result.confirm.sales_order.status).toBe("confirmed");
    expect(result.confirm.billing_plan.name).toBe("Milestone billing");
    expect(result.duplicateDraft.invoice_number).toBe("INV-000001");
  });
});
