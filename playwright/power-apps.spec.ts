import { test, expect } from "../frontend/node_modules/playwright/test";
import { ids, names, setupPowerApps } from "./power-apps-fixtures";

test("automation creation refreshes the originating list and keeps its search",async({page})=>{
  await setupPowerApps(page);
  await page.goto("/power-apps/automations");
  await page.getByRole("textbox",{name:"Search automations",exact:true}).fill("QA refresh");
  await page.getByRole("button",{name:"New automation",exact:true}).click();
  await page.getByRole("dialog").getByRole("textbox",{name:"Automation name",exact:true}).fill("QA refresh automation");
  await page.getByRole("dialog").getByRole("button",{name:"Save draft",exact:true}).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const groups=page.getByRole("button",{name:"Expand loaded groups",exact:true});
  if(await groups.isVisible())await groups.click();
  await expect(page.getByRole("button",{name:"QA refresh automation",exact:true})).toBeVisible();
  await expect(page.getByRole("textbox",{name:"Search automations",exact:true})).toHaveValue("QA refresh");
  await expect(page).toHaveURL(/\/power-apps\/automations$/);
});
test("Master Suite entry and all twelve application routes", async ({
  page,
}, info) => {
  await setupPowerApps(page);
  await page.setViewportSize({ width: 1536, height: 1100 });
  await page.goto("/");
  const application=page.getByRole("article", { name: "Power Apps", exact:true }).getByRole("link", { name: "Power Apps", exact:true });
  await expect(application).toHaveAttribute("href",/\/power-apps/);
  await page.goto((await application.getAttribute("href"))!);
  await expect(page.locator(".pa-catalog article")).toHaveCount(12);
  await expect(page.locator(".pa-metrics strong")).toHaveText([
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
  ]);
  await expect(page.locator(".async-progress")).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("power-apps-desktop.png"),
    fullPage: true,
  });
  for (let i = 0; i < ids.length; i++) {
    await page
      .locator(".pa-catalog article")
      .nth(i)
      .getByRole("button")
      .click();
    await expect(page).toHaveURL(
      new RegExp("/power-apps/" + ids[i] + "(?:\\?|$)"),
    );
    await expect(
      page.getByRole("heading", { name: ids[i]==="approvals"?"Overview":ids[i]==="connectors"?"Integration Studio":names[i], exact: true,level:1 }),
    ).toBeVisible();
    if(ids[i]==="approvals")await page.locator(".ap-suite-link").click();
    else if(ids[i]==="connectors")await page.locator(".ic-header").getByRole("link",{name:"Power Apps",exact:true}).click();
    else await page.getByRole("link", { name: "Overview", exact: true }).click();
    await expect(page.locator(".pa-catalog article")).toHaveCount(12);
  }
});
test("draft create edit persist switch environments and delete", async ({
  page,
}) => {
  await setupPowerApps(page);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/power-apps/automations");
  await page
    .getByRole("button", { name: "New automation", exact: true })
    .click();
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Welcome review");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const loadedGroups=page.getByRole("button",{name:"Expand loaded groups",exact:true});
  await expect(loadedGroups).toBeVisible();
  await loadedGroups.click();
  await page.getByRole("button",{name:"Welcome review",exact:true}).click();
  await page
    .getByLabel("Automation name", { exact: true })
    .fill("Welcome review v2");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator(".as-save-status")).toContainText("Saved");
  await page.reload();
  await expect(page.getByLabel("Automation name", { exact: true })).toHaveValue(
    "Welcome review v2",
  );
  await page
    .getByRole("button", { name: "Back to automation list", exact: true })
    .click();
  await page
    .getByLabel("Power Apps environment", { exact: true })
    .selectOption("testing");
  await page.getByRole("button",{name:"Expand all menu categories",exact:true}).click();
  await page.getByRole("link", { name: "Automations", exact: true }).click();
  await expect(page.getByText("Make your first connection")).toBeVisible();
  await page
    .getByLabel("Power Apps environment", { exact: true })
    .selectOption("development");
  await page.getByRole("button",{name:"Expand all menu categories",exact:true}).click();
  await page.getByRole("link", { name: "Automations", exact: true }).click();
  await expect(loadedGroups).toBeVisible();
  await loadedGroups.click();
  await page
    .getByLabel("Workflow actions for Welcome review v2", { exact: true })
    .click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("menuitem", { name: "Delete", exact: true }).click();
  await expect(page.getByText("Make your first connection")).toBeVisible();
});
test("mobile dashboard and editor fit viewport", async ({ page }, info) => {
  await setupPowerApps(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/power-apps");
  await expect(page.locator(".pa-catalog article")).toHaveCount(12);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator(".async-progress")).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("power-apps-mobile.png"),
    fullPage: true,
  });
  await page.locator(".pa-catalog article").first().getByRole("button").click();
  await page
    .getByRole("button", { name: "New automation", exact: true })
    .click();
  await expect(
    page.getByLabel("Automation name", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
test("revoked access blocks Power Apps routes", async ({ page }) => {
  await setupPowerApps(page, { allowed: false });
  await page.goto("/power-apps/automations");
  await expect(page.locator(".pa-shell")).toHaveCount(0);
  await expect(
    page
      .getByText(
        /Access denied|Access restricted|don't have access|permission/i,
      )
      .first(),
  ).toBeVisible();
});
test("overview errors stay visible and retry restores database data", async ({
  page,
}) => {
  await setupPowerApps(page);
  const pattern = "**/power-apps/overview?*";
  await page.route(pattern, (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Environment data is temporarily unavailable" },
    }),
  );
  await page.goto("/power-apps");
  await expect(page.locator(".pa-error")).toContainText(
    "Environment data is temporarily unavailable",
  );
  await page.unroute(pattern);
  await page.getByRole("button", { name: "Retry / reload" }).click();
  await expect(page.locator(".pa-error")).toHaveCount(0);
  await expect(page.locator(".pa-catalog article")).toHaveCount(12);
});
