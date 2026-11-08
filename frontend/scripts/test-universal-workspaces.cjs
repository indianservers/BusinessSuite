const { chromium, expect } = require('playwright/test');
const path = require('node:path');
(async () => {
 const browser = await chromium.launch();
 const errors = [];
 try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('pageerror', error => errors.push(error.message));
  const base = 'http://localhost:5174/universal-workspaces-qa.html';
  await page.goto(base);
  await expect(page.getByRole('heading', { name: 'Workspaces', exact: true })).toBeVisible();
  const region = page.getByRole('region', { name: 'Workspace list', exact: true });
  await expect(region.locator('article')).toHaveCount(3);
  await expect(region.getByRole('progressbar', { name: 'Client delivery task completion' })).toHaveAttribute('value', '16');
  await page.getByRole('button', { name: 'Actions for Client delivery', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Client delivery actions' }).getByRole('link', { name: 'View projects' })).toHaveAttribute('href', '/pms/projects?workspace=101');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Favorite Client delivery', exact: true }).click();
  await page.getByRole('button', { name: 'Favorites (1)', exact: true }).click();
  await expect(region.locator('article')).toHaveCount(1);
  await page.getByRole('button', { name: 'All (3)', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search workspaces', exact: true }).fill('engineering');
  await expect(region.locator('article')).toHaveCount(1);
  await page.getByRole('textbox', { name: 'Search workspaces', exact: true }).fill('');
  await page.getByRole('button', { name: 'List view', exact: true }).click();
  await expect(region.getByRole('table')).toBeVisible();
  await page.reload();
  await expect(region.getByRole('table')).toBeVisible();
  await page.getByRole('button', { name: 'Grid view', exact: true }).click();
  await page.getByRole('button', { name: 'Create Workspace', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('textbox', { name: 'Workspace name' }).fill('Customer implementation');
  await dialog.getByRole('button', { name: 'Create Workspace', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(region.locator('article')).toHaveCount(4);
  await page.getByRole('button', { name: 'Open workspace switcher' }).click();
  await expect(page.getByRole('heading', { name: 'Favorites', exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Search available workspaces' }).fill('engineering');
  await expect(page.locator('.wd-switcher-options a')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await page.screenshot({ path: path.join(__dirname, '../../outputs/universal-workspaces-desktop.png'), fullPage: true });
  await page.evaluate(() => {
   window.__workspaceQaDeny = true;
   window.dispatchEvent(new CustomEvent('suite:record-saved', { detail: { url: '/project-management/workspaces', method: 'post' } }));
  });
  await expect(page.getByRole('alert')).toContainText('You do not have access');
  await expect(region.locator('article')).toHaveCount(0);
  const titles = { crm: 'Sales & Customer Workspaces', hrms: 'People Workspaces', srm: 'Sales & Operations Workspaces', fam: 'Finance & Accounting Workspaces' };
  for (const [module, title] of Object.entries(titles)) {
   await page.goto(`${base}?module=${module}`);
   await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
   await expect(region.locator('article')).toHaveCount(6);
   const summaryLabels = { crm: 'Open deals', hrms: 'Employees in scope', srm: 'Sales orders · all time', fam: 'Financial year' };
   await expect(page.getByRole('region', { name: 'Workspace summary' })).toContainText(summaryLabels[module]);
   if (module === 'fam') await expect(page.getByRole('region', { name: 'Workspace summary' })).toContainText('FY 2026–27');
   await expect(region.locator('progress')).toHaveCount(0);
   await page.getByRole('button', { name: 'List view', exact: true }).click();
   await expect(region.getByRole('table')).toBeVisible();
   await page.getByRole('button', { name: 'Grid view', exact: true }).click();
   await page.screenshot({ path: path.join(__dirname, `../../outputs/universal-workspaces-${module}.png`), fullPage: true });
  }
  await page.evaluate(() => {
   window.__workspaceQaDeny = true;
   window.dispatchEvent(new CustomEvent('suite:record-saved', { detail: { url: '/fam/journal', method: 'post' } }));
  });
  await expect(page.getByRole('button', { name: 'Retry summary' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Workspace summary' })).not.toContainText('Financial year');
  for (const width of [320, 390, 768]) {
   await page.setViewportSize({ width, height: 844 });
   await page.goto(`${base}?frame`);
   await expect(region.locator('article')).toHaveCount(3);
   if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) throw Error(`Page overflows at ${width}px`);
   await page.getByRole('button', { name: 'Create Workspace', exact: true }).click();
   await expect(dialog).toBeVisible();
   await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
   if (width === 390) await page.screenshot({ path: path.join(__dirname, '../../outputs/universal-workspaces-mobile.png'), fullPage: true });
  }
  await page.goto(`${base}?user=992`);
  await expect(page.getByRole('button', { name: 'Favorites (0)', exact: true })).toBeVisible();
  await page.goto(`${base}?branch=2`);
  await expect(page.getByRole('button', { name: 'Favorites (0)', exact: true })).toBeVisible();
  await page.goto(`${base}?module=crm&missing-metrics`);
  await expect(page.getByRole('region', { name: 'Workspace summary' })).not.toContainText('Open deals');
  await page.goto(`${base}?module=fam&error`);
  await expect(page.getByRole('button', { name: 'Retry summary' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Workspace summary' })).not.toContainText('Financial year');
  await page.goto(`${base}?empty`);
  await expect(page.getByRole('heading', { name: 'Your next space starts here' })).toBeVisible();
  await page.goto(`${base}?error`);
  await expect(page.getByRole('alert')).toContainText('You do not have access');
  await expect(page.getByRole('heading', { name: 'Your next space starts here' })).toHaveCount(0);
  await page.goto(`${base}?restricted`);
  await expect(page.getByRole('button', { name: 'Create Workspace', exact: true })).toHaveCount(0);
  if (errors.length) throw Error(errors.join('; '));
  console.log('PASS: all five directories, real-field progress, favorites, search, list persistence, create dialog, switcher, account/branch isolation, access revocation, missing metrics, empty/error/restricted states, 320/390/768px layouts; no page errors.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
