const path = require('node:path');
const assert = require('node:assert/strict');
const esbuild = require('esbuild');
const { chromium } = require('playwright');

(async () => {
  const bundle = await esbuild.build({
    stdin: { contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import {MemoryRouter} from 'react-router-dom'; import {QueryClient,QueryClientProvider} from '@tanstack/react-query'; import Settings from './src/pages/settings/StarterValuesSettings'; const client=new QueryClient({defaultOptions:{queries:{retry:false}}}); const root=createRoot(document.getElementById('root')); window.show=(section)=>root.render(<QueryClientProvider client={client}><MemoryRouter><Settings key={section} section={section}/></MemoryRouter></QueryClientProvider>); window.show('starter-values');`, resolveDir: path.join(__dirname, '..'), loader: 'tsx' },
    bundle: true, write: false, format: 'iife', platform: 'browser', jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"', 'import.meta.env': '{}' },
    plugins: [{ name: 'fixture-services', setup(build) {
      build.onResolve({ filter: /^@\/services\/api$/ }, () => ({ path: 'api', namespace: 'fixture' }));
      build.onResolve({ filter: /^@\/lib\/form-defaults$/ }, () => ({ path: 'defaults', namespace: 'fixture' }));
      build.onLoad({ filter: /.*/, namespace: 'fixture' }, ({ path }) => ({ contents: path === 'defaults' ? `export const defaultsScope=()=> 'test-company';` : `
        let added=false; window.calls=[]; export const api={
          get:async(url)=>({data:url.endsWith('/catalog')?{groups:[{key:'hrms',title:'People & HR',values:['Casual Leave · 12 days/year','Basic Salary'],destination:'/settings/leaveTypes'}]}:{sources:['Website','Referral','Other'],defaults:['Website','Referral','Other']}}),
          post:async(url,body)=>{window.calls.push({url,body});const total=added?0:10;added=true;return {data:{total}}},
          put:async(url,body)=>{window.calls.push({url,body});if(body.sources.includes('Reject'))throw {response:{data:{detail:'Use unique source names'}}};return {data:{sources:body.sources.includes('Other')?body.sources:[...body.sources,'Other']}}}
        };` }));
    } }],
  });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage(); const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<style>*{box-sizing:border-box}body{font-family:Arial}textarea{width:100%;min-height:260px}article{border:1px solid #ddd;padding:20px}button{padding:10px;margin:6px}ul{padding-left:20px}</style><div id="root"></div>');
    await page.addScriptTag({ content: bundle.outputFiles[0].text });
    await page.getByRole('button', { name: 'Add starter values', exact: true }).click();
    await page.getByText('Added 10 starter records. You can edit them in Settings.').waitFor();
    await page.getByRole('button', { name: 'Add starter values', exact: true }).click();
    await page.getByText('Starter values are already configured. Existing values were preserved.').waitFor();
    assert.deepEqual(await page.evaluate(() => window.calls[0].body), { modules: ['hrms'] });
    assert.equal(await page.locator('a[href="/settings/salaryComponents"]').count(), 1);
    await page.evaluate(() => window.show('crm-lead-sources'));
    const sources = page.getByRole('textbox', { name: 'Lead sources', exact: true });
    await sources.fill('Website\nTrade Show');
    await page.getByRole('button', { name: 'Save sources', exact: true }).click();
    await page.getByText('Lead sources saved. New forms will use this list; existing records keep their source.').waitFor();
    assert.equal(await sources.inputValue(), 'Website\nTrade Show\nOther');
    await sources.fill('Reject'); await page.getByRole('button', { name: 'Save sources', exact: true }).click();
    await page.getByRole('alert').getByText('Use unique source names').waitFor();
    await page.getByRole('button', { name: 'Use starter list', exact: true }).click();
    assert.equal(await sources.inputValue(), 'Website\nReferral\nOther');
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    console.log('Starter settings browser checks passed: add, repeated apply, settings links, custom sources, server errors, starter list, mobile overflow.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
