import { test, expect, type Page } from "../frontend/node_modules/playwright/test";

// Exercise the production page with an isolated API, without a developer account or database.
async function openLibrary(page: Page, role = "Owner", projects = [{ id: 8, name: "Customer launch" }]) {
  let tools: Record<string, unknown>[] = [];
  const writes: { path: string; body: any; method: string }[] = [];
  await page.addInitScript(() => { window.__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" }; });
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (method !== "GET") {
      const body = request.postDataJSON();
      writes.push({ path, body, method });
      if (path.endsWith("/apply")) return route.fulfill({ json: { task_ids: body.task_titles.map((_: string, index: number) => index + 100) } });
      if (method === "POST" && path.endsWith("/tools")) {
        tools = [{ ...body, id: 20, enabled: true }, ...tools];
        return route.fulfill({ status: 201, json: tools[0] });
      }
      if (method === "PATCH") {
        tools = tools.map(tool => tool.id === 20 ? { ...tool, ...body } : tool);
        return route.fulfill({ json: tools[0] });
      }
    }
    if (path.endsWith("/workspaces")) return route.fulfill({ json: [{ id: 7, name: "Delivery", role }] });
    if (path.endsWith("/overview")) return route.fulfill({ json: { projects, tasks: [] } });
    if (path.endsWith("/tools")) return route.fulfill({ json: tools });
    return route.fulfill({ json: [] });
  });
  await page.goto("/test-harnesses/blueprints.html");
  await expect(page.getByRole("heading", { name: "Start with a proven plan" })).toBeVisible();
  return writes;
}

test("catalog has 120 distinct complete blueprints, searchable across 12 categories", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openLibrary(page);
  const tabColors = await page.getByRole("tab", { name: "Blueprints", exact: true }).evaluate(element => ({ text: getComputedStyle(element).color, background: getComputedStyle(element).backgroundColor }));
  expect(tabColors.text).not.toBe(tabColors.background);
  await page.screenshot({ path: testInfo.outputPath("blueprint-catalog-desktop.png") });
  const inventory = await page.evaluate(async () => {
    const { blueprints, blueprintCategories } = await import(/* @vite-ignore */ "/src/apps/project-management/data/blueprints.ts");
    return { total: blueprints.length, categories: blueprintCategories.length,
      unique: new Set(blueprints.map((item: any) => item.id)).size,
      counts: blueprintCategories.map((category: any) => blueprints.filter((item: any) => item.category === category.name).length),
      valid: blueprints.every((item: any) => item.useWhen && item.outcome && item.name.length <= 120 && item.task_titles.length >= 6
        && new Set(item.task_titles).size === item.task_titles.length && item.task_titles.every((title: string) => title.trim() && title.length <= 220)) };
  });
  expect(inventory).toEqual({ total: 120, categories: 12, unique: 120, counts: Array(12).fill(10), valid: true });
  await page.getByLabel("Blueprint category", { exact: true }).selectOption("Software & Engineering");
  await expect(page.getByRole("status").filter({ hasText: "10 matching blueprints" })).toBeVisible();
  await page.getByLabel("Search blueprint catalog").fill("rollback");
  await expect(page.getByRole("heading", { name: "Release readiness", exact: true })).toBeVisible();
  await page.getByLabel("Search blueprint catalog").fill("no-such-workflow");
  await expect(page.getByText("No blueprints match these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Clear catalog filters" }).click();
  await page.getByRole("button", { name: /Show more blueprints/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "showing 24" })).toBeVisible();
});

test("customize, save, edit, and create a one-time variation without changing the saved plan", async ({ page }) => {
  const writes = await openLibrary(page);
  await page.getByRole("button", { name: "Preview and customize New employee onboarding", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Blueprint name", { exact: true }).fill("Support team onboarding");
  await dialog.getByLabel("Blueprint task 1", { exact: true }).fill("Confirm support buddy and first-week goals");
  await dialog.getByRole("button", { name: "Move task 1 down", exact: true }).click();
  await expect(dialog.getByLabel("Blueprint task 2", { exact: true })).toHaveValue("Confirm support buddy and first-week goals");
  await dialog.getByRole("button", { name: "Remove task 6", exact: true }).click();
  await dialog.getByRole("button", { name: "Add task", exact: true }).click();
  await dialog.getByLabel("Blueprint task 6", { exact: true }).fill("Practice a support escalation");
  await dialog.getByRole("button", { name: "Save workspace copy", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(writes).toHaveLength(1);
  expect(writes[0].body.task_titles[5]).toBe("Practice a support escalation");
  await page.getByRole("button", { name: "Workspace blueprints (1)", exact: true }).click();
  await page.getByRole("button", { name: "Preview and customize", exact: true }).click();
  await dialog.getByLabel("Blueprint name", { exact: true }).fill("Support onboarding v2");
  await dialog.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Support onboarding v2", exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Preview and customize", exact: true }).click();
  await dialog.getByLabel("Blueprint task 1", { exact: true }).fill("One-time setup for the October hire");
  await dialog.getByRole("button", { name: "Create 6 tasks", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(writes[2].path.endsWith("/tools/20/apply")).toBe(true);
  expect(writes[2].body.task_titles[0]).toBe("One-time setup for the October hire");
  await expect(page.getByRole("link", { name: "Open created task #100", exact: true })).toBeVisible();
});

test("member creates directly from the catalog and guests can only preview", async ({ page }) => {
  const writes = await openLibrary(page, "Member");
  await page.getByRole("button", { name: "Preview and customize New employee onboarding", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save workspace copy" })).toHaveCount(0);
  await page.getByRole("button", { name: "Create 6 tasks", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(writes[0].path.endsWith("/blueprints/apply")).toBe(true);
  expect(writes[0].body.project_id).toBe(8);
  await page.unrouteAll({ behavior: "wait" });
  const guestWrites = await openLibrary(page, "Guest");
  await page.getByRole("button", { name: "Preview and customize New employee onboarding", exact: true }).click();
  await expect(page.getByRole("button", { name: "Create 6 tasks", exact: true })).toBeDisabled();
  await expect(page.getByRole("dialog").getByLabel("Blueprint name", { exact: true })).toBeDisabled();
  expect(guestWrites).toHaveLength(0);
});

test("mobile editor fits the viewport and requires a destination project", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const writes = await openLibrary(page, "Owner", []);
  await page.getByRole("button", { name: "Preview and customize New employee onboarding", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Create a project in this workspace before saving or using a blueprint.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Create 6 tasks", exact: true })).toBeDisabled();
  const dimensions = await dialog.evaluate(element => ({ width: element.getBoundingClientRect().width, scroll: element.scrollWidth, client: element.clientWidth }));
  expect(dimensions.width).toBeLessThanOrEqual(390);
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
  await page.screenshot({ path: testInfo.outputPath("blueprint-editor-mobile.png") });
  expect(writes).toHaveLength(0);
});

test("failed creation retains edits and reuses the request ID when retried", async ({ page }) => {
  const writes = await openLibrary(page, "Member");
  let failedRequest: any;
  await page.route("**/blueprints/apply", async route => {
    if (failedRequest) return route.fallback();
    failedRequest = route.request().postDataJSON();
    return route.fulfill({ status: 503, json: { detail: "Temporary service interruption. Retry this request." } });
  });
  await page.getByRole("button", { name: "Preview and customize New employee onboarding", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Blueprint task 1", { exact: true }).fill(" ");
  await dialog.getByRole("button", { name: "Create 6 tasks", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("nonempty task titles");
  expect(failedRequest).toBeUndefined();
  await dialog.getByLabel("Blueprint task 1", { exact: true }).fill("Prepare October hire access");
  await dialog.getByRole("button", { name: "Create 6 tasks", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Temporary service interruption");
  await expect(dialog.getByLabel("Blueprint task 1", { exact: true })).toHaveValue("Prepare October hire access");
  await dialog.getByRole("button", { name: "Create 6 tasks", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(writes[0].body.request_id).toBe(failedRequest.request_id);
});
