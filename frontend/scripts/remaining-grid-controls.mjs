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
    await record(page, id, 'Saved views: restore changed column visibility, remove, close', async () => {
      await grid.getByRole('button', { name: 'Saved views', exact: true }).click();
      const popover = tab.playwright.locator('.udg-popover').filter({ hasText: 'My saved views' });
      const name = `QA local ${Date.now()}`;
      await popover.getByRole('textbox', { name: 'Saved view name', exact: true }).fill(name);
      await popover.getByRole('button', { name: 'Save current view', exact: true }).click();
      await popover.getByRole('button', { name, exact: true }).waitFor({ state: 'visible' });
      await popover.getByRole('button', { name: 'Close saved views', exact: true }).click();
      await grid.getByRole('button', { name: 'Columns', exact: true }).click();
      const manager = tab.playwright.locator('.udg-column-manager');
      const checkbox = manager.getByRole('checkbox').first();
      const original = await checkbox.evaluate(e => e.checked);
      await checkbox.setChecked(!original);
      await manager.getByRole('button', { name: 'Close column manager', exact: true }).click();
      await grid.getByRole('button', { name: 'Saved views', exact: true }).click();
      await popover.getByRole('button', { name, exact: true }).click();
      if (!await popover.count()) await grid.getByRole('button', { name: 'Saved views', exact: true }).click();
      await popover.getByRole('button', { name: `Delete view ${name}`, exact: true }).click();
      await popover.getByRole('button', { name, exact: true }).waitFor({ state: 'detached' });
      await popover.getByRole('button', { name: 'Close saved views', exact: true }).click();
      await popover.waitFor({ state: 'detached' });
      await grid.getByRole('button', { name: 'Columns', exact: true }).click();
      if (await checkbox.evaluate(e => e.checked) !== original) throw new Error('Saved view did not restore column visibility');
      await manager.getByRole('button', { name: 'Close column manager', exact: true }).click();
      return 'Saved a uniquely named QA view; changed first column visibility; loaded the view; verified original visibility restored; removed only that view; closed both popovers. Other saved-view fields are not asserted.';
    });
  }
  async function display(page, id) {
    const grid = tab.playwright.locator(`[data-grid-id=${JSON.stringify(id)}]`);
    await record(page, id, 'Display: density, row-height endpoints, views, reset and undo', async () => {
      await grid.getByRole('button', { name: 'Grid display options', exact: true }).click();
      const popover = tab.playwright.locator('.udg-popover').filter({ hasText: 'Display & layout' });
      const density = popover.locator('select[aria-label="Grid density"]');
      const originalDensity = await density.evaluate(e => e.value);
      for (const value of ['comfortable', 'compact']) {
        await density.selectOption(value);
        if (await density.evaluate(e => e.value) !== value) throw new Error(`Density ${value} did not select`);
      }
      await popover.getByRole('button', { name: 'Undo layout change', exact: true }).click();
      await popover.getByRole('button', { name: 'Undo layout change', exact: true }).click();
      if (await density.evaluate(e => e.value) !== originalDensity) throw new Error('Density undo did not restore');
      const height = popover.locator('input[aria-label="Row height"]');
      const originalHeight = await height.evaluate(e => e.value);
      await height.press('Home');
      if (await height.evaluate(e => e.value) !== '32') throw new Error('Row height minimum failed');
      await height.press('End');
      if (await height.evaluate(e => e.value) !== '88') throw new Error('Row height maximum failed');
      await popover.getByRole('button', { name: 'Undo layout change', exact: true }).click();
      await popover.getByRole('button', { name: 'Undo layout change', exact: true }).click();
      if (await height.evaluate(e => e.value) !== originalHeight) throw new Error('Row height undo did not restore');
      const view = popover.locator('select[aria-label="Grid view"]');
      let viewCount = 0;
      if (await view.count()) {
        const original = await view.evaluate(e => e.value);
        const values = await view.evaluate(e => Array.from(e.options).map(x => x.value));
        for (const value of values) {
          await view.selectOption(value);
          if (await view.evaluate(e => e.value) !== value) throw new Error(`View ${value} did not select`);
        }
        await view.selectOption(original); viewCount = values.length;
      }
      await popover.getByRole('button', { name: 'Reset columns', exact: true }).click();
      await popover.getByRole('button', { name: 'Undo layout change', exact: true }).click();
      await density.press('Escape');
      await popover.waitFor({ state: 'detached' });
      return `Both densities selected; height32/88 verified and undone; ${viewCount} view modes selected/restored; reset and undo invoked. Rendered record equivalence and intermediate slider values are not asserted.`;
    });
  }
  async function grouping(page, id, limit = 3) {
    const grid = tab.playwright.locator(`[data-grid-id=${JSON.stringify(id)}]`);
    const select = grid.locator('select[aria-label="Add grouping column"]');
    if (!await select.count()) return { exposed: false };
    const choices = await select.evaluate(e => Array.from(e.options).filter(o => o.value && !o.disabled).map(o => ({ value: o.value, name: o.text })));
    let completed = 0;
    for (const choice of choices) {
      const control = `Group by ${choice.name}: render, expand, collapse, remove`;
      if (checks.some(x => x.page === page && x.grid === id && x.control === control && x.result === 'passed')) continue;
      if (completed++ >= limit) return { pending: true };
      await record(page, id, control, async () => {
        const total = Number(await grid.getByRole('grid').getAttribute('aria-rowcount')) - 1;
        await select.selectOption(choice.value);
        const remove = grid.getByRole('button', { name: `Remove grouping ${choice.name}`, exact: true });
        await remove.waitFor({ state: 'visible' });
        await grid.locator('[aria-busy="true"]').first().waitFor({ state: 'detached' });
        const errors = await grid.locator('[role="alert"]').allTextContents({});
        if (errors.length) throw new Error(`Grouped grid error: ${errors.join('; ')}`);
        if (total > 0) await grid.locator('.udg-group-row').first().waitFor({ state: 'visible' });
        await grid.getByRole('button', { name: 'Expand loaded groups', exact: true }).click();
        await grid.getByRole('button', { name: 'Expand loaded groups', exact: true }).waitFor({ state: 'visible' });
        if (total > 0) await grid.locator('.udg-group-row button[aria-expanded="true"]').first().waitFor({ state: 'visible' });
        await grid.getByRole('button', { name: 'Collapse all', exact: true }).click();
        if (await grid.locator('.udg-group-row button[aria-expanded="true"]').count()) throw new Error('Expanded group remained after collapse all');
        await remove.click();
        await remove.waitFor({ state: 'detached' });
        return `Grouping chip appeared; request completed without alert; ${total > 0 ? 'group rows rendered and expanded' : 'empty dataset retained'}; collapse cleared expanded groups; chip removed. Exact group membership is not asserted.`;
      });
    }
    return { pending: false };
  }
  async function filterCase(page, id, test) {
    const grid = tab.playwright.locator(`[data-grid-id=${JSON.stringify(id)}]`);
    return record(page, id, `Filter ${test.field} ${test.operator} ${test.value ?? ''} ${test.upper ?? ''}`, async () => {
      await grid.getByRole('button', { name: /^Filters/ }).click();
      const dialog = tab.playwright.getByRole('dialog', { name: 'Advanced filters', exact: true });
      await dialog.getByRole('button', { name: 'Clear conditions', exact: true }).click();
      await dialog.getByRole('button', { name: 'Condition', exact: true }).click();
      await dialog.locator('select[aria-label="Filter column 1"]').selectOption(test.field);
      await dialog.locator('select[aria-label="Filter operator 1"]').selectOption(test.operator);
      if (test.value !== undefined) await dialog.locator('input[aria-label="Filter value 1"]').fill(test.value);
      if (test.upper !== undefined) await dialog.locator('input[aria-label="Filter upper value 1"]').fill(test.upper);
      await dialog.getByRole('button', { name: 'Apply filters', exact: true }).click();
      await grid.locator(`[role="grid"][aria-busy="false"][aria-rowcount="${test.expected.length + 1}"]`).waitFor({ state: 'visible' });
      const errors = await grid.locator('[role="alert"]').allTextContents({});
      if (errors.length) throw new Error(errors.join('; '));
      const names = await grid.locator('input[aria-label^="Select row "]').evaluateAll(es => es.map(e => e.getAttribute('aria-label').replace(/^Select row /, '')).sort());
      if (JSON.stringify(names) !== JSON.stringify([...test.expected].sort())) throw new Error(`Expected ${JSON.stringify(test.expected)}; observed ${JSON.stringify(names)}`);
      return `Server-filtered result count and visible row names match ${JSON.stringify(test.expected)}.`;
    });
  }
  async function clearFilters(id) {
    const grid = tab.playwright.locator(`[data-grid-id=${JSON.stringify(id)}]`);
    await grid.getByRole('button', { name: /^Filters/ }).click();
    const dialog = tab.playwright.getByRole('dialog', { name: 'Advanced filters', exact: true });
    await dialog.getByRole('button', { name: 'Clear conditions', exact: true }).click();
    await dialog.getByRole('button', { name: 'Apply filters', exact: true }).click();
    await grid.locator('[aria-busy="true"]').first().waitFor({ state: 'detached' });
  }
  return { checks, grids, columns, savedViews, display, grouping, filterCase, clearFilters };
}
