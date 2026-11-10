// Exercise the rendered application menus against a running frontend and API.
// Default credentials belong only to the disposable suite-navigation QA server.
const { chromium, expect: baseExpect } = require('../frontend/node_modules/playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const expect = baseExpect.configure({ timeout: 30000 });
const origin = process.env.MENU_QA_ORIGIN || 'http://127.0.0.1:5187';
const output = path.resolve(process.env.MENU_QA_OUTPUT || '.local/menu-release/browser');
const modules = ['hrms', 'crm', 'pms', 'srm', 'fam', 'power-apps'];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch();
  const results = [], errors = [];
  try {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    if (process.env.MENU_QA_SESSION_FILE) {
      const session = JSON.parse(fs.readFileSync(process.env.MENU_QA_SESSION_FILE));
      await context.addInitScript(s => {
        if (!sessionStorage.getItem('hrms-auth')) sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: s.token, isAuthenticated: true, user: s.user }, version: 0 }));
      }, session);
    }
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 1000 });
    if (!process.env.MENU_QA_SESSION_FILE) {
      assert(origin.startsWith('http://127.0.0.1:'), 'Live checks require a private revocable session');
      await page.goto(origin + '/login');
      await page.getByLabel('Email address', { exact: true }).fill('admin@suiteqa.example.com');
      await page.getByLabel('Password', { exact: true }).fill('SuiteQA@12345');
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
      await page.getByRole('button', { name: 'Indian Servers (Default)', exact: true }).click();
      await expect(page).not.toHaveURL(/\/login|\/continue/);
    }
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
      for (const module of modules) {
        console.log('CHECK', width, module);
        await page.goto(origin + '/' + module);
        const menu = page.locator(`.module-menu[data-module="${module}"]`).last();
        await expect(menu).toBeAttached();
        if (module !== 'power-apps' && width < 1024 && !await menu.isVisible()) {
          const trigger = page.getByRole('button', { name: /open (navigation|sidebar)|toggle (navigation|sidebar)|show navigation/i }).first();
          await trigger.click();
        }
        await expect(menu).toBeVisible();
        await expect(menu.locator('.module-menu-heading').first()).toBeVisible();
        await expect(menu.locator('.module-menu-category-name', { hasText: /^Settings & administration$/ })).toBeVisible();
        const search = menu.getByRole('textbox', { name: 'Find a page in this application' });
        await expect(search).toBeVisible();
        await menu.getByRole('button', { name: 'Expand all menu categories', exact: true }).click();
        while (await menu.locator('.module-menu-subtoggle[aria-expanded="false"]').count()) await menu.locator('.module-menu-subtoggle[aria-expanded="false"]').first().click();
        const categories = await menu.locator('.module-menu-category-name').allTextContents();
        assert.equal(new Set(categories).size, categories.length, 'Repeated category');
        const links = await menu.locator('.module-menu-landing a, .module-menu-categories a').evaluateAll(elements => elements.map(el => ({ label: el.textContent.trim(), href: el.getAttribute('href') })));
        assert(links.length > 3, 'Empty application catalog');
        const destinations = links.map(link => link.href);
        assert.equal(new Set(destinations).size, destinations.length, 'Repeated menu destination: ' + JSON.stringify(links.filter((link, i) => destinations.indexOf(link.href) !== i)));
        const settings = menu.locator('.module-menu-category').filter({ has: page.locator('.module-menu-category-name', { hasText: /^Settings & administration$/ }) });
        await expect(settings).toHaveCount(1);
        const settingsLinks = await settings.locator('a').evaluateAll(elements => elements.map(el => ({ label: el.textContent.trim(), href: el.getAttribute('href') })));
        assert(settingsLinks.length > 0, 'Missing module settings');
        if (module !== 'power-apps') assert(settingsLinks.some(link => link.href.split('?')[0] === `/${module}/settings`), 'Missing settings entry');
        const overflowing = await menu.evaluate(el => ({ width: el.clientWidth, scroll: el.scrollWidth }));
        assert(overflowing.scroll <= overflowing.width + 1, 'Menu horizontal overflow: ' + JSON.stringify(overflowing));
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Page horizontal overflow');
        await search.fill('settings');
        await expect(menu.locator('.module-menu-categories a').first()).toBeVisible();
        await search.fill('zz-no-such-page');
        await expect(menu.getByText('No pages found', { exact: true })).toBeVisible();
        await search.fill('');
        await menu.getByRole('button', { name: 'Collapse all menu categories', exact: true }).click();
        await expect(menu.locator('.module-menu-heading[aria-expanded="true"]')).toHaveCount(0);
        await settings.getByRole('button', { name: /Settings & administration/ }).click();
        await expect(settings.locator('a').first()).toBeVisible();
        await menu.screenshot({ path: path.join(output, `${module}-${width}.png`) });
        if (module !== 'power-apps') {
          const entry = settings.locator(`a[href="/${module}/settings"]`);
          await entry.click();
          await expect(page).toHaveURL(new RegExp(`/${module}/settings(?:[?#].*)?$`));
          if (module === 'hrms') {
            await expect(page.getByRole('heading', { name: 'HR settings', exact: true })).toBeVisible();
            await page.getByRole('link', { name: /^Departments/ }).click();
            await expect(page).toHaveURL(/\/hrms\/settings\/departments$/);
            await expect(page.getByRole('link', { name: 'Back to HR settings', exact: true })).toBeVisible();
          }
        }
        results.push({ module, width, categories, links, settingsLinks, subcategories: await menu.locator('.module-menu-subtoggle').count() });
        console.log('PASS', module, width, categories.length, 'categories;', links.length, 'unique links');
      }
    }
    assert.deepEqual(errors, [], 'Browser runtime errors');
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({ origin, results, errors }, null, 2));
  } catch (error) {
    console.error(error);
    for (const context of browser.contexts()) for (const page of context.pages()) {
      await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
      console.log('Failure URL:', new URL(page.url()).pathname);
      console.log('Buttons:', await page.getByRole('button').allTextContents().catch(() => []));
    }
    throw error;
  } finally { await browser.close(); }
})().catch(() => { process.exitCode = 1; });
