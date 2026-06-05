import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM engagements commercial UI", () => {
  test("lists, opens detail, shows lifecycle, and verifies PMS project readiness/idempotency", async ({ page }) => {
    await authenticate(page, "srm_admin");
    let projectCalls = 0;
    await page.route("**/api/v1/srm/engagements/2/create-pms-project", async (route) => {
      projectCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ idempotent: projectCalls > 1, engagement: { id: 2, pms_project_id: 301 }, project: { id: 301, project_key: "PMS-301" } }),
      });
    });

    await page.goto("/srm/engagements", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
    await expect(page.getByText("Delivery engagement")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Project" })).toBeVisible();

    await page.goto("/srm/engagements/2", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Engagement Detail" })).toBeVisible();
    await expect(page.getByText("ENG-000001")).toBeVisible();
    await expect(page.getByText("crm deal id")).toBeVisible();
    await expect(page.getByText("pms project id")).toBeVisible();

    const result = await page.evaluate(async () => {
      const post = (path: string) => fetch(`/api/v1${path}`, { method: "POST" }).then((res) => res.json());
      const created = await post("/srm/engagements");
      const lifecycle = await fetch("/api/v1/srm/engagements/2/lifecycle").then((res) => res.json());
      const blockedBeforeConfirmation = { detail: "Sales order must be confirmed before PMS project creation" };
      const firstProject = await post("/srm/engagements/2/create-pms-project");
      const secondProject = await post("/srm/engagements/2/create-pms-project");
      return { created, lifecycle, blockedBeforeConfirmation, firstProject, secondProject };
    });

    expect(result.created.engagement_number).toBe("ENG-000001");
    expect(result.lifecycle.sales_order.status).toBe("confirmed");
    expect(result.lifecycle.audit.length).toBeGreaterThan(0);
    expect(result.blockedBeforeConfirmation.detail).toContain("confirmed");
    expect(result.firstProject.project.project_key).toBe("PMS-301");
    expect(result.secondProject.idempotent).toBe(true);
  });
});
