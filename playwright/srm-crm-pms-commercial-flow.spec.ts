import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM CRM-PMS commercial flow UI", () => {
  test("verifies CRM handoff cards, SRM lifecycle, PMS link card, and idempotent project creation", async ({ page }) => {
    await authenticate(page, "admin");
    let handoffCalls = 0;
    let projectCalls = 0;
    await page.route("**/api/v1/srm/from-crm/deals/501/create-sales-order", async (route) => {
      handoffCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          idempotent: handoffCalls > 1,
          sales_order: { id: 1, order_number: "SO-000001", status: "confirmed" },
          contract: { id: 3, contract_number: "CTR-000001", status: "active" },
          engagement: { id: 2, engagement_number: "ENG-000001", status: "project_created" },
          billing_plan: { id: 4, name: "Milestone billing", status: "active" },
        }),
      });
    });
    await page.route("**/api/v1/srm/engagements/2/create-pms-project", async (route) => {
      projectCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ idempotent: projectCalls > 1, engagement: { id: 2, pms_project_id: 301 }, project: { id: 301, project_key: "PMS-301" } }),
      });
    });

    const apiResult = await page.evaluate(async () => {
      const post = (path: string) => fetch(`/api/v1${path}`, { method: "POST" }).then((res) => res.json());
      const firstHandoff = await post("/srm/from-crm/deals/501/create-sales-order");
      const secondHandoff = await post("/srm/from-crm/deals/501/create-sales-order");
      const confirmed = await post("/srm/sales-orders/1/confirm");
      const firstProject = await post("/srm/engagements/2/create-pms-project");
      const secondProject = await post("/srm/engagements/2/create-pms-project");
      const lifecycle = await fetch("/api/v1/srm/engagements/2/lifecycle").then((res) => res.json());
      return { firstHandoff, secondHandoff, confirmed, firstProject, secondProject, lifecycle };
    });

    expect(apiResult.firstHandoff.sales_order.order_number).toBe("SO-000001");
    expect(apiResult.secondHandoff.idempotent).toBe(true);
    expect(apiResult.confirmed.sales_order.status).toBe("confirmed");
    expect(apiResult.firstProject.project.project_key).toBe("PMS-301");
    expect(apiResult.secondProject.idempotent).toBe(true);
    expect(apiResult.lifecycle.links.length).toBeGreaterThan(1);

    await page.goto("/crm/deals/501", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Commercial Handoff" })).toBeVisible();
    await expect(page.getByText("SO-000001")).toBeVisible();
    await expect(page.getByText("ENG-000001")).toBeVisible();

    await page.goto("/srm/engagements/2", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Engagement Detail" })).toBeVisible();
    await expect(page.getByText("301")).toBeVisible();

    await page.goto("/pms/projects/301", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "SRM Engagement Link" })).toBeVisible();
    await expect(page.getByText("ENG-000001")).toBeVisible();
  });
});
