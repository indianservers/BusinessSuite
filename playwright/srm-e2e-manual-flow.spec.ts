import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM seeded E2E manual flow", () => {
  test("runs order to cash with profitability, dashboard, reports, and audit evidence", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });

    const result = await page.evaluate(async () => {
      const json = async (path: string, options: RequestInit = {}) => {
        const response = await fetch(`/api/v1${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}", ...options });
        return response.json();
      };
      const salesOrder = await json("/srm/sales-orders");
      const line = await json("/srm/sales-orders/1/lines");
      const submitted = await json("/srm/sales-orders/1/submit");
      const approved = await json("/srm/sales-orders/1/approve");
      const confirmed = await json("/srm/sales-orders/1/confirm");
      const contract = await json("/srm/contracts");
      const engagement = await json("/srm/engagements");
      const plan = await json("/srm/billing-plans");
      const milestone = await json("/srm/billing-plans/4/milestones");
      const draft = await json("/srm/invoices/draft-from-sales-order/1");
      const invoiceApproved = await json("/srm/invoices/1/approve");
      const invoiceSent = await json("/srm/invoices/1/send");
      const receipt = await json("/srm/receipts");
      const receiptConfirmed = await json("/srm/receipts/1/confirm");
      const allocation = await json("/srm/receipts/1/allocate");
      const profitability = await fetch("/api/v1/srm/profitability").then((res) => res.json());
      const dashboard = await fetch("/api/v1/srm/dashboard").then((res) => res.json());
      const reports = await fetch("/api/v1/srm/reports").then((res) => res.json());
      const lifecycle = await fetch("/api/v1/srm/engagements/2/lifecycle").then((res) => res.json());
      return { salesOrder, line, submitted, approved, confirmed, contract, engagement, plan, milestone, draft, invoiceApproved, invoiceSent, receipt, receiptConfirmed, allocation, profitability, dashboard, reports, lifecycle };
    });

    expect(result.salesOrder.order_number).toBe("SO-000001");
    expect(result.line.line_total).toBe(250000);
    expect(result.submitted.status).toBe("pending_approval");
    expect(result.approved.status).toBe("approved");
    expect(result.confirmed.sales_order.status).toBe("confirmed");
    expect(result.contract.contract_number).toBe("CTR-000001");
    expect(result.engagement.engagement_number).toBe("ENG-000001");
    expect(result.plan.name).toBe("Milestone billing");
    expect(result.milestone.name).toBe("Go-live milestone");
    expect(result.draft.invoice_number).toBe("INV-000001");
    expect(result.invoiceApproved.status).toBe("approved");
    expect(result.invoiceSent.status).toBe("sent");
    expect(result.receipt.receipt_number).toBe("RCT-000001");
    expect(result.receiptConfirmed.status).toBe("confirmed");
    expect(result.allocation.invoice.status).toBe("partially_paid");
    expect(result.profitability[0].gross_margin).toBe(100000);
    expect(result.dashboard.total_sales_orders).toBeGreaterThan(0);
    expect(result.reports.invoice_register.count).toBeGreaterThan(0);
    expect(result.lifecycle.audit.length).toBeGreaterThan(0);
  });
});
