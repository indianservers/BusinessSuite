const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { build } = require('esbuild');
const { chromium, expect: baseExpect } = require('playwright/test');
const expect = baseExpect.configure({ timeout: 5000 });
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, '../backend/app/core/business_profiles.json'), 'utf8'));
const profile = key => ({ business_type: key, terms: { ...catalog.terms, ...catalog.profiles.find(item => item.id === key).terms } });
assert.equal(profile('hospital').terms.customer[0], 'Patient');
assert.equal(profile('restaurant').terms.customer[0], 'Guest');
assert.equal(profile('accounting_firm').terms.customer[0], 'Client');
assert.equal(profile('accounting_firm').terms.provider[0], 'Accountant');
assert.equal(profile('accounting_firm').terms.project[0], 'Engagement');
const source = `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter} from 'react-router-dom';
import {useBusinessTerms} from './src/hooks/use-business-terms';
import {setPackContext} from './src/lib/pack-context';
import {useAuthStore} from './src/store/authStore';
sessionStorage.setItem('suite-tenant','terminology-proof');sessionStorage.setItem('suite-organization','41');sessionStorage.setItem('suite-branch','3');
useAuthStore.setState({user:{id:11,email:'terms@example.invalid',role:'company_admin',access:{companyId:41,grants:{}}}});
function Probe(){const {term,routeLabel,profile,loading,error}=useBusinessTerms();return <section><output data-testid="customer">{term('customer')}</output><output data-testid="provider">{term('provider')}</output><output data-testid="appointment">{term('appointment')}</output><output data-testid="customerPlural">{term('customer',true)}</output><output data-testid="customerRoute">{routeLabel('/srm/customers','Customers')}</output><output data-testid="project">{term('project')}</output><output data-testid="business">{profile.business_type}</output><output data-testid="loading">{String(loading)}</output><output data-testid="error">{error?'error':'none'}</output></section>}
function Controls(){return <nav><button onClick={()=>setPackContext('11')}>Hospital</button><button onClick={()=>setPackContext('44')}>Salon</button><button onClick={()=>setPackContext('22')}>Restaurant</button><button onClick={()=>setPackContext('33')}>Accounts</button><button onClick={()=>setPackContext(null)}>Legacy</button><button onClick={()=>{sessionStorage.setItem('suite-pack-context','!malformed');sessionStorage.setItem('suite-business-pack-context','!malformed');window.dispatchEvent(new Event('suite:pack-context-changed'));}}>Malformed</button><button onClick={()=>cache.invalidateQueries({queryKey:['business-profile']})}>Refetch cached profile</button><button onClick={()=>window.dispatchEvent(new Event('suite:record-access-changed'))}>Refresh revoked access</button></nav>}
const cache=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
createRoot(document.getElementById('root')).render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={['/srm/appointments']}><Controls/><Probe/></MemoryRouter></QueryClientProvider>);
`;

(async () => {
  const bundle = await build({ stdin: { contents: source, resolveDir: root, loader: 'tsx' }, tsconfig: path.join(root, 'tsconfig.json'), bundle: true, write: false, format: 'iife', jsx: 'automatic', loader: { '.css': 'empty' }, define: { 'process.env.NODE_ENV': '"production"', 'import.meta.env': '{}' } });
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  const requests = [], errors = [];
  let delayHospital = false, hospitalRevoked = false, hospitalStarted, releaseHospital;
  const pending = [];
  try {
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://terms.test/api/v1/**', async route => {
      const request = route.request();
      assert.equal(request.method(), 'GET');
      assert.equal(new URL(request.url()).pathname, '/api/v1/access/settings/business-profile/effective');
      const headers = request.headers(), selected = headers['x-suite-pack-context'] || null;
      assert.equal(headers['x-suite-tenant'], 'terminology-proof');
      assert.equal(headers['x-suite-organization'], '41');
      assert.equal(headers['x-suite-branch'], '3');
      requests.push(selected);
      if (selected === '!malformed' || (selected === '11' && hospitalRevoked)) {
        return route.fulfill({ status: 403, json: { detail: 'Business Pack context unavailable' } });
      }
      const key = { 11: 'hospital', 22: 'restaurant', 33: 'accounting_firm', 44: 'salon' }[selected] || 'general';
      if (selected === '11' && delayHospital) {
        hospitalStarted();
        const wait = new Promise(resolve => { releaseHospital = resolve; });
        pending.push(wait);
        await wait;
      }
      try { await route.fulfill({ json: profile(key) }); } catch (error) {
        if (!request.failure() && !page.isClosed()) throw error;
      }
    });
    await page.route('http://terms.test/', route => route.fulfill({ contentType: 'text/html', body: '<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div>' }));
    await page.goto('http://terms.test/');
    await page.addScriptTag({ content: bundle.outputFiles[0].text });
    const check = async key => {
      const expected = profile(key);
      await expect(page.getByTestId('business')).toHaveText(key);
      for (const term of ['customer', 'provider', 'appointment', 'project']) await expect(page.getByTestId(term)).toHaveText(expected.terms[term][0]);
      await expect(page.getByTestId('customerPlural')).toHaveText(expected.terms.customer[1]);
      await expect(page.getByTestId('customerRoute')).toHaveText(expected.terms.customer[1]);
    };
    await check('general');
    await page.getByRole('button', { name: 'Hospital', exact: true }).click();
    await check('hospital');
    await page.getByRole('button', { name: 'Salon', exact: true }).click();
    await check('salon');
    await page.getByRole('button', { name: 'Restaurant', exact: true }).click();
    await check('restaurant');
    await page.getByRole('button', { name: 'Accounts', exact: true }).click();
    await check('accounting_firm');
    await page.getByRole('button', { name: 'Legacy', exact: true }).click();
    await check('general');
    // A fresh generation prevents the prior successful Hospital cache from masking this request.
    delayHospital = true;
    const started = new Promise(resolve => { hospitalStarted = resolve; });
    await page.getByRole('button', { name: 'Hospital', exact: true }).click();
    await Promise.race([started, new Promise((_, reject) => setTimeout(() => reject(Error('Hospital request did not begin after context switch')), 5000))]);
    await page.getByRole('button', { name: 'Salon', exact: true }).click();
    await check('salon');
    releaseHospital();
    await Promise.all(pending);
    await page.waitForTimeout(100);
    await check('salon');
    delayHospital = false;
    await page.getByRole('button', { name: 'Hospital', exact: true }).click();
    await check('hospital');
    hospitalRevoked = true;
    const deniedRequestCount = requests.length;
    await page.getByRole('button', { name: 'Refetch cached profile', exact: true }).click();
    await expect(page.getByTestId('error')).toHaveText('error');
    await check('general');
    assert.equal(requests.length - deniedRequestCount, 1, 'A denied cached refetch must fail closed without permission retries');
    hospitalRevoked = false;
    await page.getByRole('button', { name: 'Refetch cached profile', exact: true }).click();
    await check('hospital');
    hospitalRevoked = true;
    await page.getByRole('button', { name: 'Refresh revoked access', exact: true }).click();
    await expect(page.getByTestId('customer')).not.toHaveText(profile('hospital').terms.customer[0]);
    await expect(page.getByTestId('error')).toHaveText('error');
    await check('general');
    await page.getByRole('button', { name: 'Malformed', exact: true }).click();
    await expect(page.getByTestId('customer')).not.toHaveText(profile('hospital').terms.customer[0]);
    await expect(page.getByTestId('error')).toHaveText('error');
    await check('general');
    await page.getByRole('button', { name: 'Legacy', exact: true }).click();
    await check('general');
    for (const context of [null, '11', '22', '33', '44', '!malformed']) assert.ok(requests.includes(context), `Missing native header namespace ${context}`);
    assert.deepEqual(errors, []);
    console.log('Business Pack terminology: real hook/interceptor context switches, delayed response isolation, revoked/malformed403 and legacy fallback passed.');
  } finally {
    releaseHospital?.();
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
