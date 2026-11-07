// CUA only. Requires the explicitly disposable, generated catalog fixture.
import { readFile, writeFile } from 'node:fs/promises';

export async function resumeCatalogAudit(tab, root) {
  const file = `${root}/catalog-page-controls.json`;
  let checks;
  try { checks = JSON.parse(await readFile(file, 'utf8')).map(item => ({ page: 'crm/products', ...item })); }
  catch (error) { if (error.code !== 'ENOENT') throw error; checks = []; }
  const save = () => writeFile(file, JSON.stringify(checks, null, 2));
  const scope = tab.playwright.locator('.sc-page');
  const cards = () => scope.locator('.sc-card').evaluateAll(es => es.map(e => ({
    name: e.querySelector('.sc-card-title').textContent.trim(),
    kind: e.querySelector('.sc-kind').textContent.trim(),
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
  return { checks, cards, sortBatch, filters };
}
