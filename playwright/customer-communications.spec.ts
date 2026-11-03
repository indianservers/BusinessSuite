import { test, expect } from '../frontend/node_modules/playwright/test';
import { authenticateCommunication } from './communication-test-utils';

test('Customer communication workspace creates recipient, previews automation and fits mobile', async ({ page }) => {
  await authenticateCommunication(page);
  await page.route('**/api/v1/branches/context', route => route.fulfill({ json: { company_id: 1, selected: 1, all_branches: false, manage_access: false, branches: [{ id: 1, name: 'Synthetic branch', code: 'TEST', can_write: true }] } }));
  let recipients: any[] = [];
  let rules: any[] = [];
  let savedRecipient: any;
  await page.route('**/api/v1/communication/customers/**', async route => {
    const path = new URL(route.request().url()).pathname.split('/customers')[1];
    const method = route.request().method();
    let data: any = {};
    if (path === '/dashboard') data = { recipients: recipients.length, active_automations: rules.length, statuses: {}, note: 'Email acceptance is not confirmed delivery.' };
    if (path === '/recipients') {
      if (method === 'POST') { savedRecipient = route.request().postDataJSON(); recipients = [{ id: 1, ...savedRecipient }]; data = recipients[0]; }
      else data = { items: recipients };
    }
    if (path === '/automations') {
      if (method === 'POST') { rules = [{ id: 1, version: 1, ...route.request().postDataJSON() }]; data = rules[0]; }
      else data = { items: rules, triggers: ['service.due','order.changed','invoice.due','shipment.changed','contract.due','birthday','campaign','welcome'] };
    }
    if (path === '/deliveries' || path === '/shipments') data = { items: [] };
    if (path === '/settings') data = { paused: false, daily_limit: 1000, customer_daily_limit: 5, bulk_approval_threshold: 50 };
    if (path === '/email-connection') data = { configured: false, source: 'suite', credentials_configured: false };
    if (path.endsWith('/preview')) data = { eligible: 1, excluded: 0, usage_estimate: 1, cost_note: 'Message estimate', sample: { subject: 'Hello Synthetic', body: 'Welcome' } };
    await route.fulfill({ status: method === 'POST' ? 201 : 200, json: data });
  });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.stack ?? error.message));
  await page.goto('/crm/communication-hub?section=customers');
  const workspace = page.getByTestId('customer-communications');
  await expect(workspace).toBeVisible();
  await workspace.getByRole('button', { name: 'customers', exact: true }).click();
  await workspace.getByLabel('Customer name', { exact: true }).fill('Synthetic Customer');
  await workspace.getByLabel('Email', { exact: true }).fill('synthetic@example.com');
  await workspace.getByLabel('Consent evidence / source').fill('Synthetic opt-in');
  // Marketing remains unchecked until explicitly granted.
  const marketing = workspace.getByLabel('marketing', { exact: true });
  await expect(marketing.first()).not.toBeChecked();
  await workspace.getByRole('button', { name: 'Save customer', exact: true }).click();
  await expect(workspace.getByText('synthetic@example.com', { exact: true })).toBeVisible();
  expect(savedRecipient.preferences).toEqual({});
  await workspace.getByRole('button', { name: 'automations', exact: true }).click();
  await workspace.getByRole('button', { name: 'Welcome', exact: true }).click();
  await workspace.getByRole('button', { name: 'Save automation', exact: true }).click();
  await workspace.getByRole('button', { name: 'Preview audience', exact: true }).click();
  await expect(workspace.getByText('1 eligible · 0 excluded · about 1 messages')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await workspace.getByRole('button', { name: 'deliveries', exact: true }).click();
  await expect(workspace.getByText('No messages queued yet.')).toBeVisible();
  await workspace.getByRole('button', { name: 'settings', exact: true }).click();
  await expect(workspace.getByText('Business email connection', { exact: true })).toBeVisible();
  await expect(workspace.getByLabel('SMTP password', { exact: true })).toHaveAttribute('type', 'password');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: 'test-results/customer-communications-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});

