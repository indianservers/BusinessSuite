const { chromium } = require("playwright"),
  assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    let release,
      fail = false;
    let hold = new Promise((r) => (release = r));
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let body = { items: [], pages: 1, total: 0 };
      if (path.endsWith("/custom-fields")) {
        await hold;
        if (fail)
          return route.fulfill({
            status: 500,
            json: { detail: "Custom fields unavailable" },
          });
      }
      if (path.endsWith("/permissions"))
        body = { can_manual_probability: false };
      if (path.endsWith("/pipelines"))
        body = { items: [{ id: 1, name: "Sales", is_default: true }] };
      if (path.endsWith("/pipeline-stages"))
        body = {
          items: [
            { id: 1, pipeline_id: 1, name: "Qualification", probability: 20 },
          ],
        };
      if (path.endsWith("/1/record"))
        body = {
          id: 1,
          name: "Existing Opportunity",
          pipeline_id: 1,
          stage_id: 1,
          amount: 123,
          currency: "INR",
          probability: 20,
          status: "Open",
          related: {},
          planning: {},
        };
      await route.fulfill({ json: body }).catch(() => {});
    });
    await page.goto(
      (process.env.PROGRESS_QA_ORIGIN || "http://localhost:5174") +
        "/progress-deal-qa.html",
    );
    await page.getByRole("button", { name: "Start new deal" }).click();
    await page
      .getByRole("heading", { name: "Preparing New Deal", exact: true })
      .waitFor();
    assert.equal(
      await page.locator(".smart-progress-track").getAttribute("aria-valuenow"),
      null,
    );
    assert.equal(
      await page.getByRole("button", { name: "Run in background" }).count(),
      0,
    );
    release();
    await page
      .getByRole("dialog", { name: "Create deal", exact: true })
      .waitFor();
    assert.equal(await page.locator(".smart-progress-dialog").count(), 0);
    await page
      .getByRole("button", { name: "Close deal form", exact: true })
      .click();
    hold = new Promise((r) => (release = r));
    await page.getByRole("button", { name: "Edit existing deal" }).click();
    await page
      .getByRole("heading", { name: "Loading Deal Details", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    assert.equal(await page.locator(".smart-progress-dialog").count(), 0);
    release();
    await page.waitForTimeout(100);
    assert.equal(
      await page
        .getByRole("dialog", { name: "Edit deal", exact: true })
        .count(),
      0,
    );
    fail = true;
    hold = Promise.resolve();
    await page.getByRole("button", { name: "Start new deal" }).click();
    await page
      .getByRole("heading", { name: "Unable to Load Deal Form" })
      .waitFor();
    fail = false;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await page
      .getByRole("dialog", { name: "Create deal", exact: true })
      .waitFor();
    assert.equal(await page.locator(".smart-progress-dialog").count(), 0);
    assert.deepEqual(errors, []);
    console.log(
      "PASS: actual deal create/edit loaders, indeterminate stages, cancellation without stale form, failure/retry recovery, no orphan overlay",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
