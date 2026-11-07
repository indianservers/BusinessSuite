// CUA-only browser audit. Pass an already-bound tab; no browser/network setup.
import { readFile, writeFile } from 'node:fs/promises';

export async function resumeGridAudit(tab, root) {
  let checks;
  try { checks = JSON.parse(await readFile(`${root}/grid-controls.json`, 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; checks = []; }
  const save = () => writeFile(`${root}/grid-controls.json`, JSON.stringify(checks, null, 2));
  async function record(page, grid, control, action) {
    const result = { page, grid, control, result: 'passed' };
    try { result.evidence = await action(); }
    catch (error) { result.result = 'needs-review'; result.error = String(error); }
    checks.push(result); await save();
    return result;
  }
  const grids = () => tab.playwright.locator('main [data-grid-id]').evaluateAll(es => es.map(e => ({
    id: e.getAttribute('data-grid-id'),
    columns: Array.from(e.querySelectorAll('th,[role="columnheader"]')).map(x => x.textContent?.trim()),
    controls: Array.from(e.querySelectorAll('button')).map(x => x.getAttribute('aria-label') || x.textContent?.trim()),
  })).filter(x => x.controls.includes('Columns')));
  async function columns(page, id, limit = 3) {
    const grid = tab.playwright.locator(`[data-grid-id=${JSON.stringify(id)}]`);
    const popover = tab.playwright.locator('.udg-column-manager');
    if (!await popover.count()) await grid.getByRole('button', { name: 'Columns', exact: true }).click();
    const names = await popover.locator('.udg-column-option label').allTextContents({});
    let completed = 0;
    for (const rawName of names) {
      const name = rawName.trim();
      if (checks.some(x => x.page === page && x.grid === id && x.control === `Column ${name}: visibility, all pin positions, ordering` && x.result === 'passed')) continue;
      if (completed++ >= limit) return { pending: true };
      const option = popover.locator(`.udg-column-option:has(select[aria-label=${JSON.stringify(`Pin ${name}`)}])`);
      await record(page, id, `Column ${name}: visibility, all pin positions, ordering`, async () => {
        const input = option.locator('input[type="checkbox"]');
        const original = await input.evaluate(e => e.checked);
        const select = option.locator('select');
        const originalPin = await select.evaluate(e => e.selectedIndex);
        await input.setChecked(!original);
        if (await input.evaluate(e => e.checked) !== !original) throw new Error('Visibility checkbox did not change');
        await input.setChecked(original);
        for (const pin of ['left', 'right', 'none']) {
          await select.selectOption(pin);
          if (await select.evaluate(e => e.options[e.selectedIndex].value) !== pin) throw new Error(`Pin ${pin} did not persist`);
        }
        await select.selectOption({ index: originalPin });
        const before = await popover.locator('.udg-column-option label').allTextContents({});
        const index = before.findIndex(x => x.trim() === name);
        const direction = index < before.length - 1 ? 'right' : 'left';
        await option.getByRole('button', { name: `Move ${name} ${direction}`, exact: true }).click();
        const after = await popover.locator('.udg-column-option label').allTextContents({});
        if (after.findIndex(x => x.trim() === name) !== index + (direction === 'right' ? 1 : -1)) throw new Error('Column order did not move');
        await option.getByRole('button', { name: `Move ${name} ${direction === 'right' ? 'left' : 'right'}`, exact: true }).click();
        if (JSON.stringify(await popover.locator('.udg-column-option label').allTextContents({})) !== JSON.stringify(before)) throw new Error('Column order did not restore');
        return 'Visibility toggled/restored; Left, Right and Unpinned selected; adjacent ordering moved/restored. Assertions cover control state and manager order.';
      });
    }
    await record(page, id, 'Auto-fit all columns', async () => {
      await popover.getByRole('button', { name: 'Auto-fit all columns', exact: true }).click();
      const widths = await grid.getByRole('columnheader').evaluateAll(es => es.map(e => e.getBoundingClientRect().width));
      if (!widths.length || widths.some(x => x <= 0)) throw new Error('Invalid header width after auto-fit');
      return `${widths.length} header widths remain positive after auto-fit; exact content fit requires visual review.`;
    });
    await popover.getByRole('button', { name: 'Close column manager', exact: true }).click();
    await popover.waitFor({ state: 'detached' });
  }
  async function savedViews(page, id) {
    const grid = tab.playwright.locator(`[data-grid-id=${JSON.stringify(id)}]`);
    await record(page, id, 'Saved views: create, load, remove, close', async () => {
      await grid.getByRole('button', { name: 'Saved views', exact: true }).click();
      const popover = tab.playwright.locator('.udg-popover').filter({ hasText: 'My saved views' });
      const name = `QA local ${Date.now()}`;
      await popover.getByRole('textbox', { name: 'Saved view name', exact: true }).fill(name);
      await popover.getByRole('button', { name: 'Save current view', exact: true }).click();
      await popover.getByRole('button', { name, exact: true }).waitFor({ state: 'visible' });
      await popover.getByRole('button', { name, exact: true }).click();
      await popover.getByRole('button', { name: `Delete view ${name}`, exact: true }).click();
      await popover.getByRole('button', { name, exact: true }).waitFor({ state: 'detached' });
      await popover.getByRole('button', { name: 'Close saved views', exact: true }).click();
      await popover.waitFor({ state: 'detached' });
      return 'Created a uniquely named QA view, invoked load, removed only that view, and closed the popover. View content equivalence is not asserted.';
    });
  }
  return { checks, grids, columns, savedViews };
}
