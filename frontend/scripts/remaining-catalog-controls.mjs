// CUA only. Requires the explicitly disposable, generated catalog fixture.
import { readFile, writeFile } from 'node:fs/promises';

export async function resumeCatalogAudit(tab, root) {
  const file = `${root}/catalog-page-controls.json`;
  let checks;
  try { checks = JSON.parse(await readFile(file, 'utf8')).map(item => ({ page: 'crm/products', ...item })); }
  catch (error) { if (error.code !== 'ENOENT') throw error; checks = []; }
  const save = () => writeFile(file, JSON.stringify(checks, null, 2));
  const scope = tab.playwright.locator('.sc-page').filter({ visible: true });
  const cards = () => scope.locator('.sc-card').evaluateAll(es => es.map(e => ({
    name: e.querySelector('.sc-card-title').textContent.trim(),
    kind: e.querySelector('.sc-kind').textContent.trim(),
    image: !!e.querySelector('.sc-card-cover img'),
    price: Number(e.querySelector('.sc-card-price > strong').textContent.replace(/[^\d.-]/g, '')),
    category: e.querySelector('.sc-card-code > span').textContent.trim() === 'Uncategorized' ? '' : e.querySelector('.sc-card-code > span').textContent.trim(),
    code: Array.from(e.querySelector('.sc-card-code').childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim(),
  })));
  async function waitNames(names) {
    if (!names.length) await scope.getByRole('article').first().waitFor({ state: 'detached' });
    for (let index = 0; index < names.length; index++) {
      await scope.getByRole('article').nth(index).getByRole('button', { name: names[index], exact: true }).waitFor({ state: 'visible' });
    }
    await scope.getByRole('article').nth(names.length).waitFor({ state: 'detached' });
    const actual = (await cards()).map(item => item.name);
    if (JSON.stringify(actual) !== JSON.stringify(names)) throw new Error(`Expected ${JSON.stringify(names)}; observed ${JSON.stringify(actual)}`);
    const errors = await scope.getByRole('alert').allTextContents({});
    if (errors.length) throw new Error(errors.join('; '));
  }
  async function record(page, control, action) {
    if (checks.some(item => item.page === page && item.control === control && item.result === 'passed')) return { skipped: true };
    const item = { page, control, result: 'passed' };
    try { item.evidence = await action(); }
    catch (error) { item.result = 'needs-review'; item.error = String(error); }
    checks.push(item); await save(); return item;
  }
  const ordered = (rows, field) => [...rows].sort((a, b) => field === 'price' ? a.price - b.price : a[field].localeCompare(b[field]));
  async function sortBatch(page, limit = 2) {
    const rows = await cards();
    if (rows.length !== 3 || rows.some(item => !item.name.includes('QA'))) throw new Error('Expected the three active QA offerings');
    let completed = 0;
    for (const field of ['name', 'price', 'category', 'code']) {
      const control = `Sort ${field}: ascending, descending, restore`;
      if (checks.some(item => item.page === page && item.control === control && item.result === 'passed')) continue;
      if (completed++ >= limit) return { pending: true };
      const item = await record(page, control, async () => {
        if (new Set(rows.map(row => row[field])).size !== rows.length) throw new Error('Use distinct sort fixture values');
        const ascending = ordered(rows, field).map(row => row.name);
        await scope.getByRole('combobox', { name: 'Sort catalog', exact: true }).selectOption(field);
        await waitNames(ascending);
        await scope.getByRole('button', { name: 'Reverse sort order', exact: true }).click();
        await waitNames([...ascending].reverse());
        await scope.getByRole('button', { name: 'Reverse sort order', exact: true }).click();
        await waitNames(ascending);
        await scope.getByRole('combobox', { name: 'Sort catalog', exact: true }).selectOption('name');
        await waitNames(ordered(rows, 'name').map(row => row.name));
        return `Distinct fixture values; ascending ${JSON.stringify(ascending)}, exact reverse verified, then original ascending/name restored.`;
      });
      if (item.result === 'needs-review') return item;
    }
    return { pending: false };
  }
  async function filters(page) {
    const rows = await cards();
    if (rows.length !== 3) throw new Error('Begin with all three active QA offerings');
    const names = ordered(rows, 'name').map(row => row.name);
    for (const [label, kind] of [['Products', 'product'], ['Services', 'service'], ['All items', '']]) {
      const item = await record(page, `Type filter ${label}`, async () => {
        await scope.getByRole('button', { name: label, exact: true }).click();
        const expected = ordered(rows.filter(row => !kind || row.kind === kind), 'name').map(row => row.name);
        await waitNames(expected);
        return `Exact displayed names ${JSON.stringify(expected)}.`;
      });
      if (item.result === 'needs-review') return item;
    }
    for (const [query, expected] of [['ZZ-QA-SORT', rows.filter(row => row.code === 'ZZ-QA-SORT').map(row => row.name)], ['no-such-QA-offering', []], ['', names]]) {
      const item = await record(page, `Search catalog ${query || '(clear)'}`, async () => {
        await scope.getByRole('textbox', { name: 'Search catalog', exact: true }).fill(query);
        await waitNames(expected); return `Exact displayed names ${JSON.stringify(expected)}.`;
      });
      if (item.result === 'needs-review') return item;
    }
    for (const [query, expected] of [['ZZ QA', rows.filter(row => row.category === 'ZZ QA').map(row => row.name)], ['no-such-QA-category', []], ['', names]]) {
      const item = await record(page, `Category filter ${query || '(clear)'}`, async () => {
        await scope.getByRole('textbox', { name: 'Filter category', exact: true }).fill(query);
        await waitNames(expected); return `Exact displayed names ${JSON.stringify(expected)}.`;
      });
      if (item.result === 'needs-review') return item;
    }
    const archived = ['QA lead service controls (copy)'];
    for (const [status, expected] of [['Archived', archived], ['all', [...names, ...archived].sort((a, b) => a.localeCompare(b))], ['Active', names]]) {
      const item = await record(page, `Status filter ${status}`, async () => {
        await scope.getByRole('combobox', { name: 'Filter status', exact: true }).selectOption(status);
        await waitNames(expected); return `Exact displayed names ${JSON.stringify(expected)}.`;
      });
      if (item.result === 'needs-review') return item;
    }
    return { passed: true };
  }
  async function previewBatch(page, limit = 2) {
    let completed = 0;
    for (const row of await cards()) {
      const control = `Row preview/title/edit/cancel ${row.name}`;
      if (checks.some(item => item.page === page && item.control === control && item.result === 'passed')) continue;
      if (completed++ >= limit) return { pending: true };
      const item = await record(page, control, async () => {
        await scope.getByRole('button', { name: `Preview ${row.name}`, exact: true }).click();
        const preview = tab.playwright.getByRole('dialog', { name: row.name, exact: true });
        if (row.image) {
          await preview.locator('img').waitFor({ state: 'visible' });
          const dimensions = await preview.locator('img').evaluate(e => ({ width: e.naturalWidth, height: e.naturalHeight }));
          if (!dimensions.width || !dimensions.height) throw new Error('Preview image did not load');
        }
        if (!(await preview.locator('.sc-preview-price').innerText()).startsWith(`₹${row.price.toFixed(2)}`)) throw new Error('Preview base price differs');
        await preview.getByRole('button', { name: 'Close preview', exact: true }).click();
        await scope.getByRole('button', { name: row.name, exact: true }).click();
        await preview.getByRole('button', { name: 'Edit item', exact: true }).click();
        const editor = tab.playwright.getByRole('dialog', { name: 'Edit product or service', exact: true });
        if (await editor.getByRole('textbox', { name: 'Name', exact: true }).evaluate(e => e.value) !== row.name) throw new Error('Editor item differs');
        if (!await editor.getByRole('combobox', { name: 'Type', exact: true }).evaluate(e => e.disabled)) throw new Error('Existing item type should be immutable');
        await editor.getByRole('button', { name: 'Cancel', exact: true }).click();
        await scope.getByRole('button', { name: `Edit ${row.name}`, exact: true }).click();
        await editor.getByRole('textbox', { name: 'Name', exact: true }).waitFor({ state: 'visible' });
        await editor.getByRole('button', { name: 'Cancel', exact: true }).click();
        return 'Cover preview and title preview opened correct record/base price; image loaded where present; preview Edit and row Edit opened correct immutable-kind editor; both Cancel actions returned catalog.';
      });
      if (item.result === 'needs-review') return item;
    }
    return { pending: false };
  }
  async function bulk(page) {
    return record(page, 'Individual/page selection, bulk reuse modes, filter reset', async () => {
      const rows = await cards();
      const reuse = scope.getByRole('button', { name: 'Reuse in other branches', exact: true });
      for (const row of rows) {
        const checkbox = scope.getByRole('checkbox', { name: `Select ${row.name}`, exact: true });
        await checkbox.check();
        if (!await checkbox.evaluate(e => e.checked) || !await reuse.isEnabled()) throw new Error('Individual selection failed');
        await checkbox.uncheck();
      }
      const all = scope.getByRole('checkbox', { name: 'Select all offerings on this page', exact: true });
      await all.check();
      await scope.locator('input[type=checkbox]:checked').nth(rows.length).waitFor({ state: 'attached' });
      if ((await scope.getByRole('checkbox').evaluateAll(es => es.filter(e => e.checked).length)) !== rows.length + 1) throw new Error('Page selection incomplete');
      await reuse.click();
      const dialog = tab.playwright.getByRole('dialog', { name: 'Reuse in other branches', exact: true });
      if (!(await dialog.innerText()).includes(`${rows.length} selected offering`)) throw new Error('Bulk record count differs');
      const select = dialog.getByRole('combobox', { name: 'Branch reuse action', exact: true });
      await dialog.getByText('No other writable branches are available.', { exact: true }).waitFor({ state: 'visible' });
      const choices = await select.evaluate(e => Array.from(e.options).map(o => o.value));
      for (const value of choices) {
        await select.selectOption(value);
        if (!(await dialog.innerText()).replace(/\s+/g, ' ').includes('No other writable branches are available.')) throw new Error('Use the single-branch QA fixture');
        const buttons = await dialog.getByRole('button').evaluateAll(es => es.map(e => ({ disabled: e.disabled })));
        if (!buttons.at(-1).disabled) throw new Error('Bulk submit enabled without destination');
      }
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
      await all.uncheck();
      if (await reuse.isEnabled()) throw new Error('Bulk action remains enabled without selection');
      const first = scope.getByRole('checkbox', { name: `Select ${rows[0].name}`, exact: true });
      await first.check();
      await scope.getByRole('button', { name: 'Services', exact: true }).click();
      await waitNames(rows.filter(row => row.kind === 'service').map(row => row.name));
      if (await reuse.isEnabled()) throw new Error('Selection survived a filter change');
      await scope.getByRole('button', { name: 'All items', exact: true }).click();
      await waitNames(ordered(rows, 'name').map(row => row.name));
      if (await first.evaluate(e => e.checked)) throw new Error('Old selection reappeared');
      return `Each of ${rows.length} row checkboxes toggled; page selection selected all; bulk count matched; all${choices.length} reuse modes blocked without writable destination; Cancel/clear/filter reset behaved correctly. No sharing performed.`;
    });
  }
  return { checks, cards, sortBatch, filters, previewBatch, bulk };
}
