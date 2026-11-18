const path = require('node:path');
const fs = require('node:fs/promises');
const { chromium, expect: base } = require('playwright/test');
const expect = base.configure({ timeout: 20000 });
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen(); const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 900 } });
    await page.clock.setFixedTime(new Date('2026-11-09T09:00:00Z'));
    const errors = [], writes = [], reads = [], downloads = [];
    let fail = false, missing = false, deny = false, hold = false, release, denyPdf = false, holdPdf = false, releasePdf, dropHistory = false, actor = 1;
    const pdf = '%PDF-1.4\n% mocked payslip bytes\n%%EOF';
    page.on('pageerror', e => errors.push(e.message)); page.on('download', d => downloads.push(d));
    await page.addInitScript(() => {
      window.print = () => {
        const states = () => Array.from(document.querySelectorAll('.payslip-print details')).map(e => e.open);
        const before = states(); window.dispatchEvent(new Event('beforeprint')); const during = states(); window.dispatchEvent(new Event('afterprint'));
        window.__printSnapshot = { before, during, after: states() };
      };
    });
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), url = new URL(req.url()), p = url.pathname;
      if (req.method() !== 'GET') {
        const body = req.postDataJSON(); writes.push({ p, body });
        if (hold) await new Promise(resolve => release = resolve);
        await route.fulfill({ status: deny ? 403 : 200, json: deny ? { detail: 'Denied' } : { id: 30 } }); return;
      }
      reads.push({ p, params: Object.fromEntries(url.searchParams) });
      if (p.endsWith('/pdf')) {
        if (holdPdf) await new Promise(resolve => releasePdf = resolve);
        await route.fulfill({ status: denyPdf ? 403 : 200, contentType: denyPdf ? 'application/json' : 'application/pdf', body: denyPdf ? '{"detail":"Denied"}' : pdf }); return;
      }
      if (fail) { await route.fulfill({ status: 503, json: { detail: 'Unavailable' } }); return; }
      let data = [];
      if (p.endsWith('/my-payslips')) data = [
        ...Array.from({ length: 8 }, (_, i) => ({ id: i + 1, month: 11 - i, year: 2026, net_salary: '126200.40', currency: i === 1 ? 'USD' : 'INR', financial_year: '2026-27' })),
        ...(!dropHistory ? [1, 2].map(month => ({ id: 20 + month, month, year: 2025, net_salary: '65432.10', currency: 'INR', financial_year: '2025-26' })) : []),
      ];
      else if (p.endsWith('/payslip')) {
        if (missing) { await route.fulfill({ status: 404, json: { detail: 'Not published' } }); return; }
        const month = Number(url.searchParams.get('month')), year = Number(url.searchParams.get('year'));
        data = { payroll_record_id: year * 100 + month, currency: month === 10 ? 'USD' : 'INR', payroll_status: 'Locked', employee: { first_name: actor === 1 ? 'QA' : 'Other', last_name: 'Employee', employee_id: 'EMP' + actor }, working_days: 22, gross_salary: '150000.55', total_deductions: '25000.25', net_salary: '126200.40', financial_year: '2026-27', ytd_period_label: 'Apr-Nov 2026', earnings: Array.from({ length: 8 }, (_, i) => ({ component_name: i === 7 ? 'LongProfessionalDevelopmentAndSpecialResponsibilityAllowance' : 'Earning ' + (i + 1), amount: '12345.67' })), deductions: [{ name: 'Income tax', amount: '25000.25' }], reimbursements: [{ name: 'Approved travel', amount: '1200.10' }], employer_contributions: [{ name: 'Employer PF', amount: '8000.20' }], ytd: { gross_salary: '1200000.55', total_deductions: '200000.25', net_salary: '1000000.30', tax: '120000.10', reimbursements: '9600.80', employer_contribution: '64001.60' } };
      }
      await route.fulfill({ json: data });
    });
    await page.route('**/my-payslips-mobile-qa*', r => r.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-my-payslips.tsx");</script>' }));
    const origin = 'http://127.0.0.1:' + server.httpServer.address().port;
    const go = async () => { await page.goto(origin + '/my-payslips-mobile-qa', { waitUntil: 'domcontentloaded', timeout: 90000 }); await expect(page.getByRole('heading', { name: 'My Payslips', exact: true })).toBeVisible(); await page.getByLabel('Payslip year', { exact: true }).fill('2026'); await page.getByLabel('Payslip month', { exact: true }).selectOption('11'); };
    const image = name => page.screenshot({ animations: 'disabled', path: path.resolve(__dirname, '../../outputs/mobile-ux/' + name + '.png') });
    const openDetails = async () => { const summary = page.locator('summary').filter({ hasText: 'Earnings, deductions & employee details' }); if (!await summary.evaluate(e => e.parentElement.open)) await summary.click(); };
    if (process.env.MOBILE_PAYSLIPS_BASELINE) { await go(); await expect(page.getByRole('button', { name: 'Download PDF', exact: true })).toBeVisible(); await image('my-payslips-before-390'); console.log('Captured payslip phone baseline.'); return; }
    for (const width of [320, 360, 375, 390, 414, 430, 480]) {
      await page.setViewportSize({ width, height: 900 }); await go();
      for (const label of ['Payslip month', 'Payslip year']) expect(await page.getByLabel(label, { exact: true }).evaluate(e => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
      await page.locator('summary').filter({ hasText: /^Available payslips$/ }).click();
      expect((await page.locator('summary').filter({hasText:/^Available payslips$/}).boundingBox()).height).toBeGreaterThanOrEqual(44);
      await expect(page.locator('.hrms-payslip-history-list button')).toHaveCount(10);
      await expect(page.getByLabel('Payslip financial year', { exact: true })).toBeVisible();
      await openDetails();expect(await page.getByLabel('Question about this payslip?',{exact:true}).evaluate(e=>parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
      for (const text of ['QA Employee', 'EMP1', 'LongProfessionalDevelopmentAndSpecialResponsibilityAllowance', 'Income tax', 'Approved travel', 'Employer PF']) await expect(page.getByText(text, { exact: true })).toBeVisible();
      await expect(page.locator('.hrms-payslip-ytd .grid > div')).toHaveCount(6);
      await expect(page.locator('.payslip-print')).toContainText('1,26,200.40');
      await expect(page.locator('.payslip-print')).toContainText('12,345.67');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    await page.setViewportSize({ width: 390, height: 900 }); await go();
    await page.getByLabel('Question about this payslip?', { exact: true }).fill(' Explain the travel amount ');
    await page.getByLabel('Payslip month', { exact: true }).selectOption('10');
    await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('');
    await expect(page.locator('.payslip-print')).toContainText('$1,26,200.40');
    await page.getByLabel('Question about this payslip?', { exact: true }).fill('October question');
    await page.getByLabel('Payslip month', { exact: true }).selectOption('11');
    await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue(' Explain the travel amount ');
    await go(); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue(' Explain the travel amount ');
    deny = true; await page.getByRole('button', { name: 'Send query to Payroll', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Your question is retained' })).toBeVisible();
    deny = false; hold = true; release = undefined;
    await page.getByRole('button', { name: 'Send query to Payroll', exact: true }).click();
    for (const label of ['Payslip month', 'Payslip year', 'Question about this payslip?']) await expect(page.getByLabel(label, { exact: true })).toBeDisabled();
    await expect.poll(() => typeof release).toBe('function'); release(); hold = false;
    await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('');
    expect(writes.at(-1)).toEqual({ p: '/api/v1/payroll/payslip-queries', body: { payroll_record_id: 202611, subject: 'Payslip query: Nov 2026', description: 'Explain the travel amount', priority: 'Medium' } });
    denyPdf = true; await page.getByRole('button', { name: 'Download PDF', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'PDF could not download' })).toBeVisible();
    denyPdf = false; const downloadPromise = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download PDF', exact: true }).click(); const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('payslip-2026-11.pdf'); const target = path.resolve(__dirname, '../../outputs/mobile-ux/mock-payslip-download.pdf'); await download.saveAs(target); expect(await fs.readFile(target, 'utf8')).toBe(pdf);
    await page.getByRole('button', { name: 'Print', exact: true }).click();
    const print = await page.evaluate(() => window.__printSnapshot); expect(print.during.length).toBeGreaterThan(0); expect(print.during.every(Boolean)).toBe(true); expect(print.after).toEqual(print.before); await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));await page.emulateMedia({media:'print'});await expect(page.getByText('LongProfessionalDevelopmentAndSpecialResponsibilityAllowance',{exact:true})).toBeVisible();await expect(page.getByText('Employer PF',{exact:true})).toBeVisible();await page.emulateMedia({media:'screen'});await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));expect(await page.locator('.payslip-print details').evaluateAll(nodes=>nodes.map(e=>e.open))).toEqual(print.before);
    await page.locator('summary').filter({ hasText: /^Available payslips$/ }).click();
    await page.getByLabel('Payslip financial year', { exact: true }).selectOption('2025-26'); await expect(page.locator('.hrms-payslip-history-list button')).toHaveCount(2);
    dropHistory = true; await page.getByRole('button', { name: 'Load Payslip', exact: true }).click();
    await expect(page.getByText(/^No payslips match this financial year\./)).toBeVisible(); await page.getByRole('button', { name: 'Show all financial years', exact: true }).click(); await expect(page.locator('.hrms-payslip-history-list button')).toHaveCount(8); dropHistory = false;
    const readCount = reads.length; await page.getByLabel('Payslip year', { exact: true }).fill('2026.5'); await expect(page.getByRole('button', { name: 'Load Payslip', exact: true })).toBeDisabled(); await expect(page.getByText('Enter a whole year from 2020 to 2100.', { exact: true })).toBeVisible(); expect(reads.length).toBe(readCount);
    await page.getByLabel('Payslip year', { exact: true }).fill('2026'); await expect(page.getByRole('button', { name: 'Download PDF', exact: true })).toBeVisible();
    await page.getByLabel('Question about this payslip?', { exact: true }).fill('My private draft'); actor = 2; await page.evaluate(() => window.__payslipsQa.setActor(2));
    await expect(page.getByText('Other Employee', { exact: true })).toHaveCount(1); await expect(page.getByText('QA Employee', { exact: true })).toHaveCount(0); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('');
    actor = 1; await page.evaluate(() => window.__payslipsQa.setActor(1)); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('My private draft');
    await page.evaluate(() => window.__payslipsQa.setBranch('another')); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue(''); await page.evaluate(() => window.__payslipsQa.setBranch('')); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('My private draft');
    holdPdf = true; releasePdf = undefined; const downloadCount = downloads.length; await page.getByRole('button', { name: 'Download PDF', exact: true }).click(); await expect.poll(() => typeof releasePdf).toBe('function'); actor = 2; await page.evaluate(() => window.__payslipsQa.setActor(2)); releasePdf(); holdPdf = false; await expect(page.getByText('Other Employee', { exact: true })).toHaveCount(1); await page.getByRole('button', { name: 'Load Payslip', exact: true }).click(); await page.waitForLoadState('networkidle'); expect(downloads.length).toBe(downloadCount);
    actor = 1; await page.evaluate(() => window.__payslipsQa.setActor(1)); deny=true; await page.getByRole('button',{name:'Send query to Payroll',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Your question is retained'})).toBeVisible();deny=false; await page.getByRole('button', { name: 'Discard query draft', exact: true }).click(); await page.getByRole('button', { name: 'Continue editing', exact: true }).click(); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('My private draft'); await page.getByRole('button', { name: 'Discard query draft', exact: true }).click(); const beforeDiscard = writes.length; await page.getByRole('button', { name: 'Discard draft', exact: true }).click(); await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue(''); expect(writes.length).toBe(beforeDiscard);await expect(page.getByRole('alert').filter({hasText:'Your question is retained'})).toHaveCount(0);
    fail = true; await go(); await expect(page.getByRole('alert').filter({ hasText: 'Could not load your payslip' })).toBeVisible(); await expect(page.getByRole('button', { name: 'Retry payslip history', exact: true })).toBeVisible(); fail = false; await page.getByRole('button', { name: 'Retry', exact: true }).click(); await page.getByRole('button', { name: 'Retry payslip history', exact: true }).click(); await expect(page.getByRole('button', { name: 'Download PDF', exact: true })).toBeVisible();
    missing = true; await go(); await expect(page.getByText('No payslip available for Nov 2026.', { exact: true })).toBeVisible(); missing = false;
    await go(); while (await page.locator('[data-state="open"] [toast-close]').count()) await page.locator('[data-state="open"] [toast-close]').first().click(); await expect(page.locator('[toast-close]')).toHaveCount(0); await page.evaluate(() => scrollTo(0, 0)); await image('my-payslips-after-390'); await openDetails(); await image('my-payslips-details-after-390');
    for (const width of [481, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 }); await go(); await expect(page.getByRole('button', { name: 'Download PDF', exact: true })).toBeVisible(); await expect(page.locator('summary').filter({ hasText: /^Available payslips$/ })).toHaveCount(0); await expect(page.getByLabel('Payslip financial year', { exact: true })).toBeVisible();
      const geometry = () => page.locator('.hrms-my-payslips-page').evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }); const before = await geometry(); await page.evaluate(() => { for (const e of document.querySelectorAll('style')) if (e.getAttribute('data-vite-dev-id')?.endsWith('my-payslips-mobile.css')) e.disabled = true; }); expect(await geometry()).toEqual(before);
      await expect(page.getByLabel('Question about this payslip?', { exact: true })).toHaveValue('');
    }
    expect(errors).toEqual([]); console.log('PASS mypayslips7phones/fullhistory/fullcomponents+YTD/precisecurrency/16px/overflow;390perioddrafts+reload/403retry+pending/correctionpayload/PDFretry+bytes/printdetails/staleFY/invalidyear/actor+branch+latePDF/discard/sourceRetry+404;4desktop boundaries/originalhistory+disclosure/geometry. All Payroll query writes and PDFs mocked.');
  } finally { await browser.close(); await server.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
