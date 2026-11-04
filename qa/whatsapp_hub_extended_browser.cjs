const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.WHATSAPP_QA_ORIGIN || 'http://127.0.0.1:5191';
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=', 'base64');
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1536, height: 1050 } });
    const errors = [], sends = [], uploads = [], followupWrites = [], analyticsRequests = [];
    let followups = [], imageLoads=0;
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: 'mock', refreshToken: 'mock', isAuthenticated: true, user: { id: 1, email: 'mock@example.test', role: 'admin', is_superuser: true } }, version: 0 })));
    const contact = { id: 1, recipient: '919999999999', name: 'Alex Morgan', entityType: 'contact', entityId: 4, consent: 'opted_in', serviceWindowOpen: true };
    const item = { key: 'whatsapp:1', kind: 'whatsapp', id: 1, name: 'Alex Morgan', phone: '+919999999999', branchId: 1, entityType: 'contact', entityId: 4, companyName: 'Acme', status: 'open', handoverNote: '', whatsappReadId: 0, emailReadId: 0, unread: 1, needsMatch: false, canManage: true, lastMessage: 'Review attached documents', lastAt: new Date().toISOString() };
    const media = [
      { id: '11', kind: 'image', mimeType: 'image/png', filename: 'customer.png' },
      { id: '12', kind: 'audio', mimeType: 'audio/mpeg', filename: 'voice.mp3' },
      { id: '13', kind: 'video', mimeType: 'video/mp4', filename: 'demo.mp4' },
      { id: '14', kind: 'document', mimeType: 'application/pdf', filename: 'quote.pdf' },
    ];
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname;
      let data = { items: [], pages: 1 };
      if (path.endsWith('/status')) data = { configured: true, canAdmin: true, webhookConfigured: true, connection: { businessName: 'Demo business', displayNumber: '+919000000000', status: 'connected' } };
      else if (path.endsWith('/engagement/inbox')) data = { items: [item], userId: 1 };
      else if (path.endsWith('/conversations/whatsapp/1')) data = { conversation: { ...item, whatsappContact: contact }, events: media.map((value, i) => ({ key: `wa:${i+1}`, id: i+1, channel: 'whatsapp', direction: 'inbound', body: 'Customer attachment', status: 'received', createdAt: new Date().toISOString(), media: value })), historyLimitPerSource: 300 };
      else if (path.endsWith('/conversations/1/context')) data = { linked: true, record: { entity: 'contacts', id: 4, name: 'Alex Morgan' }, canFollowUp: true, canViewFinance: true, sections: {}, followUps: followups, deals: [{ id: 7, name: 'Acme expansion', status: 'Open', amount: 15000, currency: 'INR', url: '/crm/deals/7' }], quotations: [{ id: 8, name: 'Q-008', status: 'Sent', amount: 15000, currency: 'INR', url: '/crm/quotations/8' }], invoices: [{ id: 9, name: 'INV-009', status: 'Overdue', amount: 15000, balance: 5000, currency: 'INR', dueAt: '2026-10-31', url: '/srm/invoices/9' }] };
      else if (path.endsWith('/pending/contacts/4')) data = { items: followups };
      else if (path.endsWith('/growth/follow-up') && request.method() === 'POST') {
        const value = request.postDataJSON(); followupWrites.push(value);
        followups = value.action === 'complete' ? [] : [{ id: 42, title: value.title, due_at: value.due_at, priority: 'Medium', channel: 'whatsapp' }];
        data = { message: 'Follow-up saved', activity_id: 42 };
      } else if (path.endsWith('/conversations/1/media') && request.method() === 'POST') {
        uploads.push(request.postDataBuffer()); data = { ...media[0], filename: 'shared.png', token: 'signed-test-upload-receipt', size: png.length };
      } else if (/\/messages\/\d+\/media$/.test(path)) {
        const id = Number(path.split('/').at(-2)); const value = media[id-1];
        if(id===1&&imageLoads++===0)return route.fulfill({status:502,json:{detail:'Synthetic download interrupted. Try again.'}});
        return route.fulfill({ contentType: value.mimeType, body: id === 1 ? png : Buffer.from(id === 4 ? '%PDF-1.4\n%%EOF' : 'mock-media') });
      } else if (path.endsWith('/whatsapp/messages') && request.method() === 'POST') {
        const value = request.postDataJSON(); sends.push(value); data = { id: 100, body: value.body, status: 'accepted', direction: 'outbound', kind: 'image', createdAt: new Date().toISOString() };
      } else if (path.endsWith('/whatsapp/analytics')) {
        analyticsRequests.push(url.searchParams.toString());
        data = { teams:[{id:3,name:'Sales'}], totals: { conversations: 261, newConversations: 14, received: 360, outbound: 500, sent: 475, delivered: 460, read: 425, failed: 25, pending: 0, pendingFollowUps: 12 }, statuses: {}, firstResponseSeconds: 300, firstResponseSamples: 42, daily: [{ date: '2026-11-03', received: 100, outbound: 150 }, { date: '2026-11-04', received: 260, outbound: 350 }], templates: [{ name: 'quotation_followup · en', statuses: { read: 425, failed: 25 } }], campaigns: [{ automationId: '8', statuses: { read: 50 } }], workload: [{ employeeId: 1, name: 'Sam', conversations: 261, open: 250, resolved: 11 }], notes: ['Resolution duration is unavailable because existing workflow records do not retain resolution transition times.'] };
      } else if (path.endsWith('/matches')) data = { status: 'linked', candidates: [] };
      else if (path.endsWith('/assignees')) data = { items: [{ id: 1, name: 'Sam' }] };
      await route.fulfill({ json: data });
    });
    await page.goto(origin + '/crm/whatsapp?conversation=1');
    await expect(page.getByRole('heading', { name: 'Alex Morgan', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Acme expansion', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Q-008', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'INV-009', exact: true })).toBeVisible();
    const attachment = page.locator('.wa-message-media');
    for (let i=0; i<4; i++) await attachment.nth(i).getByRole('button', { name: 'Load attachment', exact: true }).click();
    await expect(attachment.nth(0).getByRole('alert')).toHaveText('Synthetic download interrupted. Try again.');
    await attachment.nth(0).getByRole('button',{name:'Retry attachment',exact:true}).click();
    await expect(attachment.nth(0).locator('img')).toBeVisible();
    await expect(attachment.nth(1).locator('audio')).toHaveAttribute('controls', '');
    await expect(attachment.nth(2).locator('video')).toHaveAttribute('controls', '');
    await expect(attachment.nth(3).locator('iframe')).toHaveAttribute('title', 'PDF preview: quote.pdf');
    const downloadEvent = page.waitForEvent('download');
    await attachment.nth(0).getByRole('link', { name: /Download customer.png/ }).click();
    assert.equal((await downloadEvent).suggestedFilename(), 'customer.png');
    await page.getByRole('button', { name: 'Manage CRM follow-ups', exact: true }).click();
    let dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: /Follow up/ })).toBeVisible({timeout:60000});
    await expect(dialog.getByRole('combobox',{name:'Channel',exact:true})).toHaveValue('whatsapp');
    await dialog.getByRole('textbox',{name:'Purpose',exact:true}).fill('Review quotation');
    await dialog.getByRole('button', {name:'Tomorrow',exact:true}).click();
    await dialog.getByRole('button', {name:'Save follow-up',exact:true}).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('.wa-business-context').getByText('Review quotation', {exact:true})).toBeVisible();
    assert.equal(followupWrites[0].entity, 'contacts');assert.equal(followupWrites[0].record_id,4);
    await page.getByRole('button', { name: 'Manage CRM follow-ups', exact: true }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox',{name:'Action',exact:true}).selectOption('complete');
    await dialog.getByLabel('Existing follow-up',{exact:true}).selectOption('42');
    await dialog.getByRole('button', {name:'Save outcome & next step',exact:true}).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('.wa-business-context').getByText('No pending CRM follow-ups.',{exact:true})).toBeVisible();
    assert.equal(followupWrites[1].activity_id,42);
    await page.getByLabel('Attach WhatsApp file',{exact:true}).setInputFiles({ name:'shared.png', mimeType:'image/png', buffer:png });
    await expect(page.getByRole('button',{name:'Remove attachment',exact:true})).toBeVisible();
    await page.getByLabel('Message',{exact:true}).fill('Requested image');
    await page.getByRole('button',{name:'Send reply',exact:true}).click();
    await expect(page.getByRole('button',{name:'New message',exact:true}).last()).toBeVisible();
    assert.equal(uploads.length,1);assert.equal(sends.length,1);assert.equal(sends[0].media,'signed-test-upload-receipt');
    await page.screenshot({path:'docs/qa/whatsapp-hub-rich-context.png',fullPage:true});
    await page.getByRole('button',{name:'Analytics',exact:true}).click();
    await expect(page.getByRole('heading',{name:'WhatsApp performance',exact:true})).toBeVisible();
    await expect(page.getByText('261',{exact:true})).toBeVisible();
    await page.getByRole('combobox',{name:'Current conversation owner',exact:true}).selectOption('1');
    await expect.poll(()=>analyticsRequests.some(value=>value.includes('employee=1'))).toBe(true);
    await page.getByRole('combobox',{name:'Linked CRM record team',exact:true}).selectOption('3');
    await expect.poll(()=>analyticsRequests.some(value=>value.includes('team=3'))).toBe(true);
    const fromInput=page.getByLabel('From',{exact:true}),originalFrom=await fromInput.inputValue();
    await fromInput.fill('2099-01-01');await expect(page.getByRole('alert').filter({hasText:'Choose a valid date range'})).toBeVisible();await fromInput.fill(originalFrom);
    await page.screenshot({path:'docs/qa/whatsapp-hub-analytics.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Analytics mobile overflow');
    await page.screenshot({path:'docs/qa/whatsapp-hub-analytics-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS: authenticated media previews/download, inline deals/quotes/balances, shared CRM follow-up schedule/complete, attachment send payload, WhatsApp analytics/employee filter/mobile; all APIs mocked.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
