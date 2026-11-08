const { chromium, expect } = require("playwright/test");
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const errors = [],
      reads = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/api/v1/**", (r) => {
      reads.push(r.request().url());
      return r.fulfill({
        json: [
          { id: 1, name: "Design Workspace", role: "Owner" },
          { id: 2, name: "Recent Workspace", role: "Member" },
        ],
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
    ).toHaveAttribute("href", "/pms/workspaces?workspace=1");
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
    if (errors.length) throw Error(errors.join("; "));
    console.log(
      "PASS: saved recent workspace does not auto-open, workspace list/search/direct links, Explore pages menu label",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
