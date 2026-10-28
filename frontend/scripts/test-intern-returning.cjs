// Run against a compiled portal: node scripts/test-intern-returning.cjs <dist>
// Verified identity/API fixtures keep this regression test off production data.
const { chromium, expect } = require('playwright/test');
const { existsSync, statSync } = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const dist = path.resolve(process.argv[2] || 'interns-hub/dist');
// Set INTERN_TEST_URL to verify deployed assets; all API calls remain mocked.
const origin = process.env.INTERN_TEST_URL || 'https://interns-hub.test';
const saved = {reference:'APP-EXISTING',status:'Pending',email:'returning@example.com',full_name:'Saved Applicant',details:{college:'Saved University',passout_year:2029},can_login:false};

(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    for (const scenario of ['new', 'Pending', 'Rejected', 'Correction Requested', 'Approved', 'MFA', 'Signed in']) {
      const context = await browser.newContext({viewport:{width:390,height:844}});
      await context.addInitScript(() => sessionStorage.setItem('internhub.application-access','verified-test-session'));
      if (scenario === 'Signed in') await context.addInitScript(() => {
        sessionStorage.removeItem('internhub.application-access');
        sessionStorage.setItem('internhub.session', 'test-access');
      });
      const page = await context.newPage();
      const errors = [];
      let submissions = 0, logins = 0;
      page.on('pageerror', error => errors.push(error.message));
      const record = scenario === 'new' ? null : {...saved,status:scenario === 'MFA' ? 'Approved' : scenario,can_login:['Approved','MFA'].includes(scenario),intern_id:scenario === 'Approved' ? 'IH-EXISTING' : undefined};
      await page.route(`${origin}/**`, async route => {
        const url = new URL(route.request().url());
        const pathname = url.pathname;
        const json = body => route.fulfill({json:body});
        if (pathname === '/config.js') return route.fulfill({contentType:'application/javascript',body:`window.__INTERNHUB_CONFIG__={apiBaseUrl:'${origin}/api/v1'};`});
        if (pathname.startsWith('/api/v1/')) {
          if (pathname.endsWith('/signup/session')) return json({email:saved.email,full_name:'Google Display Name',application:record});
          if (pathname.endsWith('/signup/login')) { logins++; return json(scenario === 'MFA' ? {mfa_required:true,mfa_token:'test-mfa'} : {access_token:'test-access',refresh_token:'test-refresh'}); }
          if (pathname.endsWith('/applications') && route.request().method() === 'POST') { submissions++; return json({}); }
          if (pathname.endsWith('/application-options')) return json({roles:['Software Development Intern'],today:'2026-10-27'});
          if (pathname.endsWith('/me')) return json({first_name:'Saved',last_name:'Applicant',employee_id:'IH-EXISTING',date_of_joining:'2026-10-01'});
          if (pathname.endsWith('/overview')) return json({total_tasks:0,completed:0,progress:0,score:null,streak:0,attendance_rate:0,reports:0,certificates:0});
          if (pathname.endsWith('/inbox-count')) return json({unacknowledged:0});
          return json([]);
        }
        if (process.env.INTERN_TEST_URL) return route.continue();
        const file = path.join(dist,pathname);
        return route.fulfill({path:existsSync(file) && statSync(file).isFile() ? file : path.join(dist,'index.html')});
      });
      await page.goto(`${origin}/apply`);
      if (scenario === 'new') {
        const years = page.locator('#application-passout_year');
        await expect(years).toBeVisible();
        for (const year of ['2027','2028','2029']) { await years.selectOption(year); await expect(years).toHaveValue(year); }
      } else if (scenario === 'Approved' || scenario === 'Signed in') {
        await expect(page).toHaveURL(`${origin}/`);
        await expect(page.getByRole('heading', {name:/Good .*Saved/})).toBeVisible();
        assert.equal(await page.evaluate(() => sessionStorage.getItem('internhub.session')),'test-access');
        assert.equal(logins,scenario === 'Signed in' ? 0 : 1);
      } else {
        await expect(page.getByRole('heading', {name:'You already submitted details'})).toBeVisible();
        await page.getByText('View your submitted details',{exact:true}).click();
        await expect(page.getByText('Saved University',{exact:true})).toBeVisible();
        assert.equal(await page.locator('#application-password').count(),0);
        if (scenario === 'MFA') { await expect(page.getByRole('button',{name:'Verify & Open Dashboard'})).toBeVisible(); assert.equal(logins,1); }
        else assert.equal(logins,0);
        if (scenario === 'Correction Requested') {
          await page.getByRole('link',{name:'Update requested details'}).click();
          await expect(page.locator('#application-college')).toHaveValue('Saved University');
          await expect(page.locator('#application-passout_year')).toHaveValue('2029');
        }
      }
      assert.equal(submissions,0);
      assert.deepEqual(errors,[]);
      console.log(`PASS ${scenario}: saved details, routing and duplicate prevention`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
