// Exercise the compiled Google entry flow with verified-identity fixtures only.
const { chromium, expect } = require('playwright/test');
const { existsSync, statSync } = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const dist = path.resolve(process.argv[2] || 'interns-hub/dist');
const origin = process.env.INTERN_TEST_URL || 'https://interns-hub.test';

(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    for (const entry of ['/login', '/apply']) for (const scenario of ['new','Pending','Approved','MFA','Locked']) {
      const context = await browser.newContext();
      const page = await context.newPage();
      let logins=0, submissions=0, sessionReads=0;
      const errors=[];
      page.on('pageerror', error=>errors.push(error.message));
      const profile={email:'returning@example.com',full_name:'Saved Applicant',application_token:'verified-application-session',
        expires_at:Math.floor(Date.now()/1000)+7200,
        application:scenario==='new'?null:{status:scenario==='Pending'?'Pending':'Approved',email:'returning@example.com',
          full_name:'Saved Applicant',details:{college:'Saved University'},can_login:scenario!=='Pending'}};
      await page.route(`${origin}/**`, async route=>{
        const pathname=new URL(route.request().url()).pathname;
        const json=body=>route.fulfill({json:body});
        if(pathname==='/config.js') return route.fulfill({contentType:'application/javascript',body:`window.__INTERNHUB_CONFIG__={apiBaseUrl:'${origin}/api/v1',firebaseConfig:{projectId:'fixture',apiKey:'fixture',authDomain:'fixture.firebaseapp.com',appId:'fixture'}};`});
        // Replace only the OAuth popup boundary; keep the real compiled UI/API flow.
        if(/\/firebaseSignup-[^/]+\.js$/.test(pathname)) return route.fulfill({contentType:'application/javascript',body:`export async function firebaseSignup(){return (await fetch('${origin}/api/v1/interns-hub/signup/firebase',{method:'POST'})).json()}`});
        if(pathname.startsWith('/api/v1/')) {
          if(pathname.endsWith('/signup/providers')) return json({project_id:'fixture',providers:[{provider:'google',enabled:true}]});
          if(pathname.endsWith('/signup/firebase')) return json(profile);
          if(pathname.endsWith('/signup/session')) {sessionReads++;return json(profile);}
          if(pathname.endsWith('/signup/login')) {
            logins++;
            assert.equal(route.request().headers()['x-intern-application-token'],profile.application_token);
            if(scenario==='Locked') return route.fulfill({status:423,json:{detail:'Account is temporarily locked; please try again later'}});
            return json(scenario==='MFA'?{mfa_required:true,mfa_token:'fixture-mfa'}:{access_token:'fixture-access',refresh_token:'fixture-refresh'});
          }
          if(pathname.endsWith('/auth/mfa/verify')) {
            assert.deepEqual(route.request().postDataJSON(),{mfa_token:'fixture-mfa',method:'totp',code:'123456'});
            return json({access_token:'fixture-access',refresh_token:'fixture-refresh'});
          }
          if(pathname.endsWith('/applications')&&route.request().method()==='POST') {submissions++;return json({});}
          if(pathname.endsWith('/application-options')) return json({roles:['Software Development Intern'],today:'2026-11-09'});
          if(pathname.endsWith('/me')) return json({first_name:'Saved',last_name:'Applicant',employee_id:'IH-EXISTING'});
          if(pathname.endsWith('/overview')) return json({total_tasks:0,completed:0,progress:0,score:null,streak:0,attendance_rate:0,reports:0,certificates:0});
          if(pathname.endsWith('/inbox-count')) return json({unacknowledged:0});
          return json([]);
        }
        if(process.env.INTERN_TEST_URL) return route.continue();
        const file=path.join(dist,pathname);
        return route.fulfill({path:existsSync(file)&&statSync(file).isFile()?file:path.join(dist,'index.html')});
      });
      await page.goto(origin+entry,{waitUntil:'domcontentloaded'});
      const google=page.getByRole('button',{name:'Continue with Google',exact:true});
      await expect(google).toBeEnabled();
      assert.equal(await page.getByRole('button',{name:'Sign up with Google',exact:true}).count(),0);
      await google.click();
      if(scenario==='MFA') {
        await expect(page.getByLabel('Verification code')).toBeVisible();
        assert.equal(await page.evaluate(()=>sessionStorage.getItem('internhub.session')),null);
        await page.getByLabel('Verification code').fill('123456');
        await page.getByRole('button',{name:entry==='/login'?'Verify & Sign In':'Verify & Open Dashboard',exact:true}).click();
      }
      if(['Approved','MFA'].includes(scenario)) {
        await expect(page).toHaveURL(origin+'/');
        await expect(page.getByRole('heading',{name:/Good .*Saved/})).toBeVisible();
        assert.equal(await page.evaluate(()=>sessionStorage.getItem('internhub.session')),'fixture-access');
        assert.equal(logins,1);
        if(entry==='/login') assert.equal(sessionReads,0,'Approved users must sign in without the application-page detour');
      } else if(scenario==='Locked') {
        await expect(page.getByRole('alert').filter({hasText:'Account is temporarily locked'})).toBeVisible();
        assert.equal(await page.evaluate(()=>sessionStorage.getItem('internhub.session')),null);
        assert.equal(logins,1);
      } else {
        await expect(page).toHaveURL(origin+'/apply');
        if(scenario==='new') await expect(page.locator('#application-college')).toBeVisible();
        else await expect(page.getByRole('heading',{name:'You already submitted details'})).toBeVisible();
        assert.equal(logins,0);
      }
      assert.equal(submissions,0,'Google sign-in must not submit duplicate applications');
      assert.deepEqual(errors,[]);
      console.log(`PASS ${entry} ${scenario}: shared Google entry, approval checks and session handling`);
      await context.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
