const { chromium } = require("../node_modules/playwright"),
  fs = require("fs"),
  path = require("path");
const root = path.resolve(__dirname, "../.."),
  dir = path.join(root, "docs/ui-v2");
(async () => {
  const inventory = JSON.parse(
    fs.readFileSync(path.join(dir, "route-coverage.json"), "utf8"),
  );
  const fixture = JSON.parse(
    fs.readFileSync(path.join(dir, "qa-fixture.json"), "utf8"),
  );
  const browser = await chromium.launch();
  const results = [];
  const pending = inventory.routes;
  const representatives = new Set([
    "/",
    "/pms",
    "/pms/profile",
    "/pms/projects",
    "/pms/overview",
    "/crm",
    "/srm",
    "/fam",
    "/hrms",
    "/pms/teams",
    "/analytics",
    "/admin/security",
    "/ai/copilot",
  ]);
  let cursor = 0;
  async function worker() {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    while (cursor < pending.length) {
      const route = pending[cursor++];
      const errors = [],
        failures = [];
      const onError = (e) => errors.push(e.message);
      const onResponse = (r) => {
        if (r.status() >= 500)
          failures.push({
            status: r.status(),
            url: r.url().replace(/\?.*/, ""),
          });
      };
      page.on("pageerror", onError);
      page.on("response", onResponse);
      const pathname = route.path
        .replace(/:projectId/g, String(fixture.project))
        .replace(/:taskId/g, "1")
        .replace(/:[a-zA-Z]+/g, "1")
        .replaceAll("*", "__qa_unmatched__");
      let result = {
        path: route.path,
        resolved: pathname,
        dynamic: route.dynamic,
      };
      try {
        await page.goto(
          "http://127.0.0.1:5191/__suite-ui-qa.html?path=" +
            encodeURIComponent(
              pathname === "/pms"
                ? `/pms?workspace=${fixture.workspace}`
                : pathname,
            ),
        );
        await page.waitForFunction(
          () =>
            document.body.innerText.trim().length > 20 &&
            !/^Business Suite.*Loading your workspace/s.test(
              document.body.innerText,
            ),
          {},
          { timeout: 12000 },
        );
        await page.waitForTimeout(300);
        const body = await page.locator("body").innerText();
        result = {
          ...result,
          heading: await page
            .locator("h1,h2")
            .first()
            .innerText()
            .catch(() => ""),
          overflow: await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          errors: [...errors],
          serverErrors: [...failures],
          outcome: errors.length
            ? "render-error"
            : /Something went wrong|Unable to load|Failed to load|internal server error/i.test(
                  body,
                )
              ? "error-state"
              : route.dynamic
                ? "fixture-review-needed"
                : "rendered",
        };
        if (representatives.has(route.path)) {
          await page.screenshot({
            path: path.join(
              dir,
              route.path === "/"
                ? "suite-home.png"
                : route.path.slice(1).replaceAll("/", "-") + "-desktop.png",
            ),
          });
        }
      } catch (e) {
        result = {
          ...result,
          outcome: "navigation-error",
          message: e.message,
          errors,
          serverErrors: failures,
        };
      }
      results.push(result);
      page.off("pageerror", onError);
      page.off("response", onResponse);
      if (results.length % 20 === 0) {
        fs.writeFileSync(
          path.join(dir, "route-smoke.json"),
          JSON.stringify(results, null, 2),
        );
        console.log("Checked", results.length, "/", pending.length);
      }
    }
    await page.close();
  }
  try {
    await Promise.all([worker(), worker()]);
  } finally {
    await browser.close();
    fs.writeFileSync(
      path.join(dir, "route-smoke.json"),
      JSON.stringify(results, null, 2),
    );
    console.log(
      JSON.stringify(
        results.reduce(
          (a, r) => ((a[r.outcome] = (a[r.outcome] || 0) + 1), a),
          {},
        ),
      ),
    );
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
