// CUA-only form option checks against an already-bound tab.
import { readFile, writeFile } from 'node:fs/promises';

export async function resumeFormAudit(tab, root) {
  let checks;
  try { checks = JSON.parse(await readFile(`${root}/form-options.json`, 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; checks = []; }
  const save = () => writeFile(`${root}/form-options.json`, JSON.stringify(checks, null, 2));
  async function currency(page, dialogName, label, limit = 8) {
    const dialog = tab.playwright.getByRole('dialog', { name: dialogName, exact: true });
    const trigger = dialog.getByRole('button', { name: label, exact: true });
    const list = tab.playwright.getByRole('listbox', { name: label, exact: true });
    if (!await list.count()) await trigger.click();
    const search = tab.playwright.getByRole('combobox', { name: `Search ${label.toLowerCase()}`, exact: true });
    await search.fill('');
    const choices = await list.getByRole('option').evaluateAll(es => es.map(e => ({
      code: e.querySelector('.font-semibold')?.textContent.trim(),
      name: e.querySelector('.text-muted-foreground')?.textContent.trim(),
    })));
    const pending = choices.filter(o => !checks.some(x => x.page === page && x.control === label && x.option === `${o.code} ${o.name}` && ['passed', 'fixed-and-passed'].includes(x.result)));
    for (const choice of pending.slice(0, limit)) {
      if (!await list.count()) await trigger.click();
      await search.fill(choice.code);
      await list.getByRole('option', { name: new RegExp(`^${choice.code}\\s`) }).click();
      const value = await trigger.textContent({});
      const result = value.includes(choice.code) ? 'fixed-and-passed' : 'needs-review';
      checks.push({ page, form: dialogName, control: label, option: `${choice.code} ${choice.name}`, result,
        evidence: `Searched and clicked the picker option. Trigger text: ${value}. This checks picker interaction, not a saved bank account.` });
      await save();
      if (result === 'needs-review') return { pending: pending.length, failed: choice.code, value };
    }
    return { total: choices.length, pending: Math.max(0, pending.length - limit) };
  }
  async function native(page, dialogName, panelName, label, start = 0, limit = 75) {
    const dialog = tab.playwright.getByRole('dialog', { name: dialogName, exact: true });
    await dialog.getByRole('tab', { name: panelName, exact: true }).click();
    const select = dialog.getByRole('tabpanel', { name: panelName, exact: true }).locator(`select[aria-label=${JSON.stringify(label)}]`);
    const original = await select.evaluate(e => e.value);
    const options = await select.evaluate(e => Array.from(e.options).map(o => ({ value: o.value, label: o.text, disabled: o.disabled })));
    for (const option of options.slice(start, start + limit)) {
      if (option.disabled) continue;
      await select.selectOption(option.value);
      const value = await select.evaluate(e => e.value);
      checks.push({ page, form: dialogName, control: label, option: option.label,
        result: value === option.value ? 'passed' : 'needs-review',
        evidence: 'Selected native control value only; does not assert saved validation or searchable-popup interaction.' });
      await save();
    }
    await select.selectOption(original);
    return { total: options.length, next: Math.min(start + limit, options.length) };
  }
  return { checks, currency, native };
}
