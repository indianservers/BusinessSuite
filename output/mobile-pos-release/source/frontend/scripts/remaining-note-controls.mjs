// Use only through CUA with an already-bound tab and a disposable QA note.
import { readFile, writeFile } from 'node:fs/promises';

export async function resumeNoteAudit(tab, root) {
  let checks;
  try { checks = JSON.parse(await readFile(`${root}/note-controls.json`, 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; checks = []; }
  const save = () => writeFile(`${root}/note-controls.json`, JSON.stringify(checks, null, 2));
  const editor = tab.playwright.getByRole('region', { name: 'Private note editor', exact: true });
  async function openMove() {
    const menu = tab.playwright.locator('details:has(summary[aria-label="More note actions"])');
    if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
    await menu.getByRole('button', { name: 'Move note', exact: true }).click();
    return tab.playwright.getByRole('dialog', { name: 'Move selected notes', exact: true });
  }
  async function destinations() {
    const dialog = await openMove();
    const choices = await dialog.locator('select[aria-label="Move destination"]').evaluate(e => Array.from(e.options).filter(o => !o.disabled).map(o => ({ value: o.value, name: o.text })));
    await dialog.locator('select').press('Escape');
    await dialog.waitFor({ state: 'detached' });
    return choices;
  }
  async function moveBatch(choices, limit = 4) {
    const pending = choices.filter(c => !checks.some(x => x.control === `Move destination ${c.name}` && x.result === 'passed'));
    for (const choice of pending.slice(0, limit)) {
      const item = { page: 'pms/notes', control: `Move destination ${choice.name}`, result: 'passed' };
      try {
        const beforeText = await editor.innerText();
        const beforeVersion = Number(beforeText.match(/Version\s+(\d+)/)?.[1]);
        if (!beforeVersion) throw new Error('Saved note version is not visible');
        const originalContent = await editor.getByRole('textbox', { name: 'Note content', exact: true }).textContent({});
        const originalProject = await editor.locator('select[aria-label="Note project"]').evaluate(e => e.value);
        const originalFolder = await editor.locator('select[aria-label="Note folder"]').evaluate(e => e.value);
        const dialog = await openMove();
        await dialog.locator('select[aria-label="Move destination"]').selectOption(choice.value);
        await dialog.getByRole('button', { name: 'Move notes', exact: true }).click();
        await dialog.waitFor({ state: 'detached' });
        await editor.getByText(`Version ${beforeVersion + 1}`, { exact: true }).waitFor({ state: 'visible' });
        const expectedProject = choice.value.startsWith('project:') ? choice.value.split(':')[1] : 'personal';
        const expectedFolder = choice.value.startsWith('folder:') ? choice.value.split(':')[1] : '';
        const project = await editor.locator('select[aria-label="Note project"]').evaluate(e => e.value);
        const folder = await editor.locator('select[aria-label="Note folder"]').evaluate(e => e.value);
        if (project !== expectedProject || folder !== expectedFolder) throw new Error(`Unexpected destination ${JSON.stringify({ project, folder })}`);
        await tab.playwright.getByRole('region', { name: 'Last note action', exact: true }).getByRole('button', { name: 'Undo', exact: true }).click();
        await editor.getByText(`Version ${beforeVersion + 2}`, { exact: true }).waitFor({ state: 'visible' });
        if (await editor.locator('select[aria-label="Note project"]').evaluate(e => e.value) !== originalProject ||
          await editor.locator('select[aria-label="Note folder"]').evaluate(e => e.value) !== originalFolder ||
          await editor.getByRole('textbox', { name: 'Note content', exact: true }).textContent({}) !== originalContent) throw new Error('Undo did not restore original location/content');
        item.evidence = `Moved to ${choice.value}; visible version advanced ${beforeVersion}→${beforeVersion + 1}; confirmed project/folder; Undo advanced to ${beforeVersion + 2} and restored original location/content.`;
      } catch (error) { item.result = 'needs-review'; item.error = String(error); }
      checks.push(item); await save();
      if (item.result !== 'passed') return item;
    }
    return { total: choices.length, pending: Math.max(0, pending.length - limit) };
  }
  return { checks, destinations, moveBatch };
}
