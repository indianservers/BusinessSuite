const { chromium } = require("../node_modules/playwright"),
  fs = require("fs"),
  path = require("path");
(async () => {
  const root = path.resolve(__dirname, "../.."),
    dir = path.join(root, "docs/ui-v2");
  const fixture = JSON.parse(
    fs.readFileSync(path.join(dir, "qa-fixture.json"), "utf8"),
  );
  const b = await chromium.launch();
  const results = [];
  try {
    for (const theme of ["light", "dark"])
      for (const [size, width, height] of [
        ["desktop", 1440, 1000],
        ["tablet", 820, 1000],
        ["mobile", 375, 812],
      ]) {
        const context = await b.newContext({ viewport: { width, height } });
        const page = await context.newPage();
        for (const route of [
          "/",
          "/pms",
          "/pms/profile",
          "/pms/projects",
          "/crm",
          "/srm",
          "/fam",
          "/hrms",
          "/analytics",
          "/admin/security",
          "/ai/copilot",
        ]) {
          const errors = [];
          const listener = (e) => errors.push(e.message);
          page.on("pageerror", listener);
          await page.goto(
            "http://127.0.0.1:5191/__suite-ui-qa.html?theme=" +
              theme +
              "&path=" +
              encodeURIComponent(
                route === "/pms"
                  ? `/pms?workspace=${fixture.workspace}`
                  : route,
              ),
          );
          await page
            .locator("h1")
            .first()
            .waitFor({ state: "visible", timeout: 15000 });
          await page.waitForTimeout(1200);
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          );
          const image =
            (route === "/" ? "suite" : route.slice(1).replaceAll("/", "-")) +
            "-" +
            theme +
            "-" +
            size +
            ".png";
          await page.screenshot({ path: path.join(dir, image) });
          results.push({
            route,
            theme,
            size,
            width,
            overflow,
            errors,
            screenshot: image,
          });
          page.off("pageerror", listener);
        }
        await context.close();
        console.log("Checked", theme, size);
      }
  } finally {
    await b.close();
    fs.writeFileSync(
      path.join(dir, "responsive-smoke.json"),
      JSON.stringify(results, null, 2),
    );
    console.log(
      JSON.stringify(results.filter((r) => r.overflow || r.errors.length)),
    );
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
