const assert = require('node:assert/strict');
const path = require('node:path');
const { build } = require('esbuild');
const { chromium } = require('playwright');
(async () => {
  const root = path.resolve(__dirname, '..');
  const source = `import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter,useNavigate}from'react-router-dom';import Items from './src/shared/record-sync/RecordSyncItems';import{startRecordSync,finishRecordSync,recoverRecordSync}from './src/shared/record-sync/store';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({user:{id:1,email:'qa@example.test'}});window.seed=async()=>{const id=await startRecordSync({method:'post',url:'/fam/ledgers',data:{name:'Audit ledger'}},async()=>{});finishRecordSync(id,undefined,new Error('failed'));};window.recover=recoverRecordSync;function App(){window.navigate=useNavigate();return <Items floating/>};createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={['/fam/ledgers']}><App/></MemoryRouter>);`;
  const result = await build({stdin:{contents:source,loader:'tsx',resolveDir:root},bundle:true,write:false,format:'iife',platform:'browser',alias:{'@':path.join(root,'src')},define:{'import.meta.env':'{}'},loader:{'.css':'empty'}});
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    const errors=[];
    page.on('pageerror', error=>errors.push(error.message));
    page.on('dialog',()=>{throw new Error('Native confirmation must not interrupt modal focus');});
    await page.route('http://draft.test/**', route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.goto('http://draft.test/fam/ledgers');
    await page.addScriptTag({content:result.outputFiles[0].text});
    await page.evaluate(()=>window.seed());
    await page.locator('summary').click();
    await page.evaluate(()=>window.navigate('/crm/leads'));
    await page.getByRole('region',{name:'Browser-saved changes'}).waitFor({state:'detached'});
    await page.evaluate(()=>window.navigate('/fam/ledgers'));
    await page.locator('summary').click();
    await page.getByRole('button',{name:'Discard browser copy for Audit ledger'}).click();
    await page.getByRole('button',{name:'Keep copy',exact:true}).click();
    assert.equal(await page.getByText('Audit ledger',{exact:true}).count(),1);
    await page.getByRole('button',{name:'Discard browser copy for Audit ledger'}).click();
    await page.getByRole('button',{name:'Discard copy',exact:true}).click();
    await page.getByText('Audit ledger',{exact:true}).waitFor({state:'detached'});
    await page.evaluate(()=>window.recover());
    assert.equal(await page.getByText('Audit ledger',{exact:true}).count(),0);
    assert.deepEqual(errors,[]);
    console.log('PASS: page-scoped notices, keep, discard, durable removal, no native dialog or renderer errors');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
