import {expect, test, type Page} from "../frontend/node_modules/playwright/test";
import {authenticateCrm} from "./crm-core-test-utils";

const deal = {id: 1, name: "Enterprise renewal", company_id: 1, contact_id: 1, owner_user_id: 100, pipeline_id: 1, stage_id: 1, amount: 25000, currency: "INR", probability: 50, priority: "High", status: "Open", version: 1, expected_close_date: "2026-11-25", planning: {qualification: {business_need: "Renewal planning"}}, catalog_items: []};

async function setup(page: Page) {
  await authenticateCrm(page);
  await page.route("**/api/v1/crm/deal-workspace/**", async route => {
    const url = new URL(route.request().url()), path = url.pathname;
    let payload: any = {items: [], total: 0, pages: 1};
    if (path.endsWith("/record")) payload = {...deal, related: {account: {id: 1, name: "Acme"}, contact: {id: 1, full_name: "John"}, notes: [{id: 1, body: "Customer requested a renewal proposal."}], tasks: [{id: 1, title: "Prepare renewal", status: "To Do"}], files: [], contacts: [], quotations: [{id: 1, quote_number: "QT-001", status: "Draft", grand_total: 25000, currency: "INR"}], products: []}};
    if (path.endsWith("/query")) payload = {items: [{...deal, health: {score: 60, reasons: ["No next action scheduled"]}}], total: 1, page: 1, pages: 1, can_manage: true, can_assign: true};
    if (path.endsWith("/summary")) payload = {counts: {open: 1, closing_month: 1, won_month: 0, lost_month: 0, overdue: 0, without_activity: 1}, currencies: [{currency: "INR", pipeline: 25000, weighted: 12500}, {currency: "USD", pipeline: 100, weighted: 50}], stages: [{stage_id: 1, currency: "INR", count: 1, amount: 25000}], forecast: [{month: "2026-11", currency: "INR", count: 1, amount: 25000, weighted: 12500}], breakdowns: {owner: [{id: 100, currency: "INR", amount: 25000, weighted: 12500, count: 1}]}, definitions: {pipeline: "Open deals separated by currency"}};
    if (path.endsWith("/assignees")) payload = {items: [{id: 100, name: "Sales Admin", userId: 100}], total: 1, pages: 1};
    if (path.endsWith("/insights")) payload = {score: 60, level: "Needs Attention", age_days: 12, stage_age_days: 3, qualification_score: 29, reasons: ["No next action scheduled"], stage_name: "Qualification", pipeline_name: "Sales", owner_name: "Sales Admin"};
    if (path.endsWith("/collaborators")) payload = {items: [], can_assign: true};
    if (path.endsWith("/events")) payload = {items: [{type: "stage_change", title: "Stage changed to Qualification", occurredAt: "2026-11-01T08:00:00Z", record: {description: "Moved from Discovery", actor_user_id: 100}}], total: 1, pages: 1};
    if (path.endsWith("/pipelines")) payload = {items: [{id: 1, name: "Enterprise Sales"}], total: 1, pages: 1};
    if (path.endsWith("/pipeline-stages")) payload = {items: [{id: 1, name: "Qualification", pipeline_id: 1, probability: 20}, {id: 2, name: "Proposal", pipeline_id: 1, probability: 60}, {id: 3, name: "Closed Won", pipeline_id: 1, probability: 100, is_won: true}], total: 3, pages: 1};
    await route.fulfill({json: payload});
  });
  await page.route("**/api/v1/crm/deals/1", async route => route.fulfill({json: {...deal, related: {account: {id: 1, name: "Acme"}, contact: {id: 1, full_name: "John"}, notes: [{id: 1, body: "Customer requested a renewal proposal."}], tasks: [{id: 1, title: "Prepare renewal", status: "To Do"}], files: [], contacts: [], quotations: [{id: 1, quote_number: "QT-001", status: "Draft", grand_total: 25000, currency: "INR"}], products: []}, timeline: []}}));
}

test("all deal views use real response data, currency filters, and saved preferences", async ({page}) => {
  await setup(page);
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto("/crm/deals");
  await expect(page.getByRole("link", {name: "Enterprise renewal", exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Pipeline", exact: true}).click();
  await expect(page.locator(".ed-board .ed-card")).toHaveCount(1);
  await page.getByRole("button", {name: "Timeline", exact: true}).click();
  await expect(page.locator(".ed-timeline time")).toHaveText("2026-11-25");
  await page.getByRole("button", {name: "List", exact: true}).click();
  await expect(page.locator(".ed-list details")).toHaveCount(1);
  await page.getByRole("button", {name: "Forecast", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Revenue forecast"})).toBeVisible();
  await page.getByLabel("Forecast grouping").selectOption("owner");
  await expect(page.locator(".ed-forecast").filter({has:page.getByRole("heading", {name:"Revenue forecast"})})).toContainText("Sales Admin");
  await page.getByRole("combobox", {name: "Currency", exact: true}).selectOption("USD");
  await expect.poll(() => page.url()).toContain("/crm/deals");
  await page.getByLabel("View name").fill("Dollar renewals");
  await page.getByRole("button", {name: "Save view", exact: true}).click();
  await page.reload();
  await expect(page.getByLabel("Saved deal views").locator("option")).toContainText(["My saved views", "Dollar renewals"]);
  await page.screenshot({path: "test-results/crm-enterprise-workspace.png", fullPage: true});
});

test("advanced create keeps all six tabs, paginates choices, and retains drafts on validation failure", async ({page}) => {
  await setup(page);
  const calls: number[] = [];
  await page.route("**/api/v1/crm/deal-workspace/pipelines?**", async route => {
    const url = new URL(route.request().url()), number = Number(url.searchParams.get("page") || 1);
    calls.push(Number(url.searchParams.get("per_page")));
    await route.fulfill({json: {items: number === 1 ? Array.from({length: 100}, (_, index) => ({id: index + 1, name: `Pipeline ${index + 1}`})) : [{id: 101, name: "Pipeline 101"}], total: 101, pages: 2, page: number}});
  });
  await page.route("**/api/v1/crm/deals", async route => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({status: 422, json: {detail: [{loc: ["body", "name"], msg: "Review this deal name", type: "value_error"}]}});
  });
  await page.goto("/crm/deals");
  await page.getByRole("button", {name: "Create deal", exact: true}).first().click();
  const dialog = page.getByRole("dialog", {name: "Create deal", exact: true});
  await dialog.getByPlaceholder("Enter deal name...").fill("Enterprise capture draft");
  await expect(dialog.getByLabel("Pipeline", {exact: true}).locator("option")).toHaveCount(102);
  await dialog.getByLabel("Pipeline", {exact: true}).selectOption("1");
  await dialog.locator("label").filter({hasText: /^Stage/}).locator("select").selectOption("1");
  await dialog.getByRole("button", {name: "Advanced Create", exact: true}).click();
  for (const title of ["Deal Overview", "Financial Information", "People and Ownership", "Timeline", "Qualification", "Notes & Attachments"]) await expect(dialog.getByRole("button", {name: title, exact: true})).toBeVisible();
  await dialog.getByRole("button", {name: "Qualification", exact: true}).click();
  await dialog.getByLabel("Business Need", {exact: true}).fill("Customer needs a secure renewal platform");
  await dialog.getByRole("button", {name: "Notes & Attachments", exact: true}).click();
  await dialog.getByLabel("Internal notes", {exact: true}).fill("Keep this note after an API error");
  await dialog.getByRole("button", {name: "Create Deal", exact: true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Review this deal name");
  await dialog.getByRole("button", {name: "Qualification", exact: true}).click();
  await expect(dialog.getByLabel("Business Need", {exact: true})).toHaveValue("Customer needs a secure renewal platform");
  await dialog.getByRole("button", {name: "Save draft", exact: true}).click();
  expect(calls.every(number => number <= 100)).toBe(true);
  await page.screenshot({path: "test-results/crm-advanced-deal.png", fullPage: true});
});

test("deal 360 tabs load genuine notes, tasks, quotations, paginated history, and insights", async ({page}) => {
  await setup(page);
  await page.goto("/crm/deals/1");
  await expect(page.getByRole("heading", {name: "Enterprise renewal"})).toBeVisible();
  await page.getByRole("button", {name: "Tasks", exact: true}).click();
  await expect(page.getByText("Prepare renewal", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Notes & Files", exact: true}).click();
  await expect(page.getByText("Customer requested a renewal proposal.", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Products & Quotations", exact: true}).click();
  await expect(page.getByRole("link", {name: "QT-001", exact: true})).toBeVisible();
  await page.getByRole("button", {name: "History", exact: true}).click();
  await expect(page.getByText("Stage changed to Qualification", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Insights", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Deal intelligence"})).toBeVisible();
  await expect(page.getByText("29%", {exact: true})).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  await expect(page.getByRole("heading", {name: "Enterprise renewal"})).toBeVisible();
  await page.screenshot({path: "test-results/crm-deal-360-mobile.png", fullPage: true});
  await expect.poll(() => page.locator("main.ed-workspace").evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({path: "test-results/crm-deal-360-mobile.png", fullPage: true});
});

test("dragging a pipeline card opens a reviewed, versioned stage transition", async ({page}) => {
  await setup(page);
  let submitted: any;
  await page.route("**/api/v1/crm/productivity/deals/1/stages", route => route.fulfill({json: {version: 1, current_stage_id: 1, values: {}, stages: [{id: 1, name: "Qualification", required: [], missing: [], recommended_actions: "Confirm need", completion_criteria: "Ready"}, {id: 2, name: "Proposal", required: [], missing: [], recommended_actions: "Prepare proposal", completion_criteria: "Ready"}]}}));
  await page.route("**/api/v1/crm/productivity/deals/1/transition", async route => {submitted = route.request().postDataJSON();await route.fulfill({json: {...deal, stage_id: 2, version: 2}});});
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto("/crm/deals");
  await page.getByRole("button", {name: "Pipeline", exact: true}).click();
  await page.locator(".ed-board .ed-card").first().dragTo(page.locator(".ed-board>section").nth(1));
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Review deal stage move", {exact: true})).toBeVisible();
  await expect(dialog.getByLabel("Destination stage")).toHaveValue("2");
  await dialog.getByRole("button", {name: "Apply reviewed stage move"}).click();
  await expect.poll(() => submitted).toBeTruthy();
  expect(submitted.stage_id).toBe(2);
  expect(submitted.expected_version).toBe(1);
});

test("editing qualification sends the changed structured section and the original version", async ({page}) => {
  await setup(page);
  let submitted: any;
  await page.route("**/api/v1/crm/deals/1", async route => {if (route.request().method() !== "PATCH") return route.fallback();submitted = route.request().postDataJSON();await route.fulfill({json: {...deal, ...submitted, version: 2}});});
  await page.goto("/crm/deals");
  await page.getByRole("button", {name: "Edit", exact: true}).click();
  const dialog = page.getByRole("dialog", {name: "Edit deal", exact: true});
  await dialog.getByRole("button", {name: "Advanced Create", exact: true}).click();
  await dialog.getByRole("button", {name: "Qualification", exact: true}).click();
  await dialog.getByLabel("Business Need", {exact: true}).fill("Updated customer qualification");
  await dialog.getByRole("button", {name: "Save changes", exact: true}).click();
  await expect.poll(() => submitted).toBeTruthy();
  expect(submitted.planning.qualification.business_need).toBe("Updated customer qualification");
  expect(submitted.expected_version).toBe(1);
});

test("editing a legacy deal keeps existing product associations and saved value", async ({page}) => {
  await setup(page);
  let submitted: any;
  await page.route("**/api/v1/crm/deal-workspace/1/record", route => route.fulfill({json: {...deal, amount: 110, catalog_items: null, related: {contacts: [], products: [{id: 7, product_id: 21, quantity: 1, unit_price: 100, discount_amount: 10, total_amount: 110, product: {id: 21, name: "Legacy product"}}]}}}));
  await page.route("**/api/v1/crm/deals/1", async route => {if (route.request().method() !== "PATCH") return route.fallback();submitted = route.request().postDataJSON();await route.fulfill({json: {...deal, ...submitted, version: 2}});});
  await page.goto("/crm/deals");
  await page.getByRole("button", {name: "Edit", exact: true}).click();
  const dialog = page.getByRole("dialog", {name: "Edit deal", exact: true});
  await expect(dialog.getByLabel("Catalog item")).toHaveValue("product:21");
  await dialog.getByPlaceholder("Enter deal name...").fill("Legacy deal renamed");
  await dialog.getByRole("button", {name: "Save changes", exact: true}).click();
  await expect.poll(() => submitted).toBeTruthy();
  expect(submitted.name).toBe("Legacy deal renamed");
  expect(submitted.amount).toBeUndefined();
  expect(submitted.catalog_items).toBeUndefined();
});
