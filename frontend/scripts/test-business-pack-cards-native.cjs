const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const { chromium, expect } = require('playwright/test');

(async () => {
  const target = process.env.WORKFLOW_TEST_ORIGIN;
  assert.match(target || '', /^http:\/\/127\.0\.0\.1:\d+$/, 'Use the disposable pytest HTTP server');
  const token = process.env.WORKFLOW_TEST_TOKEN, company = process.env.WORKFLOW_TEST_COMPANY, branch = process.env.WORKFLOW_TEST_BRANCH;
  const headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', 'X-Suite-Organization': company, 'X-Suite-Branch': branch };
  const api = '/api/v1', base = '/access/settings/business-packs';
  async function request(endpoint, { method = 'GET', body, auth = token, status = 200 } = {}) {
    const response = await fetch(target + api + endpoint, { method, headers: { ...headers, Authorization: 'Bearer ' + auth }, body: body ? JSON.stringify(body) : undefined });
    const value = await response.json(); assert.equal(response.status, status, endpoint + ': ' + JSON.stringify(value)); return value;
  }
  const before = await request(base + '/configuration');
  const general = await request(base + '/theme'); assert.equal(general.active_key, 'general');
  const catalog = await request(base + '/catalog');
  assert.deepEqual(catalog.items.filter(item => item.release_status === 'upcoming').map(item => item.key).sort(), ['pharma', 'restaurant', 'retail']);
  await request(base + '/theme', { auth: process.env.WORKFLOW_TEST_ORDINARY_TOKEN, status: 403 });
  await request(base + '/theme', { auth: process.env.WORKFLOW_TEST_ORDINARY_TOKEN, method: 'POST', status: 403, body: { pack_key: 'construction', expected_selection: general.selection_revision, reason: 'Ordinary user activation must be denied' } });
  assert.equal((await request(base + '/theme')).selection_revision, general.selection_revision);
  const identity = await request('/auth/me'), access = await request('/access/me');
  const primary = typeof identity.role === 'string' ? identity.role : identity.role?.name || 'employee';
  const user = { ...identity, role: primary, primary_role: primary, access };
  const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};sessionStorage.setItem('suite-organization',${JSON.stringify(company)});sessionStorage.setItem('suite-branch',${JSON.stringify(branch)});</script><script type="module">import React from'react';import{createRoot}from'react-dom/client';import{BrowserRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Settings from'/src/pages/settings/BusinessPacksSettings.tsx';import{useAuthStore}from'/src/store/authStore.ts';import'/src/index.css';useAuthStore.setState({accessToken:${JSON.stringify(token)},isAuthenticated:true,isHydrated:true,user:${JSON.stringify(user)}});createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},React.createElement(BrowserRouter,null,React.createElement('main',{className:'p-4'},React.createElement(Settings)))));</script></body></html>`;
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), appType: 'custom', cacheDir: process.env.WORKFLOW_TEST_CACHE,
    server: { host: '127.0.0.1', port: 0, hmr: false, watch: null, proxy: { '/api': { target, changeOrigin: true } } },
    plugins: [{ name: 'native-business-pack-cards', configureServer(vite) { vite.middlewares.use(async (req, res, next) => { if (!req.url.startsWith('/__business-pack-cards.html')) return next(); try { res.setHeader('Content-Type', 'text/html'); res.end(await vite.transformIndexHtml(req.url, html)); } catch (error) { next(error); } }); } }],
  });
  const trace = [], errors = [], selections = []; let browser, page;
  const active = label => page.getByRole('button', { name: `Active ${label} Business Pack`, exact: true });
  async function verify(key) {
    const selection = await request(base + '/theme'), effective = await request('/access/settings/business-profile/effective');
    const config = await request(base + '/configuration');
    assert.equal(selection.active_key, key); assert.equal(selection.multiple_active, false);
    assert.deepEqual(effective.terms, selection.terminology.terms, 'Actual effective terminology follows the selected pack');
    assert.equal(effective.business_type, key);
    assert.deepEqual(config.activations.filter(row => row.state === 'active').map(row => row.pack_key), key === 'general' ? [] : [key]);
    assert.deepEqual(config.contexts, before.contexts); assert.deepEqual(config.grants, before.grants);
    selections.push({ key, selection_revision: selection.selection_revision, business_type: effective.business_type, terms: effective.terms });
  }
  try {
    await server.listen(); browser = await chromium.launch(); page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { const url = new URL(response.url()); if (url.pathname.startsWith('/api/')) trace.push({ method: response.request().method(), path: url.pathname, status: response.status() }); });
    await page.goto('http://127.0.0.1:' + server.httpServer.address().port + '/__business-pack-cards.html');
    await expect(active('General')).toBeDisabled(); await verify('general');
    await page.getByText('Configure branch access / advanced setup', { exact: true }).click();
    await expect(page.getByLabel('Business Pack', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Pack branch', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Pack access & shared masters', exact: true })).toBeVisible();
    await page.getByText('Configure branch access / advanced setup', { exact: true }).click();
    for (const [key, width] of [['construction', 1440], ['salon', 390], ['general', 390]]) {
      const label = key === 'general' ? 'General' : catalog.items.find(item => item.key === key).label;
      await page.setViewportSize({ width, height: 1000 });
      await page.getByRole('button', { name: `Activate ${label} Business Pack`, exact: true }).click();
      await expect(active(label)).toBeDisabled(); await verify(key);
      await expect(page.getByRole('button', { name: /^Active .* Business Pack$/ })).toHaveCount(1);
      for (const upcoming of catalog.items.filter(item => item.release_status === 'upcoming')) await expect(page.getByRole('button', { name: `Activate ${upcoming.label} Business Pack`, exact: true })).toBeDisabled();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      await page.screenshot({ path: path.resolve('../.local/business-pack-cards-native-' + key + '.png'), fullPage: true });
    }
    await page.reload(); await expect(active('General')).toBeDisabled(); await verify('general');
    assert.deepEqual(trace.filter(item => item.status >= 400), []); assert.deepEqual(errors, []);
    const proof = { backend: 'actual FastAPI HTTP over disposable fixture DB', mocked_http_responses: false, ordinary_get_post_status: 403, contexts_and_grants_unchanged: true, trace, selections, js_errors: errors };
    fs.writeFileSync(path.resolve('../.local/business-pack-cards-native-proof.json'), JSON.stringify(proof, null, 2));
    console.log('PASS native BusinessPacksSettings: General→Construction→Salon→General, actual terminology, ordinary denial, unchanged contexts/grants, desktop/mobile.');
  } catch (error) { console.error(JSON.stringify({ trace, errors, body: page ? (await page.locator('body').innerText()).slice(0, 6500) : null })); throw error; }
  finally { if (browser) await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
