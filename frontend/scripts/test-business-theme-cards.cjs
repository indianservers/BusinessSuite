const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium, expect } = require('playwright/test');

(async () => {
  const root = path.resolve(__dirname, '..'), fixture = path.join(root, 'scripts/.business-theme-cards-fixture.tsx');
  const packs = [['hospital', 'Hospital', true], ['salon', 'Salon', true], ['restaurant', 'Restaurant', false], ['pharma', 'Pharma', false], ['retail', 'Retail', false], ['construction', 'Construction', true], ['accounting_firm', 'Accounting Firm', true]]
    .map(([key, label, ready]) => ({ key, label, activation_ready: ready, isolation_ready: ready, ui_integrated: ready, workflows: [{ label: 'Existing shared workflows' }] }));
  fs.writeFileSync(fixture, `import React from 'react';import{createRoot}from'react-dom/client';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import BusinessThemeCards from'@/pages/settings/BusinessThemeCards';import{useAuthStore}from'@/store/authStore';import'@/index.css';sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'component-fixture',user:{id:1,email:'fixture@example.test',role:'admin',is_superuser:false,access:{companyId:1,managed:false,grants:{}}}});const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={cache}><main className="p-4"><BusinessThemeCards scope="fixture-company-1" companyId={1} catalog={${JSON.stringify(packs)}}/></main></QueryClientProvider>);`);
  const { createServer } = await import('vite');
  const server = await createServer({ root, server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  let browser, page, failure = null, hold = false, release;
  const state = { active: 'general', multiple: false, revision: 1 }, posts = [], errors = [];
  const snapshot = () => ({ company_id: 1, active_key: state.active, multiple_active: state.multiple, selection_revision: state.revision.toString(16).padStart(64, '0'), terminology: { business_type: state.active || 'general', terms: { customer: ['Customer', 'Customers'] } } });
  try {
    await server.listen(); browser = await chromium.launch();
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.pathname === '/api/v1/access/settings/business-packs/theme') {
        if (request.method() === 'GET') return route.fulfill({ json: snapshot() });
        const body = request.postDataJSON(); posts.push(body);
        assert.equal(body.reason, `Activate ${body.pack_key === 'general' ? 'General' : packs.find(pack => pack.key === body.pack_key).label} Business Pack`);
        assert.equal(body.expected_selection, snapshot().selection_revision);
        if (hold) await new Promise(resolve => { release = resolve; });
        if (failure) { const status = failure; failure = null; return route.fulfill({ status, json: { detail: status === 409 ? 'Selection changed on the server.' : 'Required native modules are unavailable.' } }); }
        state.active = body.pack_key; state.multiple = false; state.revision++;
        return route.fulfill({ json: { ...snapshot(), activation_id: state.active === 'general' ? null : 41 } });
      }
      if (url.pathname === '/api/v1/access/me') return route.fulfill({ json: { companyId: 1, managed: false, grants: {} } });
      throw new Error('Unexpected component-fixture API ' + url.pathname);
    });
    await page.route('**/qa-business-theme-cards', route => route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.business-theme-cards-fixture.tsx');</script>` }));
    await page.goto(server.resolvedUrls.local[0] + 'qa-business-theme-cards');
    const active = label => page.getByRole('button', { name: `Active ${label} Business Pack`, exact: true });
    const activate = label => page.getByRole('button', { name: `Activate ${label} Business Pack`, exact: true });
    const activeButtons = () => page.getByRole('button', { name: /^Active .* Business Pack$/ });
    await expect(active('General')).toBeDisabled(); await expect(activeButtons()).toHaveCount(1);
    await expect(activate('Retail')).toBeDisabled();
    hold = true; await activate('Construction').click(); await expect.poll(() => posts.length).toBe(1);
    await expect(active('General')).toBeVisible(); assert.equal(await active('Construction').count(), 0, 'no optimistic Active badge');
    await activate('Salon').evaluate(button => button.click()); assert.equal(posts.length, 1, 'duplicate activation stays blocked');
    hold = false; release();
    await expect(active('Construction')).toBeDisabled(); await expect(activate('Salon')).toBeEnabled();
    await activate('Salon').click(); await expect(active('Salon')).toBeDisabled(); await expect(activeButtons()).toHaveCount(1);
    failure = 422; await activate('General').click(); await expect(page.getByRole('alert')).toContainText('Required native modules'); await expect(active('Salon')).toBeDisabled();
    failure = 409; await activate('Construction').click();
    await expect(page.getByText('The company selection changed. Reload the Business Pack and review it before activating.', { exact: true })).toBeVisible();
    await expect(active('Salon')).toBeVisible(); await expect(activate('Construction')).toBeDisabled();
    state.active = 'construction'; state.revision++; await page.getByRole('button', { name: 'Reload Business Pack', exact: true }).click();
    await expect(active('Construction')).toBeVisible(); await expect(activate('Salon')).toBeEnabled();
    state.active = null; state.multiple = true; state.revision++; await page.getByRole('button', { name: 'Reload Business Pack', exact: true }).click();
    await expect(page.getByText(/Several legacy packs are active/)).toBeVisible(); await expect(activeButtons()).toHaveCount(0);
    await activate('General').click(); await expect(active('General')).toBeDisabled();
    await page.screenshot({ path: path.resolve(root, '../.local/business-theme-cards-desktop.png'), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    await page.setViewportSize({ width: 390, height: 1000 }); await page.reload();
    await expect(active('General')).toBeDisabled(); await activate('Salon').click(); await expect(active('Salon')).toBeDisabled();
    await expect(activeButtons()).toHaveCount(1); await expect(activate('Retail')).toBeDisabled();
    await page.screenshot({ path: path.resolve(root, '../.local/business-theme-cards-mobile.png'), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false); assert.deepEqual(errors, []);
    fs.writeFileSync(path.resolve(root, '../.local/business-theme-cards-fixture-proof.json'), JSON.stringify({ fixture_only: true, backend_authorization_proven: false, checks: ['General default', 'single active A to B', 'server receipt only', 'duplicate blocked', 'failure preserves active', '409 requires reload', 'legacy multiple has no Active badge', 'General restoration', 'mobile activation', 'reload persistence', 'Upcoming disabled', 'desktop/mobile no overflow'], posts, js_errors: errors }, null, 2));
    console.log('PASS actual BusinessThemeCards component fixture: General, exclusive A→B, CAS, failure, 409/reload, legacy ambiguity, Upcoming, persistence, desktop/mobile. Mocked HTTP proves frontend behavior only.');
  } catch (error) { console.error(JSON.stringify({ errors, posts, body: page ? (await page.locator('body').innerText()).slice(0, 6000) : null })); throw error; }
  finally { if (browser) await browser.close(); await server.close(); fs.rmSync(fixture, { force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
