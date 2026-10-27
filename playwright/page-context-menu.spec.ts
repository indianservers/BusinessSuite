import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test('page menu executes the actual role action and supports keyboard dismissal', async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto('/admin/roles');
  await expectAdminSecurityShell(page);
  const button = page.getByRole('button', { name: 'Create role', exact: true });
  await button.focus();
  await page.keyboard.press('Shift+F10');
  const menu = page.locator('[data-page-context-menu]');
  await expect(menu).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: /payroll|invoice|lead/i })).toHaveCount(0);
  await page.keyboard.press('End');
  await expect(menu.getByRole('menuitem').last()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);
  await expect(button).toBeFocused();
  await button.click({ button: 'right' });
  await menu.getByRole('menuitem', { name: 'Create role', exact: true }).click();
  await expect(page.getByText('Role created', { exact: true })).toBeVisible();
  await expect(menu).toHaveCount(0);
});

test('all modules discover only current page or record controls', async ({ page }) => {
  await page.route('**/api/**', route => route.fulfill({ json: {} }));
  await page.goto('/login');
  const result = await page.evaluate(async () => {
    const { collectPageContext } = await import('/src/lib/page-context-actions.ts');
    const results: Record<string, string[]> = {};
    for (const [module, action] of [['CRM', 'Create lead'], ['HRMS', 'Process payroll'], ['FAM', 'Reconcile statement'], ['SRM', 'Create invoice'], ['Inventory', 'Adjust stock'], ['PMS', 'Create project'], ['AI', 'Run analysis'], ['Administration', 'Create role']]) {
      const root = document.createElement('main');
      root.innerHTML = `<h1>${module}</h1><button>${action}</button><button disabled>Delete everything</button><button style="display:none">Export hidden data</button><table><tbody><tr><td>Alpha</td><td><button>Edit Alpha</button></td></tr><tr><td>Beta</td><td><button>Edit Beta</button></td></tr></tbody></table><input aria-label="Search records" placeholder="Search records">`;
      document.body.append(root);
      results[module] = collectPageContext(root, root)?.actions.map(a => a.label) || [];
      results[`${module} record`] = collectPageContext(root.querySelector('td')!, root)?.actions.map(a => a.label) || [];
      const row = root.querySelector('tr')!;
      row.dataset.contextOpen = `Open ${module} record`;
      results[`${module} open`] = collectPageContext(row, root)?.actions.map(a => a.label) || [];
      results[`${module} input`] = collectPageContext(root.querySelector('input')!, root)?.actions.map(a => a.label) || [];
      root.remove();
    }
    return results;
  });
  for (const [module, action] of [['CRM', 'Create lead'], ['HRMS', 'Process payroll'], ['FAM', 'Reconcile statement'], ['SRM', 'Create invoice'], ['Inventory', 'Adjust stock'], ['PMS', 'Create project'], ['AI', 'Run analysis'], ['Administration', 'Create role']]) {
    expect(result[module]).toContain(action);
    expect(result[module]).not.toContain('Delete everything');
    expect(result[module]).not.toContain('Export hidden data');
    expect(result[module]).not.toContain('Edit Alpha');
    expect(result[`${module} record`]).toEqual(['Edit Alpha']);
    expect(result[`${module} open`]).toContain(`Open ${module} record`);
    expect(result[`${module} input`]).toEqual([]);
  }
});

test('screen edges and existing record menu priority', async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto('/admin/roles');
  await expectAdminSecurityShell(page);
  await page.locator('main').first().evaluate(root => {
    root.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: innerWidth - 1, clientY: innerHeight - 1 }));
  });
  const menu = page.locator('[data-page-context-menu]');
  await expect(menu).toBeVisible();
  const box = await menu.boundingBox();
  const viewport = page.viewportSize()!;
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
  await page.keyboard.press('Escape');
  await page.locator('main').first().evaluate(root => {
    root.addEventListener('contextmenu', event => event.preventDefault(), { once: true });
    root.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
  });
  await expect(menu).toHaveCount(0);
});
