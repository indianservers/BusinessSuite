const assert = require("node:assert/strict"),
  { build } = require("esbuild"),
  { chromium } = require("playwright"),
  path = require("node:path");
(async () => {
  const root = path.resolve(__dirname, "..");
  const built = await build({
    stdin: {
      contents: `import {api} from './src/services/api';import {progress,getOperations} from './src/lib/async-progress';import {setProgressContext} from './src/lib/progress-context';import {CanceledError} from 'axios';window.api=api;window.progress=progress;window.state=getOperations;setProgressContext({title:'Employee Records',module:'HRMS'});window.pending={};api.defaults.adapter=config=>new Promise((resolve,reject)=>{window.pending[config.url]={config,resolve:()=>resolve({data:{id:1},status:200,statusText:'OK',headers:{},config}),reject:()=>reject({config,response:{status:500,data:{detail:'Service unavailable'}},message:'Service unavailable'})};config.signal?.addEventListener('abort',()=>reject(new CanceledError('Cancelled',config)));});`,
      resolveDir: root,
      loader: "ts",
    },
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    alias: { "@": path.join(root, "src") },
    define: { "import.meta.env": "{}" },
  });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.route("http://api-progress.test/**", (r) =>
      r.fulfill({ contentType: "text/html", body: "<div/>" }),
    );
    await page.goto("http://api-progress.test");
    await page.addScriptTag({ content: built.outputFiles[0].text });
    await page.evaluate(() => {
      window.result = "";
      void window.api
        .post(
          "/fixture/upload",
          {},
          {
            progress: {
              id: "upload",
              title: "Uploading Attachment",
              operationType: "upload",
              mode: "modal",
            },
          },
        )
        .then(
          () => (window.result = "ok"),
          () => (window.result = "error"),
        );
    });
    await page.waitForFunction(() => window.pending["/fixture/upload"]);
    assert.equal(
      await page.evaluate(() => window.state().active[0].title),
      "Uploading Attachment",
    );
    await page.evaluate(() =>
      window.pending["/fixture/upload"].config.onUploadProgress({
        loaded: 250,
        total: 1000,
      }),
    );
    assert.equal(
      await page.evaluate(() => window.state().active[0].progress),
      25,
    );
    await page.evaluate(() =>
      window.pending["/fixture/upload"].config.onUploadProgress({
        loaded: 1000,
        total: 1000,
      }),
    );
    assert.equal(
      await page.evaluate(() => window.state().active[0].progress),
      undefined,
    );
    assert.equal(
      await page.evaluate(() => window.state().active[0].status),
      "running",
    );
    await page.evaluate(() => window.pending["/fixture/upload"].resolve());
    await page.waitForFunction(() => window.result === "ok");
    assert.equal(await page.evaluate(() => window.state().active.length), 0);
    assert.equal(
      await page.evaluate(() => window.state().settled[0].status),
      "success",
    );
    await page.evaluate(() => window.progress.dismiss("upload"));
    for (const config of [
      { progress: false },
      { _recordSyncBackground: true },
    ]) {
      await page.evaluate((c) => {
        void window.api.get("/fixture/silent", c).catch(() => {});
      }, config);
      await page.waitForTimeout(20);
      assert.equal(await page.evaluate(() => window.state().active.length), 0);
      await page.evaluate(() => window.pending["/fixture/silent"].resolve());
    }
    await page.evaluate(() => {
      void window.api.post("/fixture/save", {}).catch(() => {});
    });
    await page.waitForFunction(() => window.pending["/fixture/save"]);
    assert.equal(
      await page.evaluate(() => window.state().active[0].title),
      "Saving Employee Records",
    );
    await page.evaluate(() => window.pending["/fixture/save"].reject());
    await page.waitForFunction(() => window.state().active.length === 0);
    await page.evaluate(() => {
      window.controller = new AbortController();
      void window.api
        .get("/fixture/cancel", {
          signal: window.controller.signal,
          progress: {
            id: "cancel",
            title: "Loading Contacts",
            mode: "modal",
            cancellable: true,
            onCancel: () => window.controller.abort(),
          },
        })
        .catch(() => {});
    });
    await page.waitForFunction(() => window.pending["/fixture/cancel"]);
    await page.evaluate(() => window.progress.cancel("cancel"));
    assert.equal(
      await page.evaluate(() => window.controller.signal.aborted),
      true,
    );
    assert.equal(await page.evaluate(() => window.state().active.length), 0);
    assert.equal(await page.evaluate(() => window.state().settled.length), 0);
    console.log(
      "PASS: API metadata, real byte counts, indeterminate server confirmation, silent refresh, failure cleanup, AbortController cancellation",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
