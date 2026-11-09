const { chromium, expect } = require('playwright/test');
(async () => {
 const browser = await chromium.launch();
 const errors = [];
 try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
  page.on('pageerror', error => errors.push(error.message));
  const base = 'http://localhost:5174/universal-workspaces-qa.html';
  for (const module of ['pms', 'crm', 'hrms', 'srm', 'fam']) {
   await page.goto(`${base}?module=${module}`);
   const region = page.getByRole('region', { name: 'Workspace list', exact: true });
   await expect(region.locator('article')).toHaveCount(3);
   await page.getByRole('button', { name: 'Actions for Client delivery', exact: true }).click();
   await page.getByRole('button', { name: 'Workspace settings', exact: true }).click();
   const dialog = page.getByRole('dialog');
   await expect(dialog).toBeVisible();
   const title = `${module.toUpperCase()} delivery team`;
   await dialog.getByRole('textbox', { name: 'Workspace name', exact: true }).fill(title);
   await dialog.getByRole('textbox', { name: 'Description', exact: true }).fill(`Focused ${module} operations`);
   await dialog.getByRole('textbox', { name: 'Search workspace icons' }).fill(module === 'fam' ? 'finance' : 'team');
   await dialog.getByRole('button', { name: module === 'fam' ? 'Use Finance icon' : 'Use Teams icon', exact: true }).click();
   await dialog.getByRole('button', { name: 'Use accent #168354' }).click();
   if (module !== 'pms') {
    await dialog.getByRole('combobox', { name: 'Add workspace member' }).selectOption('992');
    await dialog.getByRole('combobox', { name: 'Role for member 992' }).selectOption('Guest');
   }
   await dialog.getByRole('button', { name: 'Save workspace', exact: true }).click();
   await expect(dialog).toHaveCount(0);
   await expect(region.getByRole('heading', { name: title, exact: true })).toBeVisible();
   await page.getByRole('combobox', { name: 'Workspace access filter' }).selectOption('mine');
   await expect(region.locator('article')).toHaveCount(1);
   await page.getByRole('combobox', { name: 'Workspace access filter' }).selectOption('all');
   await page.getByRole('combobox', { name: 'Sort workspaces' }).selectOption('updated');
   await expect(region.locator('article').first().getByRole('heading', { name: title })).toBeVisible();
   await page.getByRole('button', { name: `Actions for ${title}` }).click();
   await page.getByRole('button', { name: 'Archive workspace', exact: true }).click();
   await dialog.getByRole('button', { name: 'Archive workspace', exact: true }).click();
   await expect(region.locator('article')).toHaveCount(2);
   await page.getByRole('combobox', { name: 'Workspace status' }).selectOption('Archived');
   await expect(region.locator('article')).toHaveCount(1);
   await page.getByRole('button', { name: `Actions for ${title}` }).click();
   await page.getByRole('button', { name: 'Restore workspace', exact: true }).click();
   await dialog.getByRole('button', { name: 'Restore workspace', exact: true }).click();
   await expect(region.locator('article')).toHaveCount(0);
   await page.getByRole('combobox', { name: 'Workspace status' }).selectOption('Active');
   await expect(region.locator('article')).toHaveCount(3);
   await page.getByRole('button', { name: `Actions for ${title}` }).click();
   await page.getByRole('link', { name: 'Workspace overview', exact: true }).click();
   await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
   await expect(page.getByRole('region', { name: 'Workspace tools' })).toBeVisible();
   await page.getByRole('button', { name: 'Team & access', exact: true }).click();
   if (module !== 'pms') await expect(page.getByText('Guest', { exact: true })).toBeVisible();
   else await expect(page.getByText('qa@example.test', { exact: true }).first()).toBeVisible();
   await page.getByRole('button', { name: 'Activity', exact: true }).click();
   await expect(page.getByRole('region', { name: 'Recent workspace activity' })).toContainText(title);
   await page.getByRole('button', { name: 'Overview', exact: true }).click();
   await page.screenshot({ path: `../outputs/workspace-completed-${module}.png`, fullPage: true });
   await page.getByRole('button', { name: 'All workspaces', exact: true }).click();
   await expect(region.locator('article')).toHaveCount(3);
  }
  for (const module of ['pms', 'crm', 'hrms', 'srm', 'fam']) {
   await page.goto(`${base}?module=${module}&smart`);
   await page.getByRole('link', { name: 'New workspace shortcut' }).click();
   const dialog = page.getByRole('dialog');
   await expect(dialog).toHaveCount(1);
   await dialog.getByRole('textbox', { name: 'Workspace name', exact: true }).fill(`${module} shortcut space`);
   await dialog.getByRole('button', { name: 'Create workspace', exact: false }).last().click();
   await expect(dialog).toHaveCount(0);
   await expect(page.getByRole('region', { name: 'Workspace list', exact: true }).locator('article')).toHaveCount(4);
  }
  await page.goto(`${base}?module=crm&intent`);
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.goto(`${base}?module=crm&no-branch`);
  await expect(page.getByRole('region', { name: 'Workspace list', exact: true }).locator('article')).toHaveCount(3);
  for (const width of [320, 390, 768]) {
   await page.setViewportSize({ width, height: 844 });
   await page.goto(`${base}?module=crm&frame`);
   await page.getByRole('button', { name: 'Create Workspace', exact: true }).click();
   const dialog = page.getByRole('dialog');
   await expect(dialog.getByRole('button', { name: 'Create Workspace', exact: true })).toBeVisible();
   if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) throw Error(`Overflow at ${width}`);
   if (width === 390) await page.screenshot({ path: '../outputs/workspace-editor-mobile.png', fullPage: true });
   await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  }
  if (errors.length) throw Error(errors.join('; '));
  console.log('PASS: all five workspace settings, metadata/icons/colors, members, ownership filters, updated sorting, archive/restore, detail tools/team/activity, and responsive editor.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
