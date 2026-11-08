const { chromium, expect } = require('playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const origin = process.env.WORKFLOW_BOARD_QA_ORIGIN || 'http://localhost:5174';
if (!['localhost', '127.0.0.1'].includes(new URL(origin).hostname)) throw Error('Loopback QA only');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const board = page.locator('.workflow-board');
    const open = async module => { await page.goto(`${origin}/workflow-board-qa.html?module=${module}`); await expect(board.locator('.workflow-board-lane').first()).toBeVisible(); };
    await open('crm');
    const qualification = board.getByRole('region', { name: 'Qualification stage', exact: true });
    // Native sections with accessible names are regions.
    await expect(qualification.locator('.workflow-board-record strong').first()).toHaveText('Urgent opportunity');
    await expect(qualification.locator('.workflow-board-record')).toHaveCount(3);
    await expect(qualification.getByText('Overdue', { exact: true })).toBeVisible();
    await qualification.getByRole('button', { name: 'View Qualification: 4 records', exact: true }).click();
    await expect(page.getByRole('dialog').locator('.workflow-board-card')).toHaveCount(4);
    await page.getByRole('button', { name: 'Close dialog' }).click();
    await board.getByLabel('Owner', { exact: true }).selectOption('1');
    await expect(board.locator('.workflow-board-record')).toHaveCount(2);
    await board.getByLabel('Team', { exact: true }).selectOption('1');
    await expect(board.locator('.workflow-board-record')).toHaveCount(2);
    await board.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await board.getByLabel('Owner', { exact: true }).selectOption('__unassigned');
    await expect(board.locator('.workflow-board-record')).toHaveCount(2);
    await expect(board.getByText('Awaiting approval', { exact: true })).toBeVisible();
    await board.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await board.getByLabel('Expected close from', { exact: true }).fill('2099-01-01');
    await expect(board.locator('.workflow-board-record')).toHaveCount(0);
    await board.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await page.getByRole('button', { name: 'Toggle read-only access' }).click();
    await expect(board.getByRole('button', { name: 'Change stage' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Toggle read-only access' }).click();
    await expect(board.getByRole('button', { name: 'Change stage' }).first()).toBeVisible();
    await page.getByRole('button', { name: 'Toggle branch read-only' }).click();
    await expect(board.getByRole('button', { name: 'Change stage' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Toggle branch read-only' }).click();
    await page.getByRole('button', { name: 'Toggle service failure' }).click();
    await expect(board.getByRole('alert')).toContainText('Workflow fixture unavailable');
    await expect(board.locator('.workflow-board-record')).toHaveCount(0);
    await page.getByRole('button', { name: 'Toggle service failure' }).click();
    await expect(board.locator('.workflow-board-lane').first()).toBeVisible();
    const checks = [['hrms', 'Hiring pipeline', '/hrms/recruitment?candidate=6'], ['pms', 'Work delivery pipeline', '/pms/tasks/7'], ['srm', 'Sales order pipeline', '/srm/sales-orders/9'], ['fam', 'Collections pipeline', '/fam/vouchers/13'], ['power_apps', 'Approvals pipeline', '/power-apps/approvals/inbox?environment=development&request=11']];
    const out = path.resolve(__dirname, '../../docs/qa/workflow-board');
    fs.mkdirSync(out, { recursive: true });
    for (const [module, title, href] of checks) {
      await open(module);
      await expect(board.getByRole('heading', { name: title, exact: true })).toBeVisible();
      await expect(board.locator(`a[href="${href}"]`)).toHaveCount(1);
      await expect(board.getByLabel('Team', { exact: true })).toBeVisible();
      await expect(board.getByLabel('Owner', { exact: true })).toBeVisible();
      await expect(board.getByLabel('Current branch', { exact: true })).toBeVisible();
      await board.getByRole('button', { name: 'View all', exact: true }).click();
      await expect(page.getByRole('dialog').locator('.workflow-board-card')).not.toHaveCount(0);
      await page.keyboard.press('Escape');
      if (module === 'pms') {
        await board.getByRole('button', { name: 'Change stage' }).first().click();
        await page.getByLabel('Destination stage', { exact: true }).selectOption('In Review');
        await expect(page.getByRole('button', { name: 'Request transition approval', exact: true })).toBeVisible();
        await page.getByRole('button', { name: 'Request transition approval', exact: true }).click();
        await expect(page.getByRole('dialog')).toHaveCount(0);
        assert((await page.locator('body').getAttribute('data-workflow-mutation')).startsWith('post:/project-management/tasks/7/transition-approvals'));
      }
      if (module === 'hrms') {
        await page.getByRole('button', { name: 'Toggle transition rejection' }).click();
        await board.getByRole('button', { name: 'Change stage' }).first().click();
        await page.getByLabel('Destination stage', { exact: true }).selectOption('Screening');
        await page.getByRole('button', { name: 'Confirm stage change', exact: true }).click();
        await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Required evidence is missing');
        await expect(page.getByLabel('Destination stage', { exact: true })).toHaveValue('Screening');
        await page.keyboard.press('Escape');
      }
      await page.screenshot({ path: path.join(out, `${module}-desktop.png`), fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, module + ' must not overflow the mobile viewport');
      await page.screenshot({ path: path.join(out, `${module}-mobile.png`), fullPage: true });
      await page.setViewportSize({ width: 1440, height: 1000 });
    }
    assert.deepEqual(errors, []);
    console.log('Workflow Board browser: all six adapters, filters, column drill-down, urgency, compact cards, stage permission/rejection, approval requests, retries, links and mobile layout passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
