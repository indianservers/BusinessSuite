/* Isolated loopback QA API and generated suite harness only. */
const path = require("node:path");
process.chdir(path.resolve(__dirname, "../.."));
const { chromium } = require("../node_modules/playwright");
const { AxeBuilder } = require(
  process.env.AXE_PLAYWRIGHT_MODULE || "@axe-core/playwright",
);
const fs = require("fs");
(async () => {
  const session = await (
    await fetch("http://127.0.0.1:8775/qa-session")
  ).json();
  const dashboards = await (
    await fetch("http://127.0.0.1:8775/api/v1/project-management/dashboards", {
      headers: { Authorization: "Bearer " + session.token },
    })
  ).json();
  let d = dashboards.find((d) => d.name === "Project delivery overview");
  if (!d) {
    const headers = {
      Authorization: "Bearer " + session.token,
      "Content-Type": "application/json",
    };
    const ws = await (
      await fetch(
        "http://127.0.0.1:8775/api/v1/project-management/workspaces",
        {
          method: "POST",
          headers,
          body: JSON.stringify({ name: "Dashboard visual verification" }),
        },
      )
    ).json();
    const project = await (
      await fetch("http://127.0.0.1:8775/api/v1/project-management/projects", {
        method: "POST",
        headers,
        body: JSON.stringify({
          workspace_id: ws.id,
          name: "Product delivery",
          project_key: "DV" + String(Date.now()).slice(-6),
        }),
      })
    ).json();
    for (let i = 0; i < 8; i++)
      await fetch(
        "http://127.0.0.1:8775/api/v1/project-management/projects/" +
          project.id +
          "/tasks",
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            title: [
              "Finalize launch checklist",
              "Review customer feedback",
              "Prepare release notes",
              "Verify mobile navigation",
              "Publish API documentation",
              "Review team estimates",
              "Resolve integration issue",
              "Schedule launch review",
            ][i],
            task_key: "DV-" + i,
            status: i < 3 ? "Done" : i < 6 ? "In Progress" : "To Do",
            estimated_hours: 3,
            due_date: "2026-10-30",
          }),
        },
      );
    const catalog = await (
      await fetch(
        "http://127.0.0.1:8775/api/v1/project-management/dashboards/catalog",
        { headers },
      )
    ).json();
    d = await (
      await fetch(
        "http://127.0.0.1:8775/api/v1/project-management/dashboards",
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            workspace_id: ws.id,
            name: "Project delivery overview",
            description:
              "Track projects, tasks, and team progress in one clear view.",
            configuration: catalog.templates[0].configuration,
          }),
        },
      )
    ).json();
    fs.writeFileSync(
      "docs/ui-v2/dashboard-qa-fixture.json",
      JSON.stringify(
        { dashboard: d.id, workspace: ws.id, project: project.id },
        null,
        2,
      ),
    );
  }
  const browser = await chromium.launch();
  const results = [];
  for (const theme of ["light", "dark"])
    for (const width of [1672, 820, 390]) {
      const context = await browser.newContext({
        viewport: { width, height: 1050 },
        reducedMotion: "reduce",
      });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(
        "http://127.0.0.1:5191/__suite-ui-qa.html?theme=" +
          theme +
          "&path=" +
          encodeURIComponent("/pms/dashboards?dashboard=" + d.id),
      );
      await page
        .getByRole("button", { name: "View records for Total Tasks" })
        .waitFor();
      await page.waitForTimeout(500);
      await page.getByRole("heading", { level: 1 }).scrollIntoViewIfNeeded();
      const axe = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      results.push({
        theme,
        width,
        errors,
        overflow: await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth + 1,
        ),
        overlappingWidgets: await page
          .locator(".db-widget")
          .evaluateAll((nodes) => {
            const boxes = nodes.map((n) => n.getBoundingClientRect());
            return boxes.some((a, i) =>
              boxes.some(
                (b, j) =>
                  j > i &&
                  Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 &&
                  Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2,
              ),
            );
          }),
        violations: axe.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
      });
      await page.screenshot({
        path: `docs/ui-v2/dashboard-${theme}-${width}.png`,
        fullPage: true,
        animations: "disabled",
      });
      console.log(theme, width, JSON.stringify(results.at(-1)));
      await context.close();
    }
  await browser.close();
  fs.writeFileSync(
    "docs/ui-v2/dashboard-accessibility.json",
    JSON.stringify(results, null, 2),
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
