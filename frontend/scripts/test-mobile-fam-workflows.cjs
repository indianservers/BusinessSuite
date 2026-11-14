const {chromium,expect:base}=require('playwright/test');
const path=require('node:path');
const expect=base.configure({timeout:30000});
(async()=>{
 process.chdir(path.resolve(__dirname,'..'));
 const {createServer}=await import('vite');
 const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch();
 try{
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[],requests=[],writes=[];
 let failStatement=false,empty=false,failSave=false;
 const rule={id:7,version:3,name:'Office rent',bank_account_id:1,direction:'withdrawal',field:'description',operator:'contains',text:'RENT',counter_ledger_id:10,minimum:'20.00',maximum:'500.00',priority:15,active:true};
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/v1/**',async route=>{
 const req=route.request(),u=new URL(req.url()),p=u.pathname,m=req.method();let data={};
 if(p.includes('/financial-statements/')){requests.push(u.pathname+u.search);if(failStatement)return route.fulfill({status:503,json:{detail:'Statement temporarily unavailable'}});data={currency:'INR',from_date:'2026-01-01',to_date:'2026-11-08',basis:'Posted vouchers only',summary:{total_debit:'12500.00',total_credit:'12500.00',net_balance:'0.00'},items:empty?[]:[{ledger_id:1,ledger_code:'EXP-001',ledger_name:'Office rent and maintenance account',nature:'expense',opening_balance:'2500.00',debit:'12500.00',credit:'0.00',closing_balance:'15000.00',amount:'12500.00'}]};}
 else if(p.endsWith('/fam/exports')&&m==='POST'){writes.push({p,body:req.postDataJSON()});data={id:55};}
 else if(p.endsWith('/exports/55/download'))data={file_content:'Ledger,Amount\nOffice rent,12500.00\n'};
 else if(p.endsWith('/export/inspect'))data={headers:['Ledger','Amount'],rows:[['Office rent','12500.00']],rowNumbers:[2],sheets:['Sheet1'],sheet:'Sheet1',total:1,headerRow:1};
 else if(p.endsWith('/export/convert'))return route.fulfill({contentType:'text/csv',body:'Ledger,Amount\nOffice rent,12500.00\n'});
 else if(p.endsWith('/bank-rules/options'))data={ledgers:[{id:10,ledger_name:'Rent expense',nature:'expense',ledger_type:'general',active:true},{id:11,ledger_name:'Sales income',nature:'income',ledger_type:'general',active:true},{id:12,ledger_name:'Inactive expense',nature:'expense',ledger_type:'general',active:false},{id:13,ledger_name:'Tax expense',nature:'expense',ledger_type:'tax',active:true}]};
 else if(p.endsWith('/bank-accounts'))data={items:[{id:1,bank_name:'Business bank',account_number_masked:'XXXX1234'}]};
 else if(p.endsWith('/bank-statements'))data={items:[{id:8,bank_account_id:1,imported_file_name:'November statement.csv'}]};
 else if(p.endsWith('/8/preview'))data={suggestions:[{line_id:22,line_hash:'reviewed-hash',date:'2026-11-01',description:'RENT NOVEMBER',amount:'350.00',rule_id:7,rule_version:3,rule_name:'Office rent',counter_ledger_id:10}]};
 else if(p.endsWith('/22/apply')){writes.push({p,body:req.postDataJSON()});data={voucher_id:91};}
 else if(p.endsWith('/bank-rules')&&m==='GET')data=[rule];
 else if(p.includes('/bank-rules')&&['POST','PUT'].includes(m)){writes.push({p,body:req.postDataJSON()});if(failSave){failSave=false;return route.fulfill({status:503,json:{detail:'Rule save unavailable'}})}data=rule;}
 return route.fulfill({json:data});
 });
 await page.route('**/qa-mobile-fam**',r=>r.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module" src="/scripts/fixtures/mobile-fam-workflows.tsx"></script>'}));
 const url='http://127.0.0.1:'+server.httpServer.address().port+'/qa-mobile-fam';
 const closeCreation=async()=>{await page.getByRole('button',{name:'Close creation window',exact:true}).click();if(await page.getByRole('alertdialog').count())await page.getByRole('button',{name:'Discard Changes',exact:true}).click();};
 const noOverflow=async()=>expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 for(const width of [320,360,375,390,414,430,480]){
 await page.setViewportSize({width,height:844});await page.goto(url,{waitUntil:'domcontentloaded',timeout:90000});
 await expect(page.getByText('Posted vouchers only',{exact:false})).toBeVisible();await noOverflow();
 const report=page.locator('.fam-statement-filters select');
 expect(await report.evaluate(el=>parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
 await expect(page.getByRole('region',{name:'Statement rows, scroll for more columns'})).toBeVisible();
 const before=requests.length;await report.selectOption('balance_sheet');expect(requests.length).toBe(before);
 await page.getByRole('button',{name:'Run statement',exact:true}).click();await expect.poll(()=>requests.at(-1)).toContain('/balance_sheet');
 await expect(page.getByText('Office rent and maintenance account',{exact:true}).first()).toBeVisible();await noOverflow();
 }
 await page.getByLabel('From date',{exact:true}).fill('2026-02-01');await page.getByLabel('To date',{exact:true}).fill('2026-10-31');
 for(const type of ['trial_balance','ledger_report','profit_and_loss','balance_sheet']){await page.locator('.fam-statement-filters select').selectOption(type);await page.getByRole('button',{name:'Run statement',exact:true}).click();await expect.poll(()=>requests.at(-1)).toContain('/'+type+'?from_date=2026-02-01&to_date=2026-10-31');await expect(page.getByText('Office rent and maintenance account',{exact:true}).first()).toBeVisible();}
 await page.getByRole('button',{name:'Export statement CSV',exact:true}).click();const exp=page.getByRole('dialog',{name:'Export data',exact:true});await expect(exp.getByRole('checkbox',{name:'Ledger',exact:true})).toBeVisible();await exp.getByRole('button',{name:/^CSV/}).click();const downloaded=page.waitForEvent('download');await exp.getByRole('button',{name:'Download CSV',exact:true}).click();expect((await downloaded).suggestedFilename()).toBe('balance_sheet.csv');expect(writes.find(w=>w.p.endsWith('/fam/exports')).body).toEqual({export_type:'balance_sheet',export_format:'csv',filters_json:{from_date:'2026-01-01',to_date:'2026-11-08'}});await exp.getByRole('button',{name:'Close export',exact:true}).click();
 failStatement=true;await page.getByRole('button',{name:'Run statement',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Statement temporarily unavailable'})).toBeVisible();failStatement=false;empty=true;await page.getByRole('button',{name:'Run statement',exact:true}).click();await expect(page.getByText('No posted balances for this period.',{exact:true})).toBeVisible();empty=false;
 for(const width of [320,360,375,390,414,430,480]){
 await page.setViewportSize({width,height:844});await page.goto(url+'?rules',{waitUntil:'domcontentloaded',timeout:90000});await expect(page.getByRole('button',{name:'Edit Office rent',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Create bank rule',exact:true}).click();const form=page.locator('.fam-bank-rule-form');expect(await form.getByLabel('Rule name',{exact:true}).evaluate(el=>parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);await form.getByLabel('Rule name',{exact:true}).fill('Phone rule '+width);await form.getByLabel(/^Bank account/).selectOption('1');await form.getByLabel('Matching text',{exact:true}).fill('RENT');await form.getByLabel(/^Counter account/).selectOption('10');
 await expect(form.getByLabel('Active',{exact:true})).toBeVisible();await expect(form.getByLabel('Minimum amount',{exact:true})).toBeHidden();await form.locator('summary').click();await form.getByLabel('Minimum amount',{exact:true}).fill('20');await form.getByLabel('Maximum amount',{exact:true}).fill('500');await form.getByLabel('Priority (lower first)',{exact:true}).fill('0');await form.locator('summary').click();const before=writes.length;await form.getByRole('button',{name:'Create rule',exact:true}).click();await expect(form.getByLabel('Priority (lower first)',{exact:true})).toBeVisible();expect(writes.length).toBe(before);await form.getByLabel('Priority (lower first)',{exact:true}).fill('15');await noOverflow();await expect(form.getByRole('group',{name:'Bank rule actions',exact:true})).toBeInViewport();await form.getByRole('button',{name:'Create rule',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);expect(writes.at(-1).body).toMatchObject({name:'Phone rule '+width,bank_account_id:1,counter_ledger_id:10,minimum:'20',maximum:'500',priority:15,active:true,expected_version:0});
 }
 const form=page.locator('.fam-bank-rule-form');await page.getByRole('button',{name:'Edit Office rent',exact:true}).click();await expect(form.getByLabel('Rule name',{exact:true})).toHaveValue('Office rent');await form.getByLabel(/^Direction/).selectOption('deposit');await expect(form.getByLabel(/^Counter account/)).toHaveValue('');await expect(form.getByLabel(/^Counter account/).locator('option')).toHaveText(['Choose account','Sales income']);await form.getByLabel(/^Counter account/).selectOption('11');failSave=true;await form.getByRole('button',{name:'Save rule changes',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Rule save unavailable');await expect(form.getByLabel('Rule name',{exact:true})).toHaveValue('Office rent');await form.getByRole('button',{name:'Save rule changes',exact:true}).click();await expect(page.getByText('Bank rule saved.',{exact:true})).toBeVisible();expect(writes.at(-1).body).toMatchObject({direction:'deposit',counter_ledger_id:11,expected_version:3});await closeCreation();
 await page.getByRole('button',{name:'Edit Office rent',exact:true}).click();await form.getByRole('button',{name:'Cancel editing',exact:true}).click();await expect(form.getByLabel('Rule name',{exact:true})).toHaveValue('');
 await page.getByRole('button',{name:'Close creation window',exact:true}).click();if(await page.getByRole('alertdialog').count())await page.getByRole('button',{name:'Discard Changes',exact:true}).click();
 await page.getByLabel(/^Bank statement/).selectOption('8');await page.getByRole('button',{name:'Apply rule and post',exact:true}).click();await expect(page.getByRole('link',{name:'Open voucher',exact:true})).toHaveAttribute('href','/fam/vouchers/91');expect(writes.at(-1).body).toEqual({rule_id:7,expected_version:3,line_hash:'reviewed-hash'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.resolve(__dirname,'../../outputs/mobile-ux/fam-bank-rules-390.png'),fullPage:true});
 await page.goto(url+'?rules&limited',{waitUntil:'domcontentloaded',timeout:90000});await page.getByLabel(/^Bank statement/).selectOption('8');await expect(page.getByRole('button',{name:'Apply rule and post',exact:true})).toBeDisabled();await page.getByRole('button',{name:'Create bank rule',exact:true}).click();await expect(page.locator('.fam-bank-rule-form').getByRole('button',{name:'Create rule',exact:true})).toBeEnabled();
 await page.goto(url+'?rules&readonly',{waitUntil:'domcontentloaded',timeout:90000});await expect(page.getByRole('button',{name:'Edit Office rent',exact:true})).toBeDisabled();await page.getByRole('button',{name:'Create bank rule',exact:true}).click();await expect(page.locator('.fam-bank-rule-form').getByRole('button',{name:'Create rule',exact:true})).toBeDisabled();
 for(const width of [481,768,1024,1440])for(const suffix of ['', '?rules']){
 await page.setViewportSize({width,height:900});await page.goto(url+suffix,{waitUntil:'domcontentloaded',timeout:90000});await expect(page.getByRole('heading',{level:1})).toBeVisible();if(suffix)await expect(page.getByRole('button',{name:'Edit Office rent',exact:true})).toBeVisible();else await expect(page.getByText('Posted vouchers only',{exact:false})).toBeVisible();
 if(suffix)await page.getByRole('button',{name:'Create bank rule',exact:true}).click();await expect(page.locator('.mobile-disclosure')).toHaveCount(0);await expect(page.getByRole('region',{name:'Statement rows, scroll for more columns'})).toHaveCount(0);
 const capture=()=>page.locator(suffix?'.fam-bank-rule-form, .fam-bank-rule-form :is(label,input,select,button)':'main :is(form,label,input,select,button,.fam-statement-summary)').evaluateAll(nodes=>nodes.filter(n=>n.checkVisibility()).map(n=>{const s=getComputedStyle(n),r=n.getBoundingClientRect();return[n.tagName,s.fontSize,s.display,s.padding,r.width,r.height]}));
 const before=await capture();await page.locator('style[data-vite-dev-id$="/fam-mobile-workflows.css"]').evaluate(el=>el.media='not all');expect(await capture()).toEqual(before);
 }
 await page.goto(url+'?rules&cached-bank',{waitUntil:'domcontentloaded',timeout:90000});
 await expect(page.getByRole('button',{name:'Edit Office rent',exact:true})).toBeVisible();
 await expect(page.getByLabel(/^Bank statement/).locator('option')).toHaveText(['Select imported statement','November statement.csv']);
 await page.getByRole('button',{name:'Create bank rule',exact:true}).click();
 await expect(page.locator('.fam-bank-rule-form').getByLabel(/^Bank account/).locator('option')).toHaveText(['Select bank','Business bank · XXXX1234']);
 expect(errors).toEqual([]);console.log('PASS FAM: seven phone widths, report filters/all four types/export/error/empty, rules create/edit/cancel/validation/dependencies/retry, mocked reviewed posting and permission gates, desktop style parity, cached bank-page navigation');
 }finally{await browser.close();await server.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
