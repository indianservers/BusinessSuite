import { test, expect } from '../frontend/node_modules/playwright/test';
import { setupPowerApps } from './power-apps-fixtures';

for (const width of [1440, 390]) {
  test(`Telegram auto-reply stays inside Automations at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setupPowerApps(page, { configure: true });
    let enabled = true;
    let connected = false;
    let handoffStatus = 'waiting';
    let assigned = false;
    let employeeLinked = false;
    const transcript = [{ id: 1, direction: 'incoming', text: 'Please help with my order' }];
    await page.route('**/power-apps/automations/telegram/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/setup')) {
        expect(route.request().postDataJSON().token).toBe('123456789:fixture_only');
        connected = true;
        return route.fulfill({ status: 201, json: { resource_id: 91, enabled: true, username: 'fixture_bot' } });
      }
      if (path.endsWith('/employee-options')) return route.fulfill({ json: { items: [{ id: 3, employee_code: 'EMP-3', name: 'Alex Employee', user_id: 1 }] } });
      if (path.endsWith('/employee-links')) { expect(route.request().postDataJSON()).toEqual({ employee_id: 3, telegram_user_id: '123456789' }); employeeLinked = true; return route.fulfill({ status: 201, json: { identity_id: 1 } }); }
      if (path.endsWith('/operations')) return route.fulfill({ json: { current_user_id: 1, can_manage: true, identities: employeeLinked ? [{ id: 1, interface: 'company', name: 'Alex Employee', telegram_user_id: '123456789', employee_id: 3, user_id: 1, verified: true }] : [], conversations: [{ id: 8, interface: 'public', chat_id: '42', status: handoffStatus, assignee_user_id: assigned ? 1 : null, messages: transcript }] } });
      if (path.endsWith('/conversations/8')) { const action = route.request().postDataJSON().action; handoffStatus = action === 'claim' ? 'assigned' : action === 'resolve' ? 'resolved' : 'bot'; assigned = action === 'claim'; return route.fulfill({ json: { status: handoffStatus } }); }
      if (path.endsWith('/conversations/8/reply')) { expect(route.request().postDataJSON().text).toBe('We are checking your order.'); transcript.push({ id: 2, direction: 'outgoing', text: route.request().postDataJSON().text }); return route.fulfill({ status: 202, json: { run_id: 99, status: 'queued' } }); }
      if (path.endsWith('/configuration')) return route.fulfill({ json: { configuration: route.request().postDataJSON() } });
      if (path.endsWith('/simulate')) return route.fulfill({ json: { sent: false, steps: [{ message: 'Sales', reply: 'What is your name?', stage: 'name' }] } });
      if (path.endsWith('/91')) { enabled = route.request().postDataJSON().enabled; return route.fulfill({ json: { enabled } }); }
      return route.fulfill({ json: { items: connected ? [{ resource_id: 91, name: 'Telegram customer enquiries', username: 'fixture_bot', enabled, can_manage: true, messages: [] }] : [] } });
    });
    await page.goto('/power-apps/automations');
    const panel = page.getByRole('region', { name: 'Telegram automations' });
    await expect(panel).toBeVisible({ timeout: 45000 });
    await panel.getByRole('button', { name: 'Connect Telegram bot' }).click();
    await panel.getByLabel('Telegram bot token').fill('123456789:fixture_only');
    await panel.getByRole('button', { name: 'Verify bot & enable auto-reply' }).click();
    await expect(panel.getByRole('link', { name: '@fixture_bot' })).toBeVisible();
    await expect(panel.getByLabel('Telegram bot token')).toHaveCount(0);
    await panel.getByRole('button', { name: 'Pause replies' }).click();
    await expect(panel.getByRole('button', { name: 'Enable replies' })).toBeVisible();
    await panel.getByText('Try the enquiry scenario locally', { exact: true }).click();
    await panel.getByRole('button', { name: 'Run local preview' }).click();
    await expect(panel.getByRole('status')).toContainText('What is your name?');
    await panel.getByRole('link', { name: 'Open Telegram configuration page' }).click();
    await expect(page).toHaveURL(/automations\/telegram/);
    const configuration = page.getByRole('region', { name: 'Telegram automations' });
    await expect(configuration.getByText('Public interface', { exact: true })).toBeVisible();
    await expect(configuration.getByText('Company interface', { exact: true })).toBeVisible();
    await configuration.getByLabel('Create CRM leads and tasks from completed requests').check();
    await configuration.getByLabel('Company welcome message').fill('Welcome to our company');
    await configuration.getByRole('button', { name: 'Save interface settings' }).click();
    await expect(configuration.getByText('Telegram configuration saved.')).toBeVisible();
    await configuration.getByText('Identity linking & human handoff', { exact: true }).click();
    await configuration.getByRole('combobox', { name: 'Employee', exact: true }).selectOption('3');
    await configuration.getByLabel('Employee Telegram user ID', { exact: true }).fill('123456789');
    await configuration.getByRole('button', { name: 'Link employee Telegram ID' }).click();
    await expect(configuration.getByText('Employee linked. Company authorization is automatic on their next message.')).toBeVisible();
    await configuration.getByRole('button', { name: /public · Chat 42/ }).click();
    await configuration.getByRole('button', { name: 'Claim conversation' }).click();
    await expect(configuration.getByLabel('Reply through Telegram')).toBeEnabled();
    await configuration.getByLabel('Reply through Telegram').fill('We are checking your order.');
    await configuration.getByRole('button', { name: 'Queue Telegram reply' }).click();
    await expect(configuration.getByText('Reply queued. Check its execution status for delivery.')).toBeVisible();
    await expect(configuration.getByText('We are checking your order.', { exact: true })).toBeVisible();
    await configuration.getByRole('button', { name: 'Return to bot', exact: true }).click();
    await expect(configuration.getByLabel('Reply through Telegram')).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBeTruthy();
  });
}
