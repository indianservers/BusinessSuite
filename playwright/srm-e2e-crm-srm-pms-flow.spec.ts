import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM seeded E2E CRM to SRM to PMS flow", () => {
  test("creates commercial handoff, PMS project, link-backs, lifecycle, and idempotent result", async ({ page }) => {
    await authenticate(page, "srm_admin");
    let handoffCount = 0;
    let projectCount = 0;
    await page.route("**/api/v1/srm/from-crm/deals/501/create-sales-order", async (route) => {
      handoffCount += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ idempotent: handoffCount > 1, sales_order: { id: 1, order_number: "SO-000001" }, contract: { id: 3, contract_number: "CTR-000001" }, engagement: { id: 2, engagement_number: "ENG-000001" }, billing_plan: { id: 4, name: "Milestone billing" } }) });
    });
    await page.route("**/api/v1/srm/engagements/2/create-pms-project", async (route) => {
      projectCount += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ idempotent: projectCount > 1, engagement: { id: 2, pms_project_id: 301 }, project: { id: 301, project_key: "PMS-301" } }) });
    });

    const result = await page.evaluate(async () => {
      const post = (path: string) => fetch(`/api/v1${path}`, { method: "POST" }).then((res) => res.json());
      const firstHandoff = await post("/srm/from-crm/deals/501/create-sales-order");
      const secondHandoff = await post("/srm/from-crm/deals/501/create-sales-order");
      await post("/srm/sales-orders/1/confirm");
      const firstProject = await post("/srm/engagements/2/create-pms-project");
      const secondProject = await post("/srm/engagements/2/create-pms-project");
      const lifecycle = await fetch("/api/v1/srm/engagements/2/lifecycle").then((res) => res.json());
      const crmDeal = await fetch("/api/v1/crm/deals/501").then((res) => res.json());
      const pmsProject = await fetch("/api/v1/project-management/projects/301").then((res) => res.json());
      return { firstHandoff, secondHandoff, firstProject, secondProject, lifecycle, crmDeal, pmsProject };
    });

    expect(result.firstHandoff.sales_order.order_number).toBe("SO-000001");
    expect(result.firstHandoff.contract.contract_number).toBe("CTR-000001");
    expect(result.firstHandoff.engagement.engagement_number).toBe("ENG-000001");
    expect(result.firstHandoff.billing_plan.name).toBe("Milestone billing");
    expect(result.secondHandoff.idempotent).toBe(true);
    expect(result.firstProject.project.project_key).toBe("PMS-301");
    expect(result.secondProject.idempotent).toBe(true);
    expect(result.lifecycle.links.length).toBeGreaterThan(1);
    expect(result.crmDeal.related.srm.salesOrder.order_number).toBe("SO-000001");
    expect(result.pmsProject.srm_links.engagement.engagement_number).toBe("ENG-000001");
  });
});
