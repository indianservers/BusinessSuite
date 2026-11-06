import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";
async function setup(page: any) {
  await authenticate(page, "admin");
  const rows = [
    {
      id: 701,
      name: "Website delivery",
      project_key: "WEB",
      status: "Active",
      priority: "High",
      health: "Good",
      due_date: "2020-01-01",
      owner_user_id: 100,
      owner_name: "Portfolio owner",
      client_name: "Acme",
      team: [{ id: 100, name: "Portfolio owner", role: "Manager" }],
      task_count: 4,
      completed_task_count: 1,
      calculated_progress: 25,
      overdue_task_count: 1,
      can_edit_project: true,
    },
    {
      id: 702,
      name: "Completed engagement",
      project_key: "DONE",
      status: "Completed",
      priority: "Medium",
      health: "Good",
      task_count: 2,
      completed_task_count: 2,
      calculated_progress: 100,
      can_edit_project: false,
    },
  ].map((p) => ({
    ...p,
    progress_percent: 0,
    is_archived: false,
    created_at: "2026-01-01",
    updated_at: "2026-11-01",
  }));
  await page.route("**/api/v1/project-management/**", async (route: any) => {
    const path = new URL(route.request().url()).pathname;
    let body: any = [];
    if (path.endsWith("/projects")) body = rows;
    else if (path.endsWith("/custom-fields")) body = { fields: [] };
    else if (path.endsWith("/custom-fields/records")) body = { records: {} };
    else if (path.endsWith("/workspaces"))
      body = [{ id: 1, name: "Main workspace", role: "Admin" }];
    else if (route.request().method() === "PATCH") {
      const p = rows.find((p) => path.endsWith("/" + p.id));
      Object.assign(p!, route.request().postDataJSON());
      body = p;
    }
    await route.fulfill({ json: body });
  });
  await page.route("**/api/v1/pipeline-workspaces/**", async (route: any) =>
    route.fulfill({
      json:
        route.request().method() === "GET"
          ? { preferences: { module_filters: {} }, views: [], can_share: true }
          : {},
    }),
  );
  await page.route("**/api/v1/access/settings/defaults/effective", (route) =>
    route.fulfill({
      json: { values: {}, modules: {}, companyId: 1, branchId: null },
    }),
  );
  await page.route("**/api/v1/access/setup", (route) =>
    route.fulfill({ json: { companyId: 1, ready: true, items: [] } }),
  );
  await page.goto("/pms/projects");
  await expect(page.locator(".portfolio-table tbody tr")).toHaveCount(2);
}
test("portfolio filters, edits, previews, export and views", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1680, height: 1000 });
  await setup(page);
  await expect(page.locator(".portfolio-ring")).toHaveText("50%");
  await page.screenshot({
    path: "docs/qa/pms-portfolio-desktop.png",
    fullPage: true,
  });
  await page
    .getByLabel("Portfolio summary")
    .getByRole("button", { name: "Overdue 1", exact: true })
    .click();
  await expect(page.locator(".portfolio-table tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "All Projects 2", exact: true })
    .click();
  await page
    .getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    })
    .selectOption("Critical");
  await expect(page.getByRole("status")).toContainText("updated");
  await page
    .getByRole("button", { name: "Preview Website delivery", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("1 complete / 4 total");
  await page.keyboard.press("Escape");
  await page.getByRole("textbox", { name: "Search projects" }).fill("Acme");
  await expect(page.locator(".portfolio-table tbody tr")).toHaveCount(1);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("projects.csv");
  await page.getByRole("navigation",{name:"Portfolio views"}).getByRole("button", { name: "Gallery", exact: true }).click();
  await expect(page.locator(".portfolio-cards article")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Dashboard", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Projects by status" }),
  ).toBeVisible();
});
test("mobile cards and quick creation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await expect(page.locator(".portfolio-table-wrap")).toBeHidden();
  await expect(page.locator(".portfolio-mobile-cards article")).toHaveCount(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "docs/qa/pms-portfolio-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "New Project", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Main workspace");
  await expect(
    page.getByRole("button", { name: "Create project", exact: true }),
  ).toBeDisabled();
});
test("compound conditions and bulk changes respect editable selection", async ({
  page,
}) => {
  await setup(page);
  await page.getByRole("button", { name: "More filters", exact: true }).click();
  await page.getByText("Combine filter conditions", { exact: false }).click();
  await page
    .getByRole("button", { name: "Add condition", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Condition 1 value" })
    .fill("Website");
  await expect(page.locator(".portfolio-table tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Add condition", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Condition 2 value" })
    .fill("Completed");
  await expect(page.locator(".portfolio-table tbody tr")).toHaveCount(0);
  await page
    .getByRole("combobox", { name: "Filter condition matching" })
    .selectOption("any");
  await expect(page.locator(".portfolio-table tbody tr")).toHaveCount(2);
  await page
    .getByRole("checkbox", { name: "Select Completed engagement", exact: true })
    .isDisabled();
  await page
    .getByRole("checkbox", { name: "Select Website delivery", exact: true })
    .check();
  await page
    .getByRole("combobox", { name: "Bulk priority", exact: true })
    .selectOption("Low");
  await expect(
    page.getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    }),
  ).toHaveValue("Low");
  await page.route("**/api/v1/project-management/projects/701", (route) =>
    route.fulfill({ status: 403, json: { detail: "Access changed" } }),
  );
  await page
    .getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    })
    .selectOption("High");
  await expect(page.getByRole("alert")).toContainText("Access changed");
  await expect(
    page.getByRole("combobox", {
      name: "Priority for Website delivery",
      exact: true,
    }),
  ).toHaveValue("Low");
});
