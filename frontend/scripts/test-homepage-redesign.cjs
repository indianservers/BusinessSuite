const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium, expect } = require('playwright/test');

(async () => {
  const root = path.resolve(__dirname, '..');
  const fixture = path.join(__dirname, '.homepage-redesign.tsx');
  fs.writeFileSync(fixture, `import React from 'react';import{createRoot}from'react-dom/client';import{BrowserRouter,Routes,Route,useSearchParams}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Home from'@/pages/SuiteWelcomePage';import Login from'@/pages/auth/LoginPage';import Signup from'@/pages/auth/SignupPage';import{useAuthStore}from'@/store/authStore';import{loginDestination}from'@/lib/login';import'@/index.css';useAuthStore.setState({isHydrated:true,isAuthenticated:false,user:null});function Continue(){const[p]=useSearchParams();return <h1>Destination: {loginDestination(p.get('next'))}</h1>}createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Routes><Route path="/" element={<Home/>}/><Route path="/login" element={<Login/>}/><Route path="/signup" element={<Signup/>}/><Route path="/continue" element={<Continue/>}/></Routes></BrowserRouter></QueryClientProvider>);`);
  const { createServer } = await import('vite');
  const server = await createServer({ root, define: { 'import.meta.env.VITE_GOOGLE_ONE_TAP_CLIENT_ID': JSON.stringify('homepage-qa.apps.googleusercontent.com') }, server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1585, height: 1000 } });
  const page = await context.newPage();
  // Test the GIS lifecycle contract without impersonating an account or sending a credential.
  await context.addInitScript(() => {
    window.oneTapPrompts = 0;
    window.oneTapCancelled = 0;
    window.google = { accounts: { id: {
      initialize(options) { window.oneTapOptions = options; },
      prompt() { window.oneTapPrompts++; },
      cancel() { window.oneTapCancelled++; },
    } } };
  });
  const errors = [], calls = [];
  let allowLogin = false, configured = true;
  page.on('pageerror', error => errors.push(error.message));
  try {
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.pathname.startsWith('/api/v1/')) {
        const payload = request.postDataJSON();
        calls.push({ path: url.pathname, payload });
        let json = {}, status = 200;
        if (url.pathname.endsWith('/branding')) json = { company_name: 'QA organization' };
        else if (url.pathname.includes('/sso/')) json = [];
        else if (url.pathname.endsWith('/firebase/config')) json = { enabled: configured, modules: configured ? ['hrms','srm'] : [], firebase_config: configured ? { apiKey: 'fixture', projectId: 'fixture', authDomain: 'fixture.firebaseapp.com', appId: 'fixture' } : undefined };
        else if (url.pathname.endsWith('/signup/options')) json = { modules: [{ key: 'hrms', label: 'AI HRMS' }, { key: 'srm', label: 'Sales & POS' }] };
        else if (url.pathname.endsWith('/auth/login')) {
          if (allowLogin) json = { access_token: 'fixture-token', refresh_token: 'fixture-refresh', user_id: 1, email: payload.email, role: 'admin', is_superuser: false };
          else { status = 403; json = { detail: 'Your account is awaiting organization approval.' }; }
        } else if (url.pathname.endsWith('/status-link')) json = { message: 'If an application exists, a private status link has been sent.' };
        return route.fulfill({ status, json });
      }
      if (request.isNavigationRequest()) return route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.homepage-redesign.tsx');</script>` });
      return route.continue();
    });
    const base = server.resolvedUrls.local[0];
    await page.goto(base);
    await expect(page.locator('.home-app')).toHaveCount(7);
    await expect(page.getByRole('button', { name: 'Continue with Google', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Continue with Microsoft', exact: true })).toBeVisible();
    await expect.poll(() => page.evaluate(() => window.oneTapPrompts)).toBe(1);
    assert.equal(await page.evaluate(() => window.oneTapOptions.auto_select), false);
    await page.getByLabel('Email address', { exact: true }).focus();
    assert.ok(await page.evaluate(() => window.oneTapCancelled > 0));
    await page.reload();
    await expect(page.locator('.home-app')).toHaveCount(7);
    assert.equal(await page.evaluate(() => window.oneTapPrompts), 0, 'Do not repeat ambient prompt after reload');
    await page.getByRole('button', { name: 'People', exact: true }).click();
    await expect(page.locator('.home-app')).toHaveCount(2);
    await page.getByRole('button', { name: 'All apps', exact: true }).click();
    await page.getByRole('textbox', { name: 'Search applications', exact: true }).fill('calendar');
    await expect(page.locator('.home-app')).toHaveCount(1);
    await expect(page.locator('.home-app')).toHaveAttribute('aria-label', 'Schedule & Appointments');
    await page.getByRole('button', { name: 'Clear search' }).click();
    await page.getByRole('textbox', { name: 'Search applications', exact: true }).fill('no-matches');
    await expect(page.getByText('No applications match your search.')).toBeVisible();
    await page.getByRole('button', { name: 'Show all applications' }).click();
    for (const [name, destination] of [['Power Apps','/power-apps'],['AI HRMS','/hrms'],['VyaparaCRM','/crm'],['KaryaFlow PMS','/pms'],['Sales & POS','/srm'],['Finance & Accounting','/fam'],['Schedule & Appointments','/srm/appointments']]) {
      await page.getByRole('article', { name, exact: true }).getByRole('link', { name: 'Explore app' }).click();
      assert.equal(new URL(page.url()).searchParams.get('next'), destination);
    }
    await page.locator('.home-admin').click();
    assert.equal(new URL(page.url()).searchParams.get('next'), '/company-admin');
    await page.getByRole('article', { name: 'Schedule & Appointments' }).getByRole('link', { name: 'Explore app' }).click();
    await page.getByRole('button', { name: 'Get started' }).click();
    await expect(page.getByRole('tab', { name: 'Sign up', exact: true })).toHaveAttribute('aria-selected', 'true');
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Please check your application' })).toBeVisible();
    await page.getByLabel('Your name', { exact: true }).fill('Homepage QA');
    await page.getByLabel('Company name', { exact: true }).fill('Homepage QA Company');
    await page.getByLabel('Application email', { exact: true }).fill('homepage@example.test');
    await page.locator('#signup-phone').fill('9876543210');
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await page.getByRole('checkbox', { name: 'Sales & POS', exact: true }).check();
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await page.getByLabel('I understand access requires approval', { exact: false }).check();
    await page.getByRole('button', { name: 'Request trial access', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Request submitted' })).toBeVisible();
    const signupCall = calls.find(call => call.path.endsWith('/auth/signup'));
    assert.deepEqual(signupCall.payload.requested_modules, ['srm']);
    assert.equal(signupCall.payload.consent, true);
    await page.getByRole('link', { name: 'Check application status', exact: true }).click();
    assert.equal(new URL(page.url()).pathname, '/');
    assert.equal(new URL(page.url()).searchParams.get('next'), '/srm/appointments');
    await expect(page.locator('.suite-application-status')).toHaveAttribute('open', '');
    await page.getByLabel('Application email', { exact: true }).fill('homepage@example.test');
    await page.getByRole('button', { name: 'Email my application status link' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'private status link has been sent' })).toBeVisible();
    await page.getByRole('button', { name: 'Forgot password?', exact: true }).click();
    await page.getByLabel('Email address', { exact: true }).fill('homepage@example.test');
    await page.getByRole('button', { name: 'Send reset link' }).click();
    await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible();
    await page.getByRole('button', { name: 'Back to login' }).click();
    assert.equal(new URL(page.url()).pathname, '/');
    assert.equal(new URL(page.url()).searchParams.get('next'), '/srm/appointments');
    await page.getByRole('button', { name: 'Log in to workspace' }).click();
    await expect(page.getByText('Enter a valid email address.')).toBeVisible();
    await page.getByLabel('Email address', { exact: true }).fill('homepage@example.test');
    await page.getByLabel('Password', { exact: true }).fill('test-password');
    await page.getByRole('button', { name: 'Show password', exact: true }).click();
    await expect(page.locator('#password')).toHaveAttribute('type', 'text');
    await page.getByRole('button', { name: 'Log in to workspace' }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'awaiting organization approval' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Verify your identity' })).toHaveCount(0);
    allowLogin = true;
    await page.getByRole('button', { name: 'Log in to workspace' }).click();
    await expect(page.getByRole('heading', { name: 'Destination: /srm/appointments', exact: true })).toBeVisible();
    await page.goto(base + 'login?token=fixture-token&next=%2Fcrm');
    await page.getByLabel('New password', { exact: true }).fill('fixture-password');
    await page.getByLabel('Confirm new password', { exact: true }).fill('fixture-password');
    await page.getByRole('button', { name: 'Reset password', exact: true }).click();
    await expect(page.getByText('Password reset. Sign in with your new password.')).toBeVisible();
    assert.equal(new URL(page.url()).searchParams.get('next'), '/crm');
    configured = false;
    await page.goto(base);
    await expect(page.getByText('Social sign-in is unavailable. Use your email below.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Continue with Google', exact: true })).toBeDisabled();
    for (const width of [1585, 1280, 1024, 820, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      if (width <= 800 && !await page.getByRole('dialog').isVisible()) {
        const showAll = page.getByRole('button', { name: 'Show all 7 applications' });
        if (await showAll.isVisible()) await showAll.click();
        await page.getByRole('button', { name: 'Log in', exact: true }).click();
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}px`);
      await expect(page.locator('.home-app')).toHaveCount(7);
      await page.getByRole('tab', { name: 'Sign up', exact: true }).click();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Signup overflow at ${width}px`);
      await page.getByRole('tab', { name: 'Log in', exact: true }).click();
      await expect(page.getByRole('tab', { name: 'Log in', exact: true })).toHaveAttribute('aria-selected', 'true');
    }
    await page.getByRole('tab', { name: 'Log in', exact: true }).focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('tab', { name: 'Sign up', exact: true })).toBeFocused();
    await page.getByRole('button', { name: 'Close dialog' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByRole('button', { name: 'Show fewer' }).click();
    await expect(page.locator('.home-app')).toHaveCount(4);
    await expect(page.getByRole('article', { name: 'Schedule & Appointments' })).toBeVisible();
    assert.ok(await page.evaluate(() => document.documentElement.scrollHeight < 1000), 'Compact mobile home should stay below 1000px');
    await page.getByRole('article', { name: 'Schedule & Appointments' }).getByRole('link', { name: 'Explore app' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    assert.equal(new URL(page.url()).searchParams.get('next'), '/srm/appointments');
    assert.deepEqual(errors, []);
    console.log('PASS homepage: seven destinations, admin, search/categories, inline tabs and keyboard navigation, signup validation/submission/approval status, recovery/reset, denied and successful login without forced MFA, selected-app continuation, provider fallback, responsive widths 320–1585px. APIs stubbed; live provider credentials not exercised.');
  } finally {
    await context.close(); await browser.close(); await server.close(); fs.unlinkSync(fixture);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
