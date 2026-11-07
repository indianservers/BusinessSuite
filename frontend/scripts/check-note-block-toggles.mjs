// Run through CUA only, on a saved disposable note with one plain paragraph.
import { writeFile } from 'node:fs/promises';

export async function checkNoteBlockToggles(tab, root) {
  const content = tab.playwright.getByRole('textbox', { name: 'Note content', exact: true });
  const original = await content.evaluate(element => element.innerHTML);
  if (!/^<p>[^<>]+<\/p>$/.test(original)) throw new Error('Use one plain paragraph as the QA fixture');
  const cases = [
    { name: 'Bulleted list', selector: 'ul:not([data-type])' },
    { name: 'Numbered list', selector: 'ol' },
    { name: 'Checklist', selector: 'ul[data-type="taskList"]' },
    { name: 'Block quote', selector: 'blockquote', more: true },
    { name: 'Code block', selector: 'pre', more: true },
  ];
  const checks = [];
  async function click(item) {
    if (item.more) {
      const menu = tab.playwright.locator('details:has(summary[aria-label="More formatting"])');
      if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
      await menu.getByRole('button', { name: item.name, exact: true }).click();
    } else await tab.playwright.getByRole('button', { name: item.name, exact: true }).click();
  }
  for (const item of cases) {
    await content.press('ControlOrMeta+a');
    await click(item);
    if (await content.locator(item.selector).count() !== 1) throw new Error(`Expected one ${item.name}`);
    await click(item);
    const restored = await content.evaluate(element => element.innerHTML);
    if (restored !== original) throw new Error(`${item.name} did not restore the original paragraph: ${restored}`);
    checks.push({ control: item.name, result: 'fixed-and-passed', evidence: 'Selected entire paragraph; first click created one block, second restored exact original paragraph without extra empty blocks.' });
    await writeFile(`${root}/note-block-toggle-controls.json`, JSON.stringify(checks, null, 2));
  }
  return checks;
}
