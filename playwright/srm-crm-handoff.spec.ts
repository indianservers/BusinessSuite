import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM CRM handoff frontend API", () => {
  test("creates SRM commercial records from a won CRM deal and returns linked lifecycle records", async ({ page }) => {
    const calls: string[] = [];
    await authenticate(page, "srm_admin");
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.includes("/api/v1/srm/")) calls.push(`${request.method()} ${url.pathname}`);
    });

    const result = await page.evaluate(async () => {
      const { srmApi } = await import("/src/apps/srm/api.ts");
      return srmApi.createSalesOrderFromCrmDeal(501);
    });

    expect(calls).toContain("POST /api/v1/srm/from-crm/deals/501/create-sales-order");
    expect(result).toMatchObject({
      sales_order: { order_number: "SO-000001", crm_deal_id: 501 },
      engagement: { engagement_number: "ENG-000001", crm_deal_id: 501 },
      contract: { contract_number: "CTR-000001" },
      billing_plan: { name: "Milestone billing" },
      pms_project: { project_key: "PMS-301" },
    });
  });
});
