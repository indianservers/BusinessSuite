const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium, expect: raw } = require('playwright/test');
const expect = raw.configure({ timeout: 15000 });
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const { createServer } = await import('vite');
  const server = await createServer({ server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage(), writes = [], errors = [];
    let fail = true, hold = false, release;
    const profile = () => ({ userId: 101, displayName: 'Complete Person', loginEmail: 'person@example.test', kind: 'employee', accountActive: true,
      values: { first_name: 'Original', personal_email: 'person@example.test', phone_number: '9876543210', phone_number_country_code: '+91', skills: ['React'], education: [], experience: [] },
      version: 'original-v1', completeness: 50, missingFields: ['present_address'], canEdit: true, canManage: false, requiresApprovalFields: ['first_name'], documents: [], pendingRequests: [], employment: { department: 'Original department' } });
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), u = new URL(req.url());
      if (req.method() !== 'GET') {
        writes.push({ path: u.pathname, method: req.method(), body: req.postDataJSON() });
        if (hold) await new Promise(resolve => release = resolve);
        if (fail) return route.fulfill({ status: 403, json: { detail: 'Profile update denied; your draft is retained.' } });
        return route.fulfill({ json: { profile: { ...profile(), values: { ...profile().values, ...req.postDataJSON().values }, version: 'saved-v2' }, message: 'Saved complete profile' } });
      }
      if (u.pathname.endsWith('/profiles/directory')) return route.fulfill({ json: { items: [{ userId: 101, displayName: 'Complete Person', email: 'person@example.test', employeeCode: 'EMP-101', kind: 'employee', active: true }], total: 1 } });
      await route.fulfill({ json: profile() });
    });
    await page.route('**/profile-editor-qa', route => route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-profile-management.tsx");</script>' }));
    const url = `http://127.0.0.1:${server.httpServer.address().port}/profile-editor-qa`;
    const detail = () => page.locator('.up-management-detail');
    const select = async (group, section) => {
      await detail().getByRole('tab', { name: group, exact: true }).click();
      await detail().getByRole('combobox', { name: 'Profile sections section', exact: true }).selectOption(section);
    };
    const fields = {
      Personal: ['First name', 'Middle name', 'Last name', 'Preferred name', 'Gender', 'Date of birth', 'Marital status', 'Parent / guardian name', 'About me'],
      Contact: ['Personal email', 'Phone', 'Current address', 'City', 'State', 'Postal code', 'Country', 'Permanent address', 'Permanent city', 'Permanent state', 'Permanent postal code', 'Emergency contact name', 'Emergency phone', 'Emergency contact relationship'],
      Academic: ['Degree', 'College / institution', 'Specialization', 'Current academic year', 'Pass-out year', '10th marks (%)', '12th marks (%)'],
      Professional: ['Areas of interest', 'Skills', 'Languages', 'Role applied for', 'Preferred work mode', 'Available from', 'Internship duration', 'LinkedIn', 'GitHub', 'Portfolio', 'Time zone', 'Language / locale'],
    };
    for (const width of [320, 360, 375, 390, 414, 430, 480]) {
      await page.setViewportSize({ width, height: 900 }); await page.goto(url);
      await page.locator('.up-directory > button').click(); await detail().getByRole('button', { name: 'Edit profile', exact: true }).click();
      for (const [section, labels] of Object.entries(fields)) {
        await select(['Personal', 'Contact'].includes(section) ? 'Personal' : 'Career', section);
        for (const label of labels) {
          const input = detail().getByLabel(label === 'First name' ? /^First name/ : label, { exact: label !== 'First name' });
          await expect(input).toBeVisible();
          assert.equal(await input.evaluate(e => getComputedStyle(e).fontSize), '16px', `${width} ${label}`);
          assert.ok((await input.boundingBox()).height >= 44, `${width} ${label}`);
        }
        if (section === 'Contact') {
          const trigger = detail().getByRole('button', { name: /^Phone country calling code:/ });
          await trigger.click();
          const search = detail().getByRole('combobox', { name: 'Search phone country', exact: true });
          await expect(search).toBeFocused();
          assert.equal(await search.evaluate(e => getComputedStyle(e).fontSize), '16px');
          assert.ok((await search.boundingBox()).height >= 44);
          await search.fill('no-such-country');
          await expect(detail().getByRole('status').filter({ hasText: 'No countries found' })).toBeVisible();
          await search.press('Escape'); await expect(trigger).toBeFocused();
          await expect(trigger).toHaveAttribute('aria-expanded', 'false');
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width} ${section} overflow`);
      }
      await select('Career', 'Education'); await detail().getByRole('button', { name: 'Add qualification', exact: true }).click();
      for (const label of ['Qualification', 'Institution', 'Specialization', 'Board / university', 'Pass-out year', 'Marks / CGPA']) await expect(detail().getByLabel(label, { exact: true })).toBeVisible();
      await detail().getByLabel('Qualification', { exact: true }).fill('Degree retained');
      await detail().getByRole('button', { name: 'Add qualification', exact: true }).click();
      await detail().locator('.up-collection article').last().getByRole('button', { name: 'Remove', exact: true }).click();
      await expect(detail().getByLabel('Qualification', { exact: true })).toHaveValue('Degree retained');
      await select('Career', 'Experience'); await detail().getByRole('button', { name: 'Add experience', exact: true }).click();
      for (const label of ['Company', 'Job title', 'Start date', 'End date', 'Responsibilities']) await expect(detail().getByLabel(label, { exact: true })).toBeVisible();
      await detail().getByLabel('End date', { exact: true }).fill('2025-01-01');
      await detail().getByLabel('I currently work here', { exact: true }).check();
      await expect(detail().getByLabel('End date', { exact: true })).toHaveValue('');
      await select('Career', 'Education'); await expect(detail().getByLabel('Qualification', { exact: true })).toHaveValue('Degree retained');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await page.setViewportSize({ width: 390, height: 900 }); await page.goto(url);
    await page.locator('.up-directory > button').click(); await detail().getByRole('button', { name: 'Edit profile', exact: true }).click();
    await select('Personal', 'Contact');
    await detail().getByLabel('Personal email', { exact: true }).fill('invalid-email');
    await detail().getByRole('button', { name: 'Save profile', exact: true }).click();
    assert.equal(writes.length, 0, 'Native email validation must prevent PATCH');
    await detail().getByLabel('Personal email', { exact: true }).fill('changed@example.test');
    await detail().getByLabel('Current address', { exact: true }).fill('Full preserved address');
    await detail().getByRole('button', { name: 'Save profile', exact: true }).click();
    const alert = detail().getByRole('alert'); await expect(alert).toContainText('Profile update denied');
    await expect(detail().getByLabel('Current address', { exact: true })).toHaveValue('Full preserved address');
    await expect(alert).toBeInViewport();
    await expect(alert).toBeFocused();
    await require('node:fs/promises').mkdir(path.resolve(__dirname, '../../outputs/mobile-ux'), { recursive: true });
    await page.screenshot({ path: path.resolve(__dirname, '../../outputs/mobile-ux/profile-editor-error-390.png') });
    // The original PhoneInput fills the missing optional emergency country code.
    assert.deepEqual(writes[0], { path: '/api/v1/profiles/users/101', method: 'PATCH', body: { values: { personal_email: 'changed@example.test', present_address: 'Full preserved address', emergency_contact_number_country_code: '+91' }, version: 'original-v1', reason: 'Updated from complete profile' } });
    fail = false; hold = true;
    await detail().getByRole('button', { name: 'Save profile', exact: true }).click();
    await expect.poll(() => typeof release).toBe('function');
    await expect(detail().getByLabel('Current address', { exact: true })).toBeDisabled();
    await expect(detail().getByRole('button', { name: 'Saving…', exact: true })).toBeDisabled();
    await expect(detail().getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled();
    assert.equal(writes.length, 2);
    assert.deepEqual(writes[1], writes[0]); hold = false; release();
    await expect(detail().getByRole('button', { name: 'Edit profile', exact: true })).toBeVisible();
    await expect(detail().getByRole('status').filter({ hasText: 'Saved complete profile' })).toBeVisible();
    assert.deepEqual(errors, []);
    console.log('PASS seven-phone complete profile field/collection access and drafts;390 native email validation, original PATCH diff/version/reason, visible/focused failure, retained retry and pending locks/success. Writes mocked.');
  } finally { await browser.close(); await server.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
