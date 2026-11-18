const {chromium,expect:baseExpect}=require('playwright/test');const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const {createServer}=await import('vite');const server=await createServer({root:require('node:path').resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{for(const width of [390,1440]){
 const page=await browser.newPage({viewport:{width,height:900}});let fail=true,writes=0;const errors=[];
 const record={id:41,voucher_number:'JV-41',voucher_type_id:1,voucher_date:'2026-11-08',reference_number:'KEEP-41',narration:'Retain this voucher',status:'draft',lines:[{ledger_id:1,debit_amount:100,credit_amount:0},{ledger_id:2,debit_amount:0,credit_amount:100}]};
 page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.route('**/api/v1/**',async route=>{const request=route.request(),p=new URL(request.url()).pathname;let body={items:[]};
 if(p.endsWith('/voucher-types'))body={items:[{id:1,voucher_type_name:'Journal'}]};
 if(p.endsWith('/ledgers'))body={items:[{id:1,ledger_name:'Expense'},{id:2,ledger_name:'Bank'}]};
 if(p.endsWith('/vouchers/41'))body=record;
 if(p.endsWith('/vouchers/41/post')){writes++;if(fail)return route.fulfill({status:width===390?422:409,json:{detail:width===390?'Voucher date does not belong to a financial year':'Closed/locked financial year blocks posting'}});record.status='posted';body=record;}
 await route.fulfill({json:body});});
 await page.route('**/year-guidance-qa*',r=>r.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module" src="/scripts/fixtures/mobile-fam-voucher.tsx"></script>'}));
 await page.goto(server.resolvedUrls.local[0]+'year-guidance-qa?detail');const actions=page.getByRole('group',{name:'Voucher actions',exact:true});await expect(actions.getByRole('button',{name:'Post voucher',exact:true})).toBeEnabled();
 const post=async()=>{await actions.getByRole('button',{name:'Post voucher',exact:true}).click();await page.getByRole('alertdialog',{name:'Post this voucher?',exact:true}).getByRole('button',{name:'Post voucher',exact:true}).click();};
 await post();const link=page.getByRole('link',{name:'Open financial year settings (new tab)',exact:true});await expect(link).toHaveAttribute('href','/fam/financial-years');await expect(link).toHaveAttribute('target','_blank');await expect(page.getByLabel('Reference Number',{exact:true})).toHaveValue('KEEP-41');expect(record.status).toBe('draft');expect(writes).toBe(1);
 fail=false;await post();await expect.poll(()=>record.status).toBe('posted');await expect(link).toHaveCount(0);expect(writes).toBe(2);expect(errors).toEqual([]);await page.close();
 }console.log('PASS financial-year guidance: missing/locked year links from voucher errors, retained record, no automatic setup writes and successful retry at phone/desktop widths');
 }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
