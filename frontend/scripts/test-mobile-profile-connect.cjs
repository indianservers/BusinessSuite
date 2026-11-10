const path = require('node:path'), fs = require('node:fs/promises'), cp = require('node:child_process');
const assert = require('node:assert/strict');
const { chromium, expect: raw } = require('playwright/test');
const expect = raw.configure({ timeout: 15000 });
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const out = path.resolve(__dirname, '../../outputs/mobile-ux'); await fs.mkdir(out, { recursive: true });
  const baseline = process.env.PROFILE_CONNECT_BASELINE;
  const sourcePath = path.resolve(__dirname, 'fixtures/connect-profile-before.tsx');
  const fixturePath = path.resolve(__dirname, 'fixtures/connect-fixture-before.tsx');
  if (baseline) {
    let source = cp.execFileSync('git', ['show', 'a1b4de4d44cf297098ee9c2be81132d102f6b04a:frontend/src/features/profiles/UnifiedProfile.tsx'], { encoding: 'utf8' });
    for (const [from, to] of [['../../components/PhoneActions', '@/components/PhoneActions'], ['../../components/forms/CompactForm', '@/components/forms/CompactForm'], ['../../lib/validation/PhoneInput', '@/lib/validation/PhoneInput'], ['./profiles.css', '@/features/profiles/profiles.css']]) source = source.replace(from, to);
    await fs.writeFile(sourcePath, source);
    await fs.writeFile(fixturePath, (await fs.readFile(path.resolve(__dirname, 'fixtures/mobile-profile-management.tsx'), 'utf8')).replace('@/features/profiles/UnifiedProfile', './connect-profile-before'));
  } else {
    try { await fs.access(path.join(out, 'profile-connect-desktop-before.json')); }
    catch { cp.execFileSync(process.execPath, [__filename], { stdio: 'inherit', env: { ...process.env, PROFILE_CONNECT_BASELINE: '1' } }); }
  }
  const { createServer } = await import('vite');
  const server = await createServer({ server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } }); await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage(), writes = [], errors = [], reads = [];
    let denied = true, empty = false, allowed = true, hold = false, release;
    const profile = connected => ({ userId: 101, displayName: 'Complete Person', loginEmail: 'person@example.test', kind: 'employee', accountActive: true,
      values: { first_name: 'Original', skills: [], education: [], experience: [] }, version: 'original-v1', completeness: 50, missingFields: [], canEdit: true, canManage: allowed, requiresApprovalFields: [], documents: [], pendingRequests: [], employment: { department: connected ? 'Connected department' : 'Original department' } });
    const preview = () => ({ email: 'person@example.test', message: 'Choose the matching employee in your organization.', candidates: empty ? [] : [{ employeeId: 201, name: 'First candidate', employeeCode: 'EMP-201', linked: false }, { employeeId: 202, name: 'Second candidate complete name', employeeCode: 'EMP-202', linked: true }] });
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), u = new URL(req.url());
      if (req.method() !== 'GET') {
        writes.push({ path: u.pathname, method: req.method(), body: req.postDataJSON() });
        if (hold) await new Promise(resolve => release = resolve);
        if (denied) return route.fulfill({ status: 403, json: { detail: 'Connection denied; choose again or retry.' } });
        return route.fulfill({ json: profile(true) });
      }
      reads.push(u.pathname);
      if (u.pathname.endsWith('/profiles/directory')) return route.fulfill({ json: { items: [{ userId: 101, displayName: 'Complete Person', email: 'person@example.test', employeeCode: 'EMP-101', kind: 'employee', active: true }], total: 1 } });
      if (u.pathname.endsWith('/connect-preview')) return route.fulfill({ json: preview() });
      await route.fulfill({ json: profile(false) });
    });
    await page.route('**/profile-connect-qa', route => route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/' + (baseline ? 'connect-fixture-before' : 'mobile-profile-management') + '.tsx");</script>' }));
    const url = `http://127.0.0.1:${server.httpServer.address().port}/profile-connect-qa`;
    const opener = () => page.getByRole('button', { name: 'Connect by email', exact: true });
    const dialog = () => page.getByRole('dialog').last();
    const confirm = () => dialog().getByRole('button', { name: 'Confirm employee connection', exact: true });
    const choose = () => dialog().getByRole('combobox', { name: 'Matching employee', exact: true });
    const go = async width => { await page.setViewportSize({ width, height: 900 }); await page.goto(url); await page.locator('.up-directory > button').click(); await opener().click(); await expect(dialog()).toBeVisible(); };
    const geometry = () => page.locator('dialog.up-connect-dialog').evaluate(e => [e, ...e.querySelectorAll('*')].map(n => { const r = n.getBoundingClientRect(), s = getComputedStyle(n); return [n.tagName, r.x, r.y, r.width, r.height, s.fontSize, s.padding]; }));
    if (baseline) {
      const rects = {}; for (const width of [481, 768, 1024, 1440]) { await go(width); rects[width] = await geometry(); }
      await go(390); await choose().selectOption('202'); await confirm().click();
      await expect(page.locator('.up-error')).toContainText('Connection denied');
      await expect(dialog().getByRole('alert')).toHaveCount(0);
      assert.ok(await dialog().evaluate(e => e.matches(':modal')), 'Original native dialog leaves the error outside its modal layer');
      await page.screenshot({ path: path.join(out, 'profile-connect-before-390.png') });
      await fs.writeFile(path.join(out, 'profile-connect-desktop-before.json'), JSON.stringify(rects)); console.log('Captured original-source connection dialog baseline'); return;
    }
    for (const width of [320, 360, 375, 390, 414, 430, 480]) {
      await go(width);
      await expect(dialog()).toHaveAccessibleName('Connect profile by email');
      await expect(choose()).toHaveValue('201'); await expect(choose().locator('option')).toHaveCount(2);
      await expect(choose().locator('option').last()).toContainText('Second candidate complete name (EMP-202) · already connected');
      assert.equal(await choose().evaluate(e => getComputedStyle(e).fontSize), '16px');
      for (const control of [choose(), confirm(), dialog().getByRole('button', { name: 'Close', exact: true })]) assert.ok((await control.boundingBox()).height >= 44);
      for (const button of await dialog().getByRole('button').all()) assert.ok((await button.boundingBox()).height >= 44, `Phone overlay button ${width}`);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await choose().selectOption('202'); await choose().focus();
      for (let i = 0; i < 8; i++) { await page.keyboard.press('Tab'); assert.ok(await dialog().evaluate(e => e.contains(document.activeElement))); }
      await page.keyboard.press('Escape'); await expect(dialog()).toHaveCount(0); await expect(opener()).toBeFocused();
    }
    await go(390); await choose().selectOption('202'); await confirm().click();
    await expect(dialog().getByRole('alert')).toContainText('Connection denied'); await expect(dialog().getByRole('alert')).toBeFocused(); await expect(dialog().getByRole('alert')).toBeInViewport();
    await expect(choose()).toHaveValue('202'); assert.deepEqual(writes[0], { path: '/api/v1/profiles/users/101/connect-email', method: 'POST', body: { employeeId: 202 } });
    await page.screenshot({ path: path.join(out, 'profile-connect-error-390.png') });
    denied = false; hold = true; await confirm().click(); await expect.poll(() => typeof release).toBe('function');
    await expect(confirm()).toBeDisabled(); await expect(choose()).toBeDisabled();
    await expect(dialog().getByRole('button', { name: 'Close', exact: true })).toBeDisabled();
    await page.keyboard.press('Escape'); await expect(dialog()).toBeVisible();
    await dialog().getByRole('button', { name: 'Drag down or tap to close' }).click(); await expect(dialog()).toBeVisible();
    await dialog().getByRole('button', { name: 'Close dialog', exact: true }).click(); await expect(dialog()).toBeVisible();
    assert.equal(writes.length, 2); assert.deepEqual(writes[1], writes[0]); hold = false; release();
    await expect(dialog()).toHaveCount(0); await expect(opener()).toBeFocused();
    await expect(page.getByRole('status').filter({ hasText: 'Employee and account profiles are connected.' })).toBeVisible();
    await go(390); await choose().selectOption('202'); const beforeResize = reads.length;
    await page.setViewportSize({ width: 768, height: 900 }); await expect(page.locator('dialog.up-connect-dialog')).toBeVisible(); await expect(choose()).toHaveValue('202');
    await page.setViewportSize({ width: 390, height: 900 }); await expect(dialog()).toHaveAccessibleName('Connect profile by email'); await expect(choose()).toHaveValue('202'); assert.equal(reads.length, beforeResize);
    await page.keyboard.press('Escape');
    empty = true; await go(390); await expect(dialog().getByText(/No available employee matches/)).toBeVisible(); await expect(confirm()).toHaveCount(0); await dialog().getByRole('button', { name: 'Close', exact: true }).click();
    empty = false; allowed = false; await page.goto(url); await page.locator('.up-directory > button').click(); await expect(page.getByRole('button', { name: 'Edit profile', exact: true })).toBeVisible(); await expect(opener()).toHaveCount(0); allowed = true;
    const rects = JSON.parse(await fs.readFile(path.join(out, 'profile-connect-desktop-before.json'), 'utf8'));
    for (const width of [481, 768, 1024, 1440]) { await go(width); assert.deepEqual(await geometry(), rects[width], 'Original desktop connection geometry ' + width); }
    assert.deepEqual(errors, []);
    console.log('PASS connection sheet seven phones options/defaults/44px/16px/focus trap/Escape/no overflow;390 denied retry/exact payload/pending dismissal/success/focus/resize/no extra reads/empty/permission;4desktop pinned original dialog geometry. Writes mocked.');
  } finally { await browser.close(); await server.close(); if (baseline) { await fs.rm(sourcePath, { force: true }); await fs.rm(fixturePath, { force: true }); } }
})().catch(e => { console.error(e); process.exitCode = 1; });
