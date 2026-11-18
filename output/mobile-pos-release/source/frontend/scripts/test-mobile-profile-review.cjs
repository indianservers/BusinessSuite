const path = require('node:path'), fs = require('node:fs/promises'), cp = require('node:child_process'), assert = require('node:assert/strict');
const { chromium, expect: raw } = require('playwright/test'); const expect = raw.configure({ timeout: 15000 });
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const out = path.resolve(__dirname, '../../outputs/mobile-ux'); await fs.mkdir(out, { recursive: true });
  const baseline = process.env.PROFILE_REVIEW_BASELINE;
  const scratch = path.resolve(__dirname, 'fixtures/review-profile-before.tsx'), fixture = path.resolve(__dirname, 'fixtures/review-fixture-before.tsx');
  if (baseline) {
    let source = cp.execFileSync('git', ['show', 'a1b4de4d44cf297098ee9c2be81132d102f6b04a:frontend/src/features/profiles/UnifiedProfile.tsx'], { encoding: 'utf8' });
    for (const [from, to] of [['../../components/PhoneActions', '@/components/PhoneActions'], ['../../components/forms/CompactForm', '@/components/forms/CompactForm'], ['../../lib/validation/PhoneInput', '@/lib/validation/PhoneInput'], ['./profiles.css', '@/features/profiles/profiles.css']]) source = source.replace(from, to);
    await fs.writeFile(scratch, source); await fs.writeFile(fixture, (await fs.readFile(path.resolve(__dirname, 'fixtures/mobile-profile-management.tsx'), 'utf8')).replace('@/features/profiles/UnifiedProfile', './review-profile-before'));
  } else { try { await fs.access(path.join(out, 'profile-review-desktop-before.json')); } catch { cp.execFileSync(process.execPath, [__filename], { stdio: 'inherit', env: { ...process.env, PROFILE_REVIEW_BASELINE: '1' } }); } }
  const { createServer } = await import('vite'); const server = await createServer({ server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } }); await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage(), errors = [], writes = [], reads = [];
    let allowed = true, fail = true, hold = false, release, resolved = new Set();
    const long = 'CompleteRequestedValue0123456789'.repeat(16);
    const changes = () => [{ id: 501, status: 'Pending', reason: 'Complete first request reason', values: { first_name: 'Requested complete name', custom_long_field: long, education: [{ degree: 'Complete qualification', institution: long }] } }, { id: 502, status: 'Pending', reason: 'Complete second request reason', values: { bio: long } }].filter(c => !resolved.has(c.id));
    const profile = () => ({ userId: 101, displayName: 'Complete Person', loginEmail: 'person@example.test', kind: 'employee', accountActive: true, values: { first_name: 'Original', skills: [], education: [], experience: [] }, version: 'v1', completeness: 50, missingFields: [], canEdit: true, canManage: false, canReview: allowed, requiresApprovalFields: ['first_name'], documents: [], pendingRequests: changes() });
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), url = new URL(req.url());
      if (req.method() !== 'GET') {
        writes.push({ path: url.pathname, method: req.method(), body: req.postDataJSON() });
        if (hold) await new Promise(resolve => release = resolve);
        if (fail) return route.fulfill({ status: 403, json: { detail: 'Review failed; retain your remarks and retry.' } });
        resolved.add(Number(url.pathname.split('/').at(-2))); return route.fulfill({ json: {} });
      }
      reads.push(url.pathname);
      if (url.pathname.endsWith('/profiles/directory')) return route.fulfill({ json: { items: [101, 102].map(userId => ({ userId, displayName: 'Complete Person ' + userId, email: 'person@example.test', kind: 'employee', active: true })), total: 2 } });
      await route.fulfill({ json: profile() });
    });
    await page.route('**/profile-review-qa', route => route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/' + (baseline ? 'review-fixture-before' : 'mobile-profile-management') + '.tsx");</script>' }));
    const url = `http://127.0.0.1:${server.httpServer.address().port}/profile-review-qa`;
    const records = () => page.locator('.up-pending'), first = () => records().first();
    const remarks = record => record.getByRole('textbox', { name: 'Review remarks (optional)', exact: true });
    const selectPending = async () => { await page.getByRole('tab', { name: 'Overview', exact: true }).click(); await page.getByRole('combobox', { name: 'Profile sections section', exact: true }).selectOption('Pending changes'); };
    const go = async width => { resolved.clear(); await page.setViewportSize({ width, height: 900 }); await page.goto(url); await page.locator('.up-directory > button').first().click(); await selectPending(); await expect(records()).toHaveCount(2); };
    const rects = () => records().evaluateAll(nodes => nodes.map(e => [e, ...e.querySelectorAll('*')].map(n => { const r = n.getBoundingClientRect(), s = getComputedStyle(n); return [n.tagName, r.width, r.height, s.fontSize, s.padding, s.display]; })));
    if (baseline) { const geometry = {}; for (const width of [481, 768, 1024, 1440]) { await go(width); geometry[width] = await rects(); } await fs.writeFile(path.join(out, 'profile-review-desktop-before.json'), JSON.stringify(geometry)); await go(390); assert.ok(await first().locator('dd').evaluateAll(nodes => nodes.some(e => e.scrollHeight > e.clientHeight)), 'Original long values require nested scrolling'); await first().scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(out, 'profile-review-before-390.png') }); console.log('Captured original profile review baseline'); return; }
    for (const width of [320, 360, 375, 390, 414, 430, 480]) {
      await go(width); await expect(first()).toContainText('Request #501 · Pending'); await expect(first()).toContainText('Complete first request reason'); await expect(first()).toContainText('custom_long_field'); await expect(first()).toContainText(long); await expect(first()).toContainText(JSON.stringify(changes()[0].values.education));
      await expect(remarks(first())).toBeVisible(); assert.equal(await remarks(first()).evaluate(e => getComputedStyle(e).fontSize), '16px');
      const expanded = first().locator('.up-review-value'); await expect(expanded).toHaveCount(2);
      for (const field of await expanded.all()) { const summary=field.locator('summary'); assert.ok((await summary.boundingBox()).height>=44); await summary.focus(); await summary.press('Enter'); await expect(field).toHaveAttribute('open',''); await expect(field.locator('div')).toBeVisible(); }
      assert.ok(await first().locator('dd').evaluateAll(nodes => nodes.every(e => e.scrollWidth <= e.clientWidth)), 'Long requested values must wrap');
      for (const field of await expanded.all()) await field.locator('summary').click();
      const approve = first().getByRole('button', { name: 'Approve changes', exact: true }), reject = first().getByRole('button', { name: 'Reject changes', exact: true });
      const a = await approve.boundingBox(), b = await reject.boundingBox(); assert.ok(a.height >= 44 && b.height >= 44); assert.equal(a.y, b.y, 'Paired phone decisions');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await remarks(first()).fill('Retained first remarks'); await remarks(records().last()).fill('Retained second remarks');
      const beforeTabs = reads.length; await page.getByRole('tab', { name: 'Career', exact: true }).click(); await selectPending(); await expect(remarks(first())).toHaveValue('Retained first remarks'); assert.equal(reads.length, beforeTabs);
      await page.getByRole('button', { name: 'All profiles', exact: true }).click();
      const event = page.waitForEvent('dialog'); const click = page.locator('.up-directory > button').last().click(); await (await event).dismiss(); await click;
      await page.getByRole('button', { name: 'Continue editing profile', exact: true }).click(); await expect(remarks(first())).toHaveValue('Retained first remarks');
      const beforeResize=reads.length; await page.setViewportSize({width:768,height:900});
      const resizedGuard=page.waitForEvent('dialog'); const resizedSelection=page.locator('.up-directory > button').last().click(); await (await resizedGuard).dismiss(); await resizedSelection;
      await page.setViewportSize({width,height:900}); await expect(remarks(first())).toHaveValue('Retained first remarks'); assert.equal(reads.length,beforeResize);
    }
    assert.ok(await page.evaluate(() => { const event=new Event('beforeunload',{cancelable:true}); window.dispatchEvent(event); return event.defaultPrevented; }), 'Review remarks retain the existing unload safeguard');
    await page.getByRole('button', { name: 'All profiles', exact: true }).click();
    const discard=page.waitForEvent('dialog'); const changePerson=page.locator('.up-directory > button').last().click(); await (await discard).accept(); await changePerson; await selectPending();
    await expect(remarks(first())).toHaveValue(''); await expect(remarks(records().last())).toHaveValue(''); assert.equal(writes.length,0);
    await go(390); await remarks(first()).fill('  Original raw review remarks  '); await remarks(records().last()).fill('Other request draft');
    await first().getByRole('button', { name: 'Approve changes', exact: true }).click(); await expect(first().getByRole('alert')).toContainText('Review failed'); await expect(first().getByRole('alert')).toBeFocused();
    await expect(remarks(first())).toHaveValue('  Original raw review remarks  '); assert.deepEqual(writes[0], { path: '/api/v1/hrms/profile-change-requests/501/approve', method: 'POST', body: { remarks: '  Original raw review remarks  ', applyChanges: true } });
    await page.screenshot({ path: path.join(out, 'profile-review-error-390.png') });
    fail = false; hold = true; await first().getByRole('button', { name: 'Approve changes', exact: true }).click(); await expect.poll(() => typeof release).toBe('function');
    await expect(remarks(first())).toBeDisabled(); await expect(records().last().getByRole('button', { name: 'Reject changes', exact: true })).toBeDisabled(); await expect(page.getByRole('button', { name: 'All profiles', exact: true })).toBeDisabled();
    assert.equal(writes.length, 2); assert.deepEqual(writes[1], writes[0]); hold = false; release();
    await expect(records()).toHaveCount(1); await expect(remarks(first())).toHaveValue('Other request draft');
    await expect(page.getByRole('heading', { name: 'Changes awaiting HR review', exact: true })).toBeFocused();
    fail = true; await remarks(first()).fill('Raw rejection remarks'); await first().getByRole('button', { name: 'Reject changes', exact: true }).click();
    await expect(first().getByRole('alert')).toContainText('Review failed'); await expect(remarks(first())).toHaveValue('Raw rejection remarks');
    assert.deepEqual(writes.at(-1), { path: '/api/v1/hrms/profile-change-requests/502/reject', method: 'POST', body: { remarks: 'Raw rejection remarks', applyChanges: true } });
    fail = false; await remarks(first()).fill('');
    await first().getByRole('button', { name: 'Reject changes', exact: true }).click(); await expect(records()).toHaveCount(0);
    assert.deepEqual(writes.at(-1), { path: '/api/v1/hrms/profile-change-requests/502/reject', method: 'POST', body: { remarks: '', applyChanges: true } });
    await expect(page.getByRole('status').filter({ hasText: 'No changes awaiting HR review.' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Changes awaiting HR review', exact: true })).toBeFocused();
    allowed = false; await go(390); await expect(first()).toContainText(long); await expect(first().getByRole('button')).toHaveCount(0); await expect(remarks(first())).toHaveCount(0); allowed = true;
    const geometry = JSON.parse(await fs.readFile(path.join(out, 'profile-review-desktop-before.json'), 'utf8'));
    for (const width of [481, 768, 1024, 1440]) { await go(width); assert.deepEqual(await rects(), geometry[width], 'Original desktop review geometry ' + width); await expect(remarks(first())).toHaveCount(0); }
    const previousWrites = writes.length; let prompt = page.waitForEvent('dialog'); let clicked = first().getByRole('button', { name: 'Approve changes', exact: true }).click(); await (await prompt).dismiss(); await clicked; assert.equal(writes.length, previousWrites);
    prompt = page.waitForEvent('dialog'); clicked = first().getByRole('button', { name: 'Approve changes', exact: true }).click(); await (await prompt).accept('desktop raw remarks'); await clicked; await expect.poll(() => writes.length).toBe(previousWrites + 1); assert.deepEqual(writes.at(-1).body, { remarks: 'desktop raw remarks', applyChanges: true });
    assert.deepEqual(errors, []); console.log('PASS review seven phones full values/wrapping/paired decisions/remarks/tab-list drafts/dirty guard;390 local403/raw payload/retry/pending/refetch/other draft/blank rejection/readonly;4desktop original geometry/native prompt. Writes mocked.');
  } finally { await browser.close(); await server.close(); if (baseline) { await fs.rm(scratch, { force: true }); await fs.rm(fixture, { force: true }); } }
})().catch(e => { console.error(e); process.exitCode = 1; });
