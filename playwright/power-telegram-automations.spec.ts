import { test, expect } from '../frontend/node_modules/playwright/test';
import { setupPowerApps } from './power-apps-fixtures';

for (const width of [1440, 390]) {
  test(`Telegram auto-reply stays inside Automations at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setupPowerApps(page);
    let enabled = true;
    let connected = false;
    await page.route('**/power-apps/automations/telegram/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/setup')) {
        expect(route.request().postDataJSON().token).toBe('123456789:fixture_only');
        connected = true;
        return route.fulfill({ status: 201, json: { resource_id: 91, enabled: true, username: 'fixture_bot' } });
      }
      if (path.endsWith('/simulate')) return route.fulfill({ json: { sent: false, steps: [{ message: 'Sales', reply: 'What is your name?', stage: 'name' }] } });
      if (path.endsWith('/91')) { enabled = route.request().postDataJSON().enabled; return route.fulfill({ json: { enabled } }); }
      return route.fulfill({ json: { items: connected ? [{ resource_id: 91, name: 'Telegram customer enquiries', username: 'fixture_bot', enabled, can_manage: true, messages: [] }] : [] } });
    });
    await page.goto('/power-apps/automations');
    const panel = page.getByRole('region', { name: 'Telegram automations' });
    await expect(panel).toBeVisible();
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
    expect(new URL(page.url()).pathname).toBe('/power-apps/automations');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBeTruthy();
  });
}
