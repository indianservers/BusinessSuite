const path = require('node:path');
const { chromium, expect: base } = require('playwright/test');
const expect = base.configure({ timeout: 20000 });
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen(); const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 900 } });
    const writes = [], reads = [], errors = [];
    let fail = false, failReplies = false, deny = false, hold = false, release;
    const tickets = Array.from({ length: 8 }, (_, i) => ({ id: i + 1, ticket_number: 'HD-' + (i + 1), subject: 'Ticket ' + (i + 1), description: 'Full original ticket description', category: { name: 'Payroll' }, priority: i === 0 ? 'Critical' : 'Medium', status: i === 1 ? 'Resolved' : i === 2 ? 'Closed' : 'Open', created_at: '2026-11-09T09:00:00Z', updated_at: '2026-11-09T10:00:00Z' }));
    const breaches = Array.from({ length: 8 }, (_, i) => ({ ...tickets[0], id: 101 + i, subject: 'Breach ' + (i + 1), ticket_number: 'SLA-' + (i + 1), resolution_due_at: '2026-11-08T09:00:00Z' }));
    const replies = Array.from({ length: 8 }, (_, i) => ({ id: i + 1, message: 'Full reply ' + (i + 1), is_internal: i === 0, created_at: '2026-11-09T10:00:00Z', author: { first_name: 'QA', last_name: 'Agent' } }));
    const repliesByTicket=new Map(tickets.map(ticket=>[ticket.id,structuredClone(replies)]));
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), url = new URL(req.url()), p = url.pathname;
      let data = [];
      if (req.method() !== 'GET') {
        const params = Object.fromEntries(url.searchParams);
        writes.push({ p, method: req.method(), body: req.postData() ? JSON.parse(req.postData()) : null, params });
        if (hold) await new Promise(resolve => release = resolve);
        if (deny) { await route.fulfill({ status: 403, json: { detail: 'Denied' } }); return; }
        const id = Number(p.match(/tickets\/(\d+)/)?.[1]), ticket = tickets.find(t => t.id === id);
        if (p.endsWith('/status')) { ticket.status = params.status; data = ticket; }
        else if (p.endsWith('/csat')) { ticket.satisfaction_rating = Number(params.rating); data = ticket; }
        else if (p.endsWith('/reply')) { data = { id: 9, message: params.message, is_internal: false, created_at: '2026-11-09T11:00:00Z' }; repliesByTicket.get(id).push(data); }
        else data = { id: 50 };
      } else {
        reads.push({ p, params: Object.fromEntries(url.searchParams) });
        if (fail || failReplies && p.endsWith('/replies')) { await route.fulfill({ status: 503, json: { detail: 'Unavailable' } }); return; }
        if (p.endsWith('/helpdesk/tickets')) data = tickets.filter(t => !url.searchParams.get('status') || t.status === url.searchParams.get('status'));
        else if (p.endsWith('/categories')) data = [{ id: 3, name: 'Payroll' }];
        else if (p.endsWith('/analytics')) data = { total: 8, open: 6, resolved: 1, sla_breached: 8, due_soon: 2, first_response_breached: 1, csat_average: 4.5, csat_responses: 12, by_status: { Open: 6, Resolved: 1, Closed: 1 } };
        else if (p.endsWith('/breaches')) data = breaches;
        else if (p.endsWith('/replies')) data = repliesByTicket.get(Number(p.match(/tickets\/(\d+)/)?.[1])) || [];
      }
      await route.fulfill({ json: data });
    });
    await page.route('**/helpdesk-mobile-qa*', r => r.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-helpdesk.tsx");</script>' }));
    const origin = 'http://127.0.0.1:' + server.httpServer.address().port;
    const go = async () => { await page.goto(origin + '/helpdesk-mobile-qa', { waitUntil: 'domcontentloaded', timeout: 90000 }); await expect(page.getByRole('heading', { name: 'Helpdesk', exact: true })).toBeVisible(); };
    const image = name => page.screenshot({ animations: 'disabled', path: path.resolve(__dirname, '../../outputs/mobile-ux/' + name + '.png') });
    const dismissToasts = async () => { while(await page.locator('[data-state="open"] [toast-close]').count())await page.locator('[data-state="open"] [toast-close]').first().click();await expect(page.locator('[toast-close]')).toHaveCount(0); };
    const openCreate = async () => { await page.getByRole('button', { name: 'New Ticket', exact: true }).click(); return page.getByRole('dialog', { name: 'Create support ticket', exact: true }); };
    const closeDetail = async () => { await page.getByRole('button', { name: 'Drag down or tap to close', exact: true }).click(); await expect(page.getByRole('dialog', { name: 'Ticket details', exact: true })).toHaveCount(0); };
    const openTicket = async id => { await page.getByLabel('Filter ticket status', { exact: true }).selectOption(''); await page.getByRole('button', { name: 'View details for ticket HD-' + id, exact: true }).click(); return page.getByRole('dialog', { name: 'Ticket details', exact: true }); };
    if (process.env.MOBILE_HELPDESK_BASELINE) {
      await go(); await expect(page.getByText('Breach 5', { exact: true })).toBeVisible(); await image('helpdesk-before-390');
      await openCreate(); await image('helpdesk-create-before-390'); console.log('Captured Helpdesk phone baseline.'); return;
    }
    for (const width of [320, 360, 375, 390, 414, 430, 480]) {
      await page.setViewportSize({ width, height: 900 }); await go();
      await expect(page.locator('.hrms-helpdesk-kpis .kf-card')).toHaveCount(6);
      await expect(page.getByLabel('Filter ticket status', { exact: true })).toHaveValue('Open');
      await page.locator('summary').filter({ hasText: 'SLA and queue analytics' }).click();
      await expect(page.getByText('Breach 8', { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const card=page.locator('[data-card-collection="apps/hrms/pages/helpdesk/HelpdeskPage:records-1"] .suite-record-card-shell').first();
      for(const button of await card.getByRole('button').all()){const rect=await button.boundingBox();expect(rect.width).toBeGreaterThanOrEqual(44);expect(rect.height).toBeGreaterThanOrEqual(44);}
      const priorityRect=await card.locator('[data-priority-badge]').boundingBox();
      for(const button of await card.locator('.suite-record-star').all()){const rect=await button.boundingBox();expect(rect.x+rect.width<=priorityRect.x||priorityRect.x+priorityRect.width<=rect.x||rect.y+rect.height<=priorityRect.y||priorityRect.y+priorityRect.height<=rect.y).toBe(true);}
      const create = await openCreate();
      for (const name of ['Ticket subject', 'Ticket category', 'Ticket priority']) {
        const input = create.getByLabel(name, { exact: true }); await expect(input).toBeVisible();
        expect(await input.evaluate(e => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
      }
      await expect(create.getByRole('textbox', { name: 'Description', exact: true })).toBeVisible(); expect(await create.getByRole('textbox',{name:'Description',exact:true}).evaluate(e=>parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16); await create.press('Escape');
      const detail = await openTicket(1);
      await expect(detail.getByText('Full original ticket description', { exact: true })).toBeVisible();
      await expect(detail.getByText('Full reply 8', { exact: true })).toBeVisible();
      await expect(detail.getByText('(Internal)', { exact: true })).toBeVisible();
      await expect(detail.getByLabel('Ticket status', { exact: true })).toBeVisible(); await expect(detail.getByRole('textbox', { name: 'Ticket reply', exact: true })).toBeVisible(); expect(await detail.getByRole('textbox',{name:'Ticket reply',exact:true}).evaluate(e=>parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await closeDetail();
    }
    await page.setViewportSize({ width: 390, height: 900 }); await go();
    let create = await openCreate(); await expect(create.getByLabel('Ticket priority', { exact: true })).toHaveValue('Medium');
    await create.getByLabel('Ticket subject', { exact: true }).fill('Payroll clarification');
    const beforeValidation = writes.length;
    await create.locator('.smart-create-footer').getByRole('button', { name: 'Raise Ticket', exact: true }).click();
    await expect(create.getByText('Required', { exact: true })).toBeVisible(); expect(writes.length).toBe(beforeValidation);
    await create.getByRole('textbox', { name: 'Description', exact: true }).fill('Full rich ticket description');
    await create.getByLabel('Ticket category', { exact: true }).selectOption('3');
    await create.getByLabel('Ticket priority', { exact: true }).selectOption('Critical');
    await create.press('Escape'); await expect(page.getByRole('alertdialog')).toContainText('Discard changes?');
    await page.getByRole('button', { name: 'Continue Editing', exact: true }).click();
    deny = true; await create.locator('.smart-create-footer').getByRole('button', { name: 'Raise Ticket', exact: true }).click();
    await expect(create.getByRole('alert')).toContainText('Your ticket details are retained');
    await expect(create.getByLabel('Ticket subject', { exact: true })).toHaveValue('Payroll clarification');
    deny = false; hold = true; release = undefined;
    await create.locator('.smart-create-footer').getByRole('button', { name: 'Raise Ticket', exact: true }).click();
    await expect(create.locator('.smart-create-footer button').last()).toBeDisabled(); await create.press('Escape'); await expect(create).toBeVisible();
    await expect.poll(() => typeof release).toBe('function'); release(); hold = false; await expect(create).toHaveCount(0);
    expect(writes.at(-1)).toMatchObject({ p: '/api/v1/helpdesk/tickets', method: 'POST', params: { subject: 'Payroll clarification', category_id: '3', priority: 'Critical' } });
    expect(writes.at(-1).params.description).toContain('Full rich ticket description'); expect(writes.at(-1).body).toBeNull();
    await dismissToasts(); create = await openCreate(); await expect(create.getByLabel('Ticket subject', { exact: true })).toHaveValue(''); await image('helpdesk-create-after-390'); await create.press('Escape');

    let detail = await openTicket(1);
    deny = true; await detail.getByLabel('Ticket status', { exact: true }).selectOption('Resolved');
    await expect(detail.getByRole('alert').filter({ hasText: 'Status could not update' })).toBeVisible();
    await expect(detail.getByLabel('Ticket status', { exact: true })).toHaveValue('Open');
    deny = false; hold = true; release = undefined;
    await detail.getByLabel('Ticket status', { exact: true }).selectOption('Resolved'); await expect(detail.getByLabel('Ticket status', { exact: true })).toBeDisabled();
    await detail.press('Escape'); await page.getByRole('button',{name:'Drag down or tap to close',exact:true}).click(); await expect(detail).toBeVisible(); await expect.poll(() => typeof release).toBe('function'); release(); hold = false;
    await expect(detail.getByLabel('Ticket status', { exact: true })).toHaveValue('Resolved');
    expect(writes.at(-1)).toMatchObject({ p: '/api/v1/helpdesk/tickets/1/status', method: 'PUT', body: null, params: { status: 'Resolved' } });
    await dismissToasts(); await detail.getByRole('textbox', { name: 'Ticket reply', exact: true }).fill('New rich reply');
    await detail.press('Escape'); await expect(page.getByRole('alertdialog')).toContainText('Discard unsent reply?');
    await page.getByRole('button', { name: 'Continue editing', exact: true }).click();
    deny = true; await detail.getByRole('button', { name: 'Send ticket reply', exact: true }).click();
    await expect(detail.getByRole('alert').filter({ hasText: 'Reply could not send' })).toBeVisible();
    await expect(detail.getByRole('textbox', { name: 'Ticket reply', exact: true })).toContainText('New rich reply');
    deny = false; hold = true; release = undefined; const beforeReply = writes.length;
    await detail.getByRole('button', { name: 'Send ticket reply', exact: true }).click();
    await expect(detail.getByRole('button', { name: 'Send ticket reply', exact: true })).toBeDisabled();
    await detail.getByRole('textbox', { name: 'Ticket reply', exact: true }).press('Control+Enter'); expect(writes.length).toBe(beforeReply + 1);
    await expect.poll(() => typeof release).toBe('function'); release(); hold = false;
    await expect(detail.getByRole('textbox', { name: 'Ticket reply', exact: true })).toHaveText('');
    expect(writes.at(-1)).toMatchObject({ p: '/api/v1/helpdesk/tickets/1/reply', method: 'POST', body: null, params: { is_internal: 'false' } });
    expect(writes.at(-1).params.message).toContain('New rich reply');
    await detail.getByLabel('Ticket status', { exact: true }).selectOption('Closed');
    await expect(detail.getByRole('textbox', { name: 'Ticket reply', exact: true })).toHaveCount(0);
    deny = true; await detail.getByRole('button', { name: 'Rate support 5 out of 5', exact: true }).click();
    await expect(detail.getByRole('alert').filter({ hasText: 'Rating could not save' })).toBeVisible();
    deny = false; hold = true; release = undefined;
    await detail.getByRole('button', { name: 'Rate support 5 out of 5', exact: true }).click();
    for (const rating of [1, 2, 3, 4, 5]) await expect(detail.getByRole('button', { name: `Rate support ${rating} out of 5`, exact: true })).toBeDisabled();
    await detail.press('Escape'); await page.getByRole('button',{name:'Drag down or tap to close',exact:true}).click(); await expect(detail).toBeVisible(); await expect.poll(() => typeof release).toBe('function'); release(); hold = false;
    await expect(detail.getByRole('button', { name: 'Rate support 5 out of 5', exact: true })).toBeEnabled();
    expect(writes.at(-1)).toMatchObject({ p: '/api/v1/helpdesk/tickets/1/csat', method: 'PUT', body: null, params: { rating: '5' } });
    await expect(detail.getByRole('button',{name:'Rate support 5 out of 5',exact:true})).toHaveAttribute('aria-pressed','true');await expect(detail.getByText('Saved rating: 5/5',{exact:true})).toBeVisible();await dismissToasts();await image('helpdesk-ticket-after-390');await detail.locator('.hrms-helpdesk-ticket-sheet').evaluate(e=>e.scrollTop=0);await image('helpdesk-ticket-header-after-390'); await closeDetail();
    await openTicket(8); await page.getByRole('textbox', { name: 'Ticket reply', exact: true }).fill('Discard this reply'); await page.getByRole('button',{name:'Drag down or tap to close',exact:true}).click();
    const beforeDiscard = writes.length; await page.getByRole('button', { name: 'Discard reply', exact: true }).click();
    await expect(detail).toHaveCount(0); expect(writes.length).toBe(beforeDiscard);
    failReplies = true; detail = await openTicket(8);
    await expect(detail.getByRole('alert').filter({ hasText: 'Conversation could not load' })).toBeVisible();
    failReplies = false; await detail.getByRole('button', { name: 'Retry conversation', exact: true }).click(); await expect(detail.getByText('Full reply 8', { exact: true })).toBeVisible(); await closeDetail();
    fail = true; await go(); await expect(page.getByRole('alert').filter({ hasText: 'Helpdesk information could not load' })).toBeVisible();
    await expect(page.getByText('No tickets found', { exact: true })).toHaveCount(0);
    await expect(page.getByText('No breached tickets right now.', { exact: true })).toHaveCount(0);
    await expect(page.locator('.hrms-helpdesk-kpis')).toContainText('—');
    create=await openCreate();await expect(create.getByRole('alert').filter({hasText:'Categories could not load'})).toBeVisible();
    fail=false;await create.getByRole('button',{name:'Retry categories',exact:true}).click();
    await expect(create.getByLabel('Ticket category',{exact:true}).getByRole('option',{name:'Payroll',exact:true})).toHaveCount(1);
    await expect(create.getByLabel('Ticket priority',{exact:true})).toHaveValue('Medium');await create.press('Escape');
    await page.getByRole('button', { name: 'Retry helpdesk', exact: true }).click(); await expect(page.getByRole('button', { name: 'View details for ticket HD-8', exact: true })).toBeVisible();
    while (await page.locator('[data-state="open"] [toast-close]').count()) await page.locator('[data-state="open"] [toast-close]').first().click();
    await expect(page.locator('[toast-close]')).toHaveCount(0); await page.evaluate(() => scrollTo(0, 0)); await image('helpdesk-after-390');
    for (const width of [481, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 }); await go(); await expect(page.getByText('Breach 5', { exact: true })).toBeVisible();
      await expect(page.getByText('Breach 6', { exact: true })).toHaveCount(0); await expect(page.locator('summary').filter({ hasText: 'SLA and queue analytics' })).toHaveCount(0);
      const geometry = () => page.locator('.hrms-helpdesk-page').evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
      const before = await geometry(); await page.evaluate(() => { for (const e of document.querySelectorAll('style')) if (e.getAttribute('data-vite-dev-id')?.endsWith('helpdesk-mobile.css')) e.disabled = true; }); expect(await geometry()).toEqual(before);
      await page.getByLabel('Filter ticket status', { exact: true }).selectOption(''); await page.getByText('Ticket 1', { exact: true }).click();
      await expect(page.getByText('Full reply 8', { exact: true })).toBeVisible(); await expect(page.getByRole('dialog', { name: 'Ticket details', exact: true })).toHaveCount(0);
      await openCreate(); await expect(page.locator('.smart-create-phone-sheet')).toHaveCount(0); await page.getByRole('dialog').press('Escape');
    }
    expect(errors).toEqual([]);
    console.log('PASS Helpdesk7phones all4createfields/richtext/16px/6KPIs/all8breaches/full8replies/overflow;390required/dirty/create403retry+pending/querypayload/reset; detail/status/reply/CSAT403retry+pending/payloads/dirtydiscard/readretry;4desktopboundaries CSSgeometry/5SLAcap/inline details/nonphonesheet. All support writes mocked.');
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
