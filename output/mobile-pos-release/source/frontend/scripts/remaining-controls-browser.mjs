// Run only from the CUA REPL with an already-bound tab. Never launches a browser.
import { readFile, writeFile } from 'node:fs/promises';

export async function resumeAudit(tab, root, inventoryPath) {
  const read = async name => JSON.parse(await readFile(`${root}/${name}`, 'utf8'));
  const inventory = JSON.parse(await readFile(inventoryPath, 'utf8'));
  const panels = await read('workspace-panels.json');
  const filters = await read('filter-options.json');
  let availability;
  try { availability = await read('workspace-availability.json'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; availability = []; }
  const save = (name, rows) => writeFile(`${root}/${name}`, JSON.stringify(rows, null, 2));
  const safeFilter = /filter|^sort |^group |rows per page|page size|^density$|^date range$|^time range$|^timeline scale$|^calendar view$|^zoom level$|^financial project$|^record type$/i;
  // These legacy URLs now render the real workspaces instead of the old mock pages.
  const currentHeadings = {
    'pms/product-launch': ['Product launch'],
    'pms/dependency-management': ['Gantt'],
    'pms/resource-planning': ['Workload'],
    'pms/agile-execution': ['Backlog'],
  };
  const headingMatchers = {
    'crm/leads': /^\s*Lead\s+workbench\s+\d+\s*$/i,
    'crm/potential-clients': /^\s*Potential\s+Clients\s+\d+\s*$/i,
    'crm/leads/workbench': /^\s*Lead\s+workbench\s+\d+\s*$/i,
    'pms/custom-fields': 'Custom fields, built around your work.',
  };
  const headingSelectors = {
    'pms/projects/new': 'h3',
    'pms/calendar': 'section[aria-label="Planner calendar"] h2',
    'pms/planner': 'section[aria-label="Planner calendar"] h2',
  };
  async function waitVisible(locator) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try { await locator.waitFor({ state: 'visible' }); return; }
      catch (error) {
        if (attempt === 2) throw error;
        // Observe before waiting again; never repeat a write after a timeout.
        await tab.playwright.domSnapshot();
      }
    }
  }
  async function navigate(path, purpose) {
    const route = inventory.find(r => r.path === path);
    if (!route?.headings?.length) throw new Error(`Missing observed heading for ${path}`);
    const href = `/${path}`;
    const alreadyThere = new URL(await tab.url()).pathname === href;
    const links = alreadyThere ? [] : await tab.playwright.locator('a[href]').evaluateAll(elements => elements.map(e => ({
      href: e.getAttribute('href'), visible: !!e.getClientRects().length, target: e.getAttribute('target'), download: e.hasAttribute('download'),
    })));
    if (alreadyThere) { /* Preserve the current page while rechecking its controls. */ }
    else if (links.some(link => link.href === href && link.visible && link.target !== '_blank' && !link.download)) {
      const link = tab.playwright.locator(`a[href=${JSON.stringify(href)}]`).filter({ visible: true }).first();
      try { await link.click(); }
      catch {
        await tab.playwright.domSnapshot();
        if (new URL(await tab.url()).pathname !== href) {
          await tab.goto(`http://127.0.0.1:1569/${path}?qa_audit=${purpose}`);
        }
      }
    } else {
      const url = `http://127.0.0.1:1569/${path}?qa_audit=${purpose}`;
      if (await tab.url() !== url) await tab.goto(url);
    }
    const alternatives = [...new Set(currentHeadings[path] || route.headings)].map(heading => Array.from(heading).filter(c => !/\s/.test(c))
      .map(c => c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s*'));
    await waitVisible(tab.playwright.locator('main').first());
    await tab.playwright.locator('main').first().press('Control+Home');
    const heading = tab.playwright.locator(headingSelectors[path] || 'h1').filter({ hasText: headingMatchers[path] || new RegExp(`^\\s*(?:${alternatives.join('|')})\\s*$`, 'i') }).filter({ visible: true }).first();
    await waitVisible(heading);
    return heading.innerText();
  }

  async function probeFilters(path) {
    const choices = await tab.playwright.locator('select[aria-label]').evaluateAll(elements => {
      const seen = {};
      return elements.map(e => {
        const name = e.getAttribute('aria-label');
        const instance = seen[name] || 0; seen[name] = instance + 1;
        return { name, instance, value: e.value, disabled: e.matches(':disabled'), state: e.getAttribute('data-choice-state'),
          excluded: !!e.closest('table,article,[role="dialog"],[role="row"]'),
          grid: e.closest('[data-grid-id]')?.getAttribute('data-grid-id'),
          options: Array.from(e.options).map(o => ({ value: o.value, label: o.label, disabled: o.disabled })) };
      }).filter(e => !e.excluded);
    });
    for (const filter of choices.filter(e => safeFilter.test(e.name))) {
      const context = { page: path, control: filter.name, instance: filter.instance, grid: filter.grid };
      if (filter.disabled) {
        filters.push({ ...context, result: 'disabled-in-current-state', evidence: 'Native control disabled; no selection attempted.' });
        continue;
      }
      const select = tab.playwright.locator(`select[aria-label=${JSON.stringify(filter.name)}]`).nth(filter.instance);
      const reveal = async () => {
        const ancestors = await select.evaluate(e => {
          const all = Array.from(document.querySelectorAll('details')), result = [];
          for (let p = e.parentElement; p; p = p.parentElement) if (p.tagName === 'DETAILS' && !p.open) result.unshift(all.indexOf(p));
          return result;
        });
        for (const index of ancestors) await tab.playwright.locator('details').nth(index).locator('summary').first().click();
      };
      await reveal();
      if (filter.state === 'loading') {
        try { await select.locator('option').filter({ hasText: /^Loading/ }).waitFor({ state: 'detached' }); }
        catch { filters.push({ ...context, result: 'needs-review', evidence: 'Choice source is still loading; no placeholder was tested as an option.' }); continue; }
        filter.options = await select.evaluate(e => Array.from(e.options).map(o => ({ value: o.value, label: o.label, disabled: o.disabled })));
        filter.value = await select.evaluate(e => e.value);
      }
      if (!await select.evaluate(e => !!e.getClientRects().length)) {
        filters.push({ ...context, result: 'not-exposed-current-layout', evidence: 'Native control is hidden in this responsive layout.' });
        continue;
      }
      for (const option of filter.options.filter(o => !o.disabled)) {
        try {
          await reveal();
          await select.selectOption(option.value);
          await select.locator('option:checked').filter({ hasText: option.label }).waitFor({ state: 'attached' });
          const value = await select.evaluate(e => e.value);
          filters.push({ ...context, option: option.label,
            result: value === option.value ? 'passed' : 'needs-review', evidence: `Selected value ${value}; this check does not assert server-side filtering.` });
        } catch (error) {
          filters.push({ ...context, option: option.label, result: 'needs-review', evidence: String(error).slice(0, 300) });
          break;
        }
        await save('filter-options.json', filters);
      }
      try { await reveal(); await select.selectOption(filter.value); } catch { /* Keep the failure recorded above. */ }
    }
    await save('filter-options.json', filters);
  }

  async function panel(path) {
    await waitVisible(tab.playwright.getByRole('button', { name: 'Team workspace', exact: true }));
    await tab.playwright.getByRole('button', { name: 'Team workspace', exact: true }).click();
    const dialog = tab.playwright.getByRole('dialog', { name: 'Team workspace', exact: true });
    const workspace = dialog.getByRole('combobox', { name: 'Workspace', exact: true });
    await waitVisible(workspace);
    const errors = await dialog.getByRole('alert').allTextContents({});
    await tab.playwright.getByRole('button', { name: 'Close team workspace', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    return { page: path, control: 'Team workspace open/load/close', result: errors.length ? 'failed' : 'passed',
      evidence: errors.length ? errors.join(';') : 'Workspace selector loaded; panel closed.' };
  }

  async function run(limit = 3) {
    const stop = Math.min(panels.length + limit, inventory.length);
    while (panels.length < stop) {
      const route = inventory[panels.length];
      let result;
      try {
        const heading = await navigate(route.path, 'heading-verified');
        const count = await tab.playwright.locator('button').filter({ hasText: /^Team workspace$/ }).count();
        result = count ? await panel(route.path) : { page: route.path, control: 'Team workspace availability', result: 'not-exposed-current-layout' };
        result.headingVerified = heading;
      } catch (error) {
        result = { page: route.path, control: 'Team workspace open/load/close', result: 'needs-review', evidence: String(error).slice(0, 300) };
      }
      panels.push(result);
      await save('workspace-panels.json', panels);
      if (result.headingVerified) await probeFilters(route.path);
    }
    return { routesProcessed: panels.length, total: inventory.length, filterEntries: filters.length, last: panels.at(-1) };
  }

  async function recheckPanel(path) {
    const heading = await navigate(path, 'recheck');
    const count = await tab.playwright.locator('button').filter({ hasText: /^Team workspace$/ }).count();
    const result = count ? await panel(path) : { page: path, control: 'Team workspace availability', result: 'not-exposed-current-layout' };
    result.headingVerified = heading;
    const previous = panels.find(r => r.page === path);
    if (previous) Object.assign(previous, result, {
      rechecked: true,
      previousEvidence: previous.evidence,
      evidence: result.evidence || 'Page heading verified; this layout does not expose a Team workspace button.',
    });
    await save('workspace-panels.json', panels);
    return result;
  }
  async function verifyAvailability(limit = 3) {
    const routes = panels.filter(r => r.result === 'not-present-in-inventory');
    const stop = Math.min(availability.length + limit, routes.length);
    while (availability.length < stop) {
      const route = routes[availability.length];
      await navigate(route.page, 'availability');
      const count = await tab.playwright.locator('button').filter({ hasText: /^Team workspace$/ }).count();
      let result;
      if (count) {
        result = await panel(route.page);
      } else {
        result = { page: route.page, control: 'Team workspace availability', result: 'not-exposed-current-layout', evidence: 'Page main rendered; no Team workspace button in the DOM.' };
      }
      availability.push(result);
      await save('workspace-availability.json', availability);
      await probeFilters(route.page);
    }
    return { checked: availability.length, total: routes.length, last: availability.at(-1) };
  }
  return { run, navigate, probeFilters, recheckPanel, verifyAvailability, panels, filters, availability };
}
