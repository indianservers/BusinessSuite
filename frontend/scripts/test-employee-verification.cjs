// Real UI -> API handlers -> isolated SQL database. Invoked by pytest.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch();
  const output = path.resolve('../outputs/employee-verification');
  fs.mkdirSync(output, {recursive:true});
  try {
    for (const [width,employee,population] of [[1440,process.env.BGV_CURRENT,'current'],[390,process.env.BGV_FORMER,'former']]) {
      const page = await browser.newPage({viewport:{width,height:1000}});
      const errors = []; page.on('pageerror',e => errors.push(e.message));
      let queue = Promise.resolve();
      await page.route('**/api/v1/**',route => {
        queue = queue.then(async () => {
          const url = new URL(route.request().url());
          const response = await route.fetch({url:process.env.BGV_API+url.pathname+url.search,headers:{...route.request().headers(),'X-Suite-Organization':process.env.BGV_COMPANY,'X-Suite-Branch':process.env.BGV_BRANCH}});
          if(response.status() >= 400) console.log('API ERROR',url.pathname,response.status(),await response.text());
          await route.fulfill({response});
        });
        return queue;
      });
      await page.route('**/verification-qa?*',route => route.fulfill({contentType:'text/html',body:`<html><meta charset="utf-8"><body><div id="root"></div><script>window.__BGV_QA__=${JSON.stringify({token:process.env.BGV_TOKEN})}</script><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>(type)=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/employee-verification-harness.tsx');</script></body></html>`}));
      const url = `http://127.0.0.1:5198/verification-qa?employee_id=${employee}&population=${population}`;
      await page.goto(url,{waitUntil:'networkidle'});
      await page.getByRole('heading',{name:'Background verification & employee records'}).waitFor();
      await page.getByRole('button',{name:population==='former'?'Former employees':'Current employees',exact:true}).waitFor();
      for(const check of ['Education','Employment','Address']) await page.getByRole('checkbox',{name:check,exact:true}).uncheck();
      await page.getByRole('button',{name:'Create verification case',exact:true}).click();
      await page.getByLabel('Signed consent document',{exact:true}).waitFor();
      await page.getByLabel('Signed consent document',{exact:true}).selectOption({label:'Signed consent'});
      await page.getByRole('button',{name:'Record consent',exact:true}).click();
      await page.getByText('Consent: Captured',{exact:false}).waitFor();
      await page.getByLabel('Check status',{exact:true}).selectOption('Verified');
      await page.getByLabel('Existing employee document',{exact:true}).selectOption({label:'Signed consent'});
      await page.getByLabel('Verification findings and employee explanation',{exact:true}).fill('Identity checked against original source.');
      await page.getByRole('button',{name:'Save check',exact:true}).click();
      await page.getByText('Awaiting Review',{exact:false}).first().waitFor();
      await page.getByLabel('HR decision, employee response and discrepancy resolution',{exact:true}).fill('Reviewed sources and employee explanation.');
      await page.getByRole('button',{name:'Approve review and close case',exact:true}).click();
      await page.getByText('Reviewed sources and employee explanation.',{exact:false}).waitFor();
      await page.reload({waitUntil:'networkidle'});
      await page.getByText('Reviewed sources and employee explanation.',{exact:false}).waitFor();
      await page.getByRole('button',{name:'Show case history',exact:true}).click();
      await page.getByText('verification.reviewed',{exact:false}).waitFor();
      assert.equal(await page.getByRole('button',{name:'Create verification case',exact:true}).isVisible(), false);
      if(population==='former') await page.getByText('Exit record missing',{exact:true}).waitFor();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
      assert.deepEqual(errors,[]);
      await page.screenshot({path:path.join(output,`records-${width}.png`),fullPage:true});
      console.log(`PASS ${width}: ${population} employee, case creation, linked consent/evidence, review, persisted closure and history`);
      await page.close();
    }
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exit(1);});
