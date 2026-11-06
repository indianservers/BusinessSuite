const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { MemoryRouter } = require('react-router-dom');
const { chromium } = require('playwright');

const source = fs.readFileSync(path.join(__dirname, '../src/components/suite/SetupGuide.tsx'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const exported = {};
new Function('require', 'exports', compiled)(name => name.endsWith('.css') ? {} : require(name), exported);
const Guide = exported.default;
const item = (id, module, ready = false, required = true) => ({ id, module, ready, required, canRepair: true, title: id, description: `Configure ${id}`, destination: `/setup/${id}` });
const data = { items: [item('company', 'company')], moduleItems: [item('workspace', 'project_management'), item('project', 'project_management')], recommendations: [item('custom-fields', 'project_management', false, false)] };
const render = data => renderToStaticMarkup(React.createElement(MemoryRouter, {}, React.createElement(Guide, { data, loading: false, error: false, refreshing: false, refresh() {} })));

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const css = fs.readFileSync(path.join(__dirname, '../src/components/suite/setup-guide.css'), 'utf8');
    await page.setContent(`<style>:root{--border:220 13% 85%;--background:0 0% 100%;--foreground:222 47% 11%;--muted-foreground:215 16% 47%;--primary:250 75% 60%;--muted:220 14% 96%}*{box-sizing:border-box}body{font-family:Arial;margin:0;padding:24px}${css}</style>${render(data)}`);
    const groups = page.locator('details');
    assert.match(await groups.first().innerText(), /Shared essentials/);
    assert.equal(await groups.first().getAttribute('open'), '');
    assert.equal(await groups.nth(1).getAttribute('open'), null);
    await groups.nth(1).locator('summary').click();
    assert.equal(await groups.nth(1).getAttribute('open'), '');
    assert.equal(await page.getByText('Complete Project workspace first.').count(), 1);
    assert.equal(await page.locator('a[href="/setup/project"]').count(), 0);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      const output = path.join(__dirname, '../../outputs/setup-guide');
      fs.mkdirSync(output, { recursive: true });
      await page.screenshot({ path: path.join(output, `guide-${width}.png`), fullPage: true });
    }
    const complete = { ...data, items: data.items.map(i => ({ ...i, ready: true })), moduleItems: data.moduleItems.map(i => ({ ...i, ready: true })) };
    assert.equal(render(complete), '');
    const repaired = render({ ...data, moduleItems: data.moduleItems.map(i => i.id === 'workspace' ? { ...i, ready: true } : i) });
    assert.match(repaired, /href="\/setup\/project"/);
    console.log('Setup guide passed: group order, accordion, prerequisite links, mobile overflow, automatic hiding with recommendations incomplete.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
