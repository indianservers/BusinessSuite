const {chromium,expect:baseExpect}=require('playwright/test');const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const {createServer}=await import('vite');const server=await createServer({root:require('node:path').resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{for(const mode of ['found','missing','ambiguous','denied','retry','race']){
 const page=await browser.newPage();let attempts=0,writes=0,releaseMatch,matchReleased=false;const matchHold=new Promise(resolve=>releaseMatch=resolve);const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.route('**/api/v1/**',async route=>{const request=route.request(),url=new URL(request.url()),p=url.pathname;let body={items:[],total:0,pages:1,canCreate:true};if(request.method()!=='GET')writes++;
 if(p.endsWith('/crm/leads'))body={items:[{id:4,full_name:'QA company lead',company_name:'Acme QA'}],total:1,pages:1};
 if(p.endsWith('/master-data/companies')&&!url.searchParams.has('exact_name')&&mode==='race')body={items:[{id:88,name:'Manual company'}],total:1,canCreate:true};
 if(p.endsWith('/master-data/companies')&&url.searchParams.has('exact_name')){attempts++;if(mode==='race'){await matchHold;matchReleased=true;}expect(url.searchParams.get('exact_name')).toBe('Acme QA');expect(url.searchParams.get('entity_kind')).toBe('companies');if(mode==='retry'&&attempts===1)return route.fulfill({status:503,json:{detail:'Temporary match failure'}});body={items:['found','retry','race'].includes(mode)?[{id:77,name:'Acme QA'}]:[],total:['found','retry','race'].includes(mode)?1:mode==='ambiguous'?2:0,canCreate:mode!=='denied'};}
 if(p.endsWith('/master-data/companies/88'))body={id:88,name:'Manual company',contacts:[]};
 if(p.endsWith('/master-data/companies/77'))body={id:77,name:'Acme QA',contacts:[]};
 if(p.endsWith('/permissions'))body={can_manual_probability:false};
 if(p.endsWith('/pipelines'))body={items:[{id:1,name:'Sales'}],total:1};
 if(p.endsWith('/pipeline-stages'))body={items:[{id:1,name:'New',pipeline_id:1}],total:1};
 if(p.includes('/custom-fields'))body={items:[],fields:[]};
 await route.fulfill({json:body}).catch(()=>{});});
 await page.goto(server.resolvedUrls.local[0]+'progress-deal-qa.html');await page.getByRole('button',{name:'Start new deal',exact:true}).click();const form=page.getByRole('dialog',{name:'Create deal',exact:true});await expect(form).toBeVisible();await form.getByPlaceholder('Enter deal name...').fill('User deal title');await form.getByRole('combobox',{name:'Search lead',exact:true}).fill('QA company lead');await form.getByRole('option',{name:/QA company lead/}).click();
 if(mode==='race'){await expect(form.getByText('Checking company Acme QA…',{exact:true})).toBeVisible();await form.getByRole('combobox',{name:'Search company',exact:true}).fill('Manual company');await form.getByRole('option',{name:/Manual company/}).click();releaseMatch();await expect.poll(()=>matchReleased).toBe(true);await expect(form.getByRole('combobox',{name:'Search company',exact:true})).toHaveValue('Manual company');}
 if(mode==='retry'){await expect(form.getByRole('button',{name:'Retry company match',exact:true})).toBeVisible();await form.getByRole('button',{name:'Retry company match',exact:true}).click();}
 if(mode==='found'||mode==='retry')await expect(form.getByRole('combobox',{name:'Search company',exact:true})).toHaveValue('Acme QA');
 if(mode==='missing'){const create=form.getByRole('button',{name:'Create company Acme QA',exact:true});await expect(create).toBeVisible();await create.click();await expect(page.getByRole('textbox',{name:/Company name/i})).toHaveValue('Acme QA');}
 if(mode==='ambiguous')await expect(form.getByText('More than one company matches Acme QA. Choose the correct company above.',{exact:true})).toBeVisible();
 if(mode==='denied'){await expect(form.getByText('No matching company found for Acme QA.',{exact:true})).toBeVisible();await expect(form.getByRole('button',{name:'Create company Acme QA',exact:true})).toHaveCount(0);}
 await expect(form.getByPlaceholder('Enter deal name...')).toHaveValue('User deal title');releaseMatch();expect(writes).toBe(0);expect(errors).toEqual([]);await page.close();
 }console.log('PASS lead company prefill: exact match, seeded create offer, ambiguous/denied guards, failure/retry, delayed-response guard and no automatic writes');
 }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
