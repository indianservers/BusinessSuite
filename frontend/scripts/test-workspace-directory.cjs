const { chromium, expect } = require("playwright/test");
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    let emptyResponses = false;
    const errors = [],
      reads = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/api/v1/**", (r) => {
      reads.push(r.request().url());
      return r.fulfill({
        json: r.request().url().endsWith("/activity") ? [] : { items: emptyResponses ? [] : [
          { id: "1", name: "Design Workspace", role: "Owner", status: "Active", views: [], version: 0 },
          { id: "2", name: "Recent Workspace", role: "Member", status: "Active", views: [], version: 0 },
        ], can_create: true },
      });
    });
    await page.route("**/workspace-directory-qa", (r) =>
      r.fulfill({
        contentType: "text/html",
        body: '<div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/workspace-directory-qa.tsx");</script>',
      }),
    );
    await page.goto("http://localhost:5174/workspace-directory-qa");
    await expect(
      page.getByRole("heading", { name: "Workspaces", exact: true }),
    ).toBeVisible();
    const list = page.getByRole("region", { name: "Workspace list" });
    await expect(list.getByRole("link")).toHaveCount(2);
    await expect(
      list.getByRole("link", { name: /Design Workspace/ }),
    ).toHaveAttribute("href", "/pms/workspaces?space=1");
    if (reads.some((u) => /overview|members|invitations/.test(u)))
      throw Error("Directory auto-loaded a workspace");
    await page
      .getByRole("textbox", { name: "Search workspaces" })
      .fill("Design");
    await expect(list.getByRole("link")).toHaveCount(1);
    await page
      .getByRole("button", { name: "Explore pages", exact: true })
      .click();
    await expect(page.getByLabel("Explore module pages")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Switch workspace", exact: true }),
    ).toHaveCount(0);
    await page.keyboard.press("Escape");
    await page.getByRole("textbox", {name:"Search workspaces"}).fill("");
    await page.getByRole("button", {name:"List view",exact:true}).click();
    await expect(list.getByRole("columnheader",{name:/Workspace/})).toBeVisible();
    await expect(list.getByRole("button",{name:/^Columns /})).toBeVisible();
    await expect(list.getByRole("button",{name:"Favorite Design Workspace",exact:true})).toHaveCount(1);
    await list.getByRole("button",{name:"Favorite Design Workspace",exact:true}).click();
    await expect(list.getByRole("button",{name:"Unfavorite Design Workspace",exact:true})).toHaveAttribute("aria-pressed","true");
    await list.getByLabel("Add grouping column").selectOption({label:"Access / Category"});
    await list.getByRole("button",{name:"Expand loaded groups",exact:true}).click();
    await expect(list.locator(".suite-group-badge")).toHaveCount(2);
    await expect(list.getByRole("link",{name:/Design Workspace/})).toHaveAttribute("href","/pms/workspaces?space=1");
    const resize=list.getByRole("separator",{name:"Resize Workspace",exact:true});
    const width=Number(await resize.getAttribute("aria-valuenow"));await resize.focus();await page.keyboard.press("ArrowRight");
    if(Number(await resize.getAttribute("aria-valuenow"))<=width)throw Error("Workspace column resize did not apply");
    await page.screenshot({path:"outputs/workspace-directory-list.png"});
    emptyResponses = true;
    await page.reload();
    await expect(list.getByRole("columnheader",{name:/Workspace/})).toBeVisible();
    await expect(list.locator(".suite-count-total strong")).toHaveText("0");
    await expect(list.getByRole("button",{name:/^Columns /})).toBeVisible();
    await page.screenshot({path:"outputs/workspace-directory-empty-list.png"});
    if (errors.length) throw Error(errors.join("; "));
    console.log(
      "PASS: saved recent workspace does not auto-open, workspace list/search/direct links, original favorite controls, shared columns/grouping/resize, empty list controls and Explore pages menu label",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
