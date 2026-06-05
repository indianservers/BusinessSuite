import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM engagement lifecycle frontend API", () => {
  test("loads CRM, SRM, PMS lifecycle links and audit evidence", async ({ page }) => {
    const calls: string[] = [];
    await authenticate(page, "srm_admin");
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.includes("/api/v1/srm/engagements/2/lifecycle")) calls.push(`${request.method()} ${url.pathname}`);
    });

    const lifecycle = await page.evaluate(async () => {
      const { srmApi } = await import("/src/apps/srm/api.ts");
      return srmApi.engagementLifecycle(2);
    });

    expect(calls).toContain("GET /api/v1/srm/engagements/2/lifecycle");
    expect(lifecycle).toMatchObject({
      engagement: { engagement_number: "ENG-000001", crm_deal_id: 501, pms_project_id: 301 },
      sales_order: { order_number: "SO-000001", status: "confirmed" },
      contract: { contract_number: "CTR-000001" },
      billing_plan: { name: "Milestone billing" },
      pms_project: { project_key: "PMS-301" },
    });
    expect(lifecycle.links).toEqual(expect.arrayContaining([
      expect.objectContaining({ linked_module: "crm", linked_entity_type: "deal", linked_entity_id: 501 }),
      expect.objectContaining({ linked_module: "pms", linked_entity_type: "project", linked_entity_id: 301 }),
    ]));
    expect(lifecycle.audit).toEqual(expect.arrayContaining([expect.objectContaining({ action: "crm_won_handoff" })]));
  });
});
