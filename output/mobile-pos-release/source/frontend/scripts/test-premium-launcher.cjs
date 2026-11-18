const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const base = process.env.LAUNCHER_QA_URL || 'http://127.0.0.1:5273';
const output = path.resolve(__dirname, '../../.tmp/premium-launcher');
const banner = { image: '/images/suite-office-hero.webp', mobile_image: '', x: 70, y: 50, mobile_x: 75, mobile_y: 50, zoom: 1, overlay: '#eeedff', opacity: .15 };
const option = { id: 'appearance', title: 'Homepage Banner', group: 'Appearance', description: 'Manage your company banner.', destination: null, scope: 'organization', editable: true };
const access = { companyId: 1, companyName: 'Acme Workspace', organizations: [{ id: 1, name: 'Acme Workspace' }], memberships: [1], managed: false, grants: {}, modules: [], isAccessAdmin: true, isGlobalAdmin: true };

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1672, height: 941 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    let saved = { ...banner };
    await page.route('**/api/v1/**', async route => {
      const url = new URL(route.request().url());
      const pathname = url.pathname.replace('/api/v1', '');
      let data = {};
      if (pathname === '/access/homepage-banner/upload') data = { image: 'asset:1-' + 'a'.repeat(64) };
      else if (pathname.startsWith('/auth/homepage-banner/assets/')) { await route.fulfill({ body: fs.readFileSync(path.resolve(__dirname, '../public/images/suite-office-hero.webp')), contentType: 'image/webp' }); return; }
      else if (pathname === '/auth/homepage-banner') data = banner;
      else if (pathname === '/access/homepage-banner') {
        if (route.request().method() === 'PUT') saved = route.request().postDataJSON();
        data = saved;
      } else if (pathname === '/access/settings') data = { companyId: 1, companyName: 'Acme Workspace', options: [option] };
      else if (pathname === '/access/settings/appearance') data = option;
      else if (pathname === '/access/me') data = access;
      else if (pathname === '/branches/context') data = { company_id: 1, selected: null, branches: [], all_branches: true, manage_access: false };
      else if (pathname === '/auth/me') data = { id: 1, email: 'admin@example.com', role: 'super_admin', is_superuser: true, access };
      else if (pathname.includes('/notifications/summary')) data = { groups: [] };
      else if (pathname === '/auth/branding') data = { company_name: 'Acme Workspace' };
      else if (pathname.includes('/notifications')) data = { items: [], pages: 0, unread_count: 0 };
      await route.fulfill({ json: data });
    });
    await page.goto(base);
    await page.locator('.launcher-card').last().waitFor();
    assert.equal(await page.locator('.launcher-card').count(), 6);
    const cards = await page.locator('.launcher-card').evaluateAll(nodes => nodes.map(n => ({ x: n.offsetLeft, y: n.offsetTop, h: n.offsetHeight })));
    assert.equal(cards[0].y, cards[2].y);
    assert.equal(cards[3].y, cards[5].y);
    assert(cards[3].y > cards[0].y);
    assert(cards.every(c => c.h >= 185 && c.h <= 215));
    assert((await page.locator('.launcher-settings').boundingBox()).y < 941);
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    for (const width of [1920, 1440, 1280, 1024, 768, 390, 360]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.waitForTimeout(80);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Horizontal overflow at ${width}`);
      const positions = await page.locator('.launcher-card').evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect().y));
      assert.equal(positions[0], positions[width >= 1440 ? 2 : 1], `Grid columns at ${width}`);
      if (width === 390) await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 1672, height: 941 });
    for (const zoom of [.8, 1, 1.25]) {
      await page.evaluate(value => { document.documentElement.style.zoom = String(value); }, zoom);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at zoom ${zoom}`);
    }
    await page.evaluate(() => { document.documentElement.style.zoom = ''; });
    await page.keyboard.press('Control+k');
    assert(await page.getByRole('combobox', { name: 'Search applications' }).evaluate(n => n === document.activeElement));
    await page.getByRole('combobox', { name: 'Search applications' }).fill('payroll');
    assert.equal(await page.locator('.launcher-card').count(), 1);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.launcher-search-results').count(), 0);
    await page.getByRole('combobox', { name: 'Search applications' }).fill('no such app');
    await page.getByRole('button', { name: 'Show all applications' }).click();
    assert.equal(await page.locator('.launcher-card').count(), 6);
    assert.equal(await page.locator('.launcher-card-link').first().getAttribute('href'), '/login?next=%2Fpower-apps');
    await page.getByRole('combobox', { name: 'Search applications' }).fill('payroll');
    await page.keyboard.press('Enter');
    await page.waitForURL('**/login?next=%2Fhrms');

    await page.evaluate(value => sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: 'qa-only', refreshToken: 'qa-only', user: { id: 1, email: 'admin@example.com', name: 'Admin', role: 'super_admin', is_superuser: true, access: value }, isAuthenticated: true }, version: 0 })), access);
    await page.goto(`${base}/settings/appearance`);
    await page.getByRole('button', { name: 'Save banner' }).waitFor().catch(async error => { console.log(await page.locator('body').innerText()); throw error; });
    await page.getByLabel('Image zoom').fill('1.5');
    await page.getByLabel('Horizontal position').fill('25');
    await page.getByLabel('Image alignment').selectOption('right');
    const crop = await page.locator('.banner-crop').boundingBox();
    await page.mouse.move(crop.x + 150, crop.y + 80);
    await page.mouse.down(); await page.mouse.move(crop.x + 220, crop.y + 90); await page.mouse.up();
    assert(Number(await page.getByLabel('Horizontal position').inputValue()) < 100);
    await page.locator('input[type=file]').setInputFiles(path.resolve(__dirname, '../public/images/suite-office-hero.webp'));
    await page.getByRole('button', { name: 'Save banner' }).waitFor();
    await page.waitForFunction(() => document.querySelector('.banner-crop img')?.src.startsWith('blob:'));

    await page.getByRole('button', { name: 'Save banner' }).click();
    await page.getByRole('status').filter({ hasText: 'Homepage banner saved' }).waitFor();
    assert.equal(saved.zoom, 1.5);
    assert(saved.image.startsWith('asset:'));
    await page.reload();
    await page.getByRole('button', { name: 'Save banner' }).waitFor();
    assert.equal(await page.getByLabel('Image zoom').inputValue(), '1.5');
    await page.getByRole('button', { name: 'Mobile', exact: true }).click();
    assert.equal(await page.locator('.banner-crop-mobile').count(), 1);
    await page.screenshot({ path: path.join(output, 'appearance.png'), fullPage: true });
    await page.getByRole('button', { name: 'Desktop', exact: true }).click();
    await page.getByRole('button', { name: 'Remove image', exact: true }).click();
    assert.equal(await page.locator('.banner-crop img').count(), 0);
    await page.getByRole('button', { name: 'Reset to default' }).click();
    await page.getByRole('button', { name: 'Save banner' }).click();
    await page.getByRole('status').filter({ hasText: 'Homepage banner saved' }).waitFor();
    assert.equal(saved.zoom, 1);
    await page.goto(`${base}/dashboard`);
    await page.locator('.launcher-card').last().waitFor();
    assert.equal(await page.locator('.launcher-card-link').first().getAttribute('href'), '/power-apps');
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Passed: desktop/tablet/mobile layouts, zoom, search keyboard controls, launch links, authenticated dashboard, banner preview/save/reload/reset.');
    console.log(`Screenshots: ${output}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
