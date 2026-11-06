import { test, expect, type Page } from '../frontend/node_modules/playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test.skip(!process.env.TEMPLATE_STUDIO_AUTH_FILE, 'Requires an isolated seeded API and auth snapshot.');
async function prepare(page: Page) {
  const auth = JSON.parse(fs.readFileSync(process.env.TEMPLATE_STUDIO_AUTH_FILE!, 'utf8'));
  await page.addInitScript(({ token, user }) => {
    if (window.top !== window) return;
    (window as any).__AI_HRMS_CONFIG__ = { apiBaseUrl: '/api/v1' };
    sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: token, refreshToken: token, user, isAuthenticated: true }, version: 0 }));
  }, auth);
  // Ancillary shell requests are unrelated to the editor. Studio requests use
  // the real isolated API; backend integration tests cover authorization.
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.includes('/template-studio/')) return route.continue();
    const body = pathname.endsWith('/auth/me') ? auth.user : pathname.endsWith('/business-os/modules') ? { enabled_modules: ['crm', 'hrms', 'project_management'] } : pathname.endsWith('/access/me') ? {} : pathname.endsWith('/access/setup') ? { ready: true, items: [] } : { items: [], total: 0 };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

test('design, placeholders, saved email, invoice output and mail merge gallery', async ({ page }, info) => {
  const templateName = `Visual welcome ${info.project.name} ${Date.now()}`;
  await prepare(page);
  const errors: string[] = [];
  page.on('pageerror', e => {
    // Playwright's serviceWorkers:block init script also executes inside the
    // intentionally opaque preview iframe; it cannot read navigator.serviceWorker.
    if (e.message.includes('Service worker is disabled because the context is sandboxed')) return;
    errors.push(e.message);
  });
  await page.goto('/crm/templates');
  await expect(page.getByRole('heading', { name: 'Make every message yours.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create template', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Create template', exact: true }).click();
  await expect(page.locator('.ts-paper')).toContainText('Welcome aboard');
  await page.getByRole('button', { name: 'Select Heading block', exact: true }).dblclick();
  await page.getByLabel('Edit canvas text', { exact: true }).click();
  await page.getByLabel('Edit canvas text', { exact: true }).press('Control+a');
  await page.keyboard.insertText('Welcome, {{name}} — let’s begin');
  await page.getByLabel('Edit canvas text', { exact: true }).press('Control+a');
  await page.getByLabel('Edit canvas text', { exact: true }).press('Control+b');
  await page.getByRole('button', { name: 'Done editing', exact: true }).click();
  await expect(page.locator('.ts-paper')).toContainText('let’s begin');
  await expect(page.locator('.ts-paper strong')).toHaveText('Welcome, {{name}} — let’s begin');
  await page.getByRole('button', { name: 'Placeholders', exact: true }).click();
  await page.getByLabel('Search placeholders').fill('Recipient email');
  await expect(page.locator('.ts-field-list')).toContainText('{{email}}');
  await page.getByLabel('Sample data', { exact: true }).check();
  await expect(page.locator('.ts-paper')).toContainText('Ananya Rao');
  await page.getByLabel('Template name').fill(templateName);
  await page.getByLabel('Template status', { exact: true }).selectOption('ready');
  await page.getByRole('button', { name: 'Save template', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Template saved' })).toBeVisible();
  await page.getByRole('button', { name: 'Publish to email composer', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Published to the email composer' })).toBeVisible();
  await page.getByRole('button', {name:'Elements',exact:true}).click();
  fs.mkdirSync(path.resolve('../outputs/template-studio'), {recursive:true});
  await page.locator('.ts-editor').screenshot({ path: path.resolve(`../outputs/template-studio/email-editor-${info.project.name}.png`) });
  await page.getByRole('button', { name: '← Library', exact: true }).click();
  await expect(page.getByRole('heading', { name: templateName, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: templateName, exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^Business documents/ }).click();
  await expect(page.locator('.ts-preset')).toHaveCount(4);
  await page.getByRole('button', { name: 'Create template', exact: true }).click();
  await page.getByLabel('Template name').fill(`Invoice ${templateName}`);
  await page.getByRole('button', {name:'Save template',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Template saved'})).toBeVisible();
  await page.getByLabel('Sample data', { exact: true }).check();
  await expect(page.locator('.ts-paper')).toContainText('INVOICE');
  await expect(page.locator('.ts-paper')).toContainText('29,500.00');
  await expect(page.getByRole('button', { name: 'Export sample HTML', exact: true })).toBeEnabled();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export sample HTML', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toContain('SAMPLE');
  await page.getByRole('button', {name:'Edit merge values & line items',exact:true}).click();
  const fields = page.locator('.ts-value-grid input');
  for (const input of await fields.all()) await input.fill((await input.getAttribute('placeholder')) || 'Verified value');
  await page.getByRole('button', {name:'Add line item',exact:true}).click();
  await page.getByLabel('Line 1 description',{exact:true}).fill('Verified annual subscription');
  await page.getByLabel('Line 1 quantity',{exact:true}).fill('1');
  await page.getByLabel('Line 1 rate',{exact:true}).fill('25,000.00');
  await page.getByLabel('Line 1 amount',{exact:true}).fill('25,000.00');
  await page.getByRole('button',{name:'Close merge values',exact:true}).click();
  await page.getByLabel('Sample data',{exact:true}).uncheck();
  await expect(page.getByRole('button',{name:'Export HTML',exact:true})).toBeEnabled();
  const invoiceDownload = page.waitForEvent('download');
  await page.getByRole('button',{name:'Export HTML',exact:true}).click();
  const invoiceFile = await (await invoiceDownload).path();
  const invoiceHtml = fs.readFileSync(invoiceFile!, 'utf8');
  expect(invoiceHtml).toContain('Verified annual subscription');
  expect(invoiceHtml).not.toContain('{{');
  await page.locator('.ts-editor').screenshot({ path: path.resolve(`../outputs/template-studio/invoice-editor-${info.project.name}.png`) });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.getByRole('button', { name: '← Library', exact: true }).click();
  await page.getByRole('button', { name: /^Mail merge/ }).click();
  await expect(page.locator('.ts-preset')).toHaveCount(5);
  await page.getByRole('button', { name: 'Create template', exact: true }).click();
  await expect(page.locator('.ts-paper')).toContainText('A letter to');
  await page.getByLabel('Template name').fill(`Letter ${templateName}`);
  await page.getByRole('button',{name:'Edit merge values & line items',exact:true}).click();
  for (const input of await page.locator('.ts-value-grid input').all()) await input.fill((await input.getAttribute('placeholder')) || 'Verified value');
  await page.getByRole('button',{name:'Close merge values',exact:true}).click();
  await page.getByRole('button', { name: 'Save template', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Template saved' })).toBeVisible();
  await page.getByLabel('Asha template preview', { exact: true }).check();
  await page.getByRole('button', { name: 'Generate personalized copies', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Created 1 personalized previews' })).toBeVisible();
  await expect(page.frameLocator('iframe[title="Template preview"]').getByText('A letter to Asha template preview')).toBeVisible();
  const mergedDownload = page.waitForEvent('download');
  await page.getByRole('button',{name:'Export complete merged copies',exact:true}).click();
  const mergedFile = await (await mergedDownload).path();
  const mergedHtml = fs.readFileSync(mergedFile!, 'utf8');
  expect(mergedHtml).toContain('Asha template preview');
  expect(mergedHtml).not.toContain('{{');
  expect(errors).toEqual([]);
});


test('expanded CRM gallery filters and all designs render through the API', async ({page}, info) => {
  test.skip(info.project.name !== 'desktop', 'Catalog contract is independent of viewport.');
  await prepare(page);
  await page.goto('/crm/templates');
  const gallery = page.getByRole('region', {name:'Email template gallery'});
  await expect(gallery.locator('article')).toHaveCount(72);
  await gallery.getByRole('button',{name:'Leads 11',exact:true}).click();
  await expect(gallery.locator('article')).toHaveCount(11);
  await gallery.getByLabel('Filter gallery category').selectOption('Celebration');
  await expect(gallery.locator('article')).toHaveCount(1);
  await gallery.getByRole('button',{name:'Preview A fresh start for your business',exact:true}).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.frameLocator('iframe[title="Gallery design preview"]').getByText('Northstar Technologies', {exact:false})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await gallery.getByRole('button',{name:'Reset gallery',exact:true}).click();
  await gallery.getByLabel('Filter gallery layout').selectOption('digest');
  expect(await gallery.locator('article').count()).toBeGreaterThan(5);
  const catalog = await page.evaluate(async () => {
    const {galleryCatalog,galleryTemplate} = await import('/src/apps/crm/templates/gallery-catalog.ts');
    const {payload} = await import('/src/apps/crm/templates/template-presets.ts');
    return galleryCatalog.map(entry => payload(galleryTemplate(entry)));
  });
  const auth = JSON.parse(fs.readFileSync(process.env.TEMPLATE_STUDIO_AUTH_FILE!, 'utf8'));
  for (const template of catalog) {
    const response = await page.request.post('/api/v1/crm/template-studio/render', {headers:{Authorization:`Bearer ${auth.token}`},data:{template,sample:true}});
    expect(response.ok(), template.name + ': ' + await response.text()).toBeTruthy();
    const rendered = await response.json();
    expect(rendered.unresolved, template.name).toEqual([]);
    expect(rendered.html).toContain('data-suite-template="v1"');
  }
});
