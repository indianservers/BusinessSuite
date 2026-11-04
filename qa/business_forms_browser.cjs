// Real HTTP/browser checks against the disposable fixture on :1564.
const {chromium,expect:raw}=require('../frontend/node_modules/playwright/test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const expect=raw.configure({timeout:30000}),origin='http://127.0.0.1:5202',root='http://127.0.0.1:1564/api/v1';
const output=path.resolve('.tmp/business-forms-qa');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const response=await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})});
 assert.equal(response.status,200);const login=await response.json();
 const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
 async function api(url,method='GET',body){const r=await fetch(root+url,{method,headers,body:body?JSON.stringify(body):undefined});const data=await r.json();assert.ok(r.ok,r.status+' '+url+': '+JSON.stringify(data));return data;}
 const actor=await api('/auth/me'),access=await api('/access/me'),browser=await chromium.launch();
 async function context(width){const c=await browser.newContext({viewport:{width,height:1000}});await c.addInitScript(({login,actor,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:actor.id,email:actor.email,role:'admin',is_superuser:true,access}},version:0}));},{login,actor,access});return c;}
 let page;
 try{
  for(const width of [1440,390,320]){
   const c=await context(width);page=await c.newPage();const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});
   await page.goto(origin+'/crm/vendors');await page.getByRole('button',{name:'Create vendor',exact:true}).click();
   const dialog=page.getByRole('dialog',{name:'Create vendor'}),name=dialog.getByRole('textbox',{name:'Company name *',exact:true});
   const title='Country-aware vendor '+width+' '+Date.now();await name.fill(title);
   const phone=dialog.getByRole('textbox',{name:'Company phone',exact:true});
   await phone.fill('9876543210');await phone.press('1');await expect(phone).toHaveValue('9876543210');
   await phone.evaluate(el=>{const data=new DataTransfer();data.setData('text/plain','98765 43210');el.select();el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));});
   await expect(phone).toHaveValue('9876543210');
   const number='987'+String(Date.now()).slice(-7);let storedNumber=number;await phone.fill(number);
   const countryButton=dialog.getByRole('button',{name:/Company phone country calling code/});
   const widths=await countryButton.evaluate(el=>({selector:el.getBoundingClientRect().width,row:el.parentElement.getBoundingClientRect().width}));assert.ok(widths.selector<widths.row*.42);
   await dialog.getByRole('tab',{name:'Legal & tax',exact:true}).click();await expect(dialog.getByLabel('Legal name',{exact:true})).toHaveValue(title);
   await dialog.getByRole('tab',{name:'Basic details',exact:true}).click();await expect(name).toHaveValue(title);await expect(phone).toHaveValue(number);
   if(width===390){
    await countryButton.click();await page.getByRole('combobox',{name:'Search company phone country',exact:true}).fill('United Arab Emirates');
    await page.getByRole('listbox',{name:'Country calling codes'}).getByRole('option',{name:/United Arab Emirates/}).click();storedNumber='50'+String(Date.now()).slice(-7);await phone.fill(storedNumber);await expect(phone).toHaveValue(storedNumber);
    await dialog.getByLabel('Country',{exact:true}).selectOption({value:'AE'},{force:true});
    await dialog.getByLabel('Business type',{exact:true}).selectOption({value:'llc'},{force:true});
   } else await dialog.getByLabel('Business type',{exact:true}).selectOption({value:'private_limited'},{force:true});
   await dialog.getByLabel('Vendor classification',{exact:true}).selectOption({label:'Service Provider'},{force:true});
   const footerFits=await dialog.locator('.md-dialog-footer').evaluate(el=>Array.from(el.querySelectorAll('button')).every(button=>button.scrollWidth<=button.clientWidth+1&&button.getBoundingClientRect().right<=el.getBoundingClientRect().right));assert.ok(footerFits,'All footer actions fit without clipped labels');
   await dialog.screenshot({path:path.join(output,'vendor-'+width+'.png')});
   if(width===320){
    const saved=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/master-data/companies'));
    await dialog.getByRole('button',{name:'Save & new',exact:true}).click();assert.equal((await saved).status(),201);
    await expect(dialog).toBeVisible();await expect(name).toHaveValue('');await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
   }else{
    await dialog.getByRole('button',{name:'Save vendor',exact:true}).click();await expect(dialog).toHaveCount(0);
   }
   const items=await api('/master-data/companies?role=Vendor&search='+encodeURIComponent(title));const stored=items.items.find(r=>r.name===title);assert.ok(stored);
   assert.equal(stored.phone,storedNumber);assert.equal(stored.vendorClassification,'Service Provider');
   await page.reload();assert.deepEqual(errors,[]);await c.close();
   console.log('PASS '+width+'px: phone cap, paste, country search, legal type, tab drafts, persisted vendor and '+(width===320?'Save & new':'save'));
  }
  const existingRun=Date.now();
  const existing=await api('/master-data/companies','POST',{name:'Existing customer '+Date.now(),roles:['Customer'],email:'existing-customer-'+existingRun+'@example.com'});
  const c=await context(1440);page=await c.newPage();await page.goto(origin+'/crm/vendors');await page.getByRole('button',{name:'Create vendor',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Create vendor'});await dialog.getByRole('textbox',{name:'Company name *',exact:true}).fill(existing.name);
  await dialog.getByRole('region',{name:'Existing company matches'}).getByRole('button').filter({hasText:existing.name}).click();
  await expect(dialog.getByLabel('Email',{exact:true})).toHaveValue('existing-customer-'+existingRun+'@example.com');
  await dialog.getByRole('button',{name:'Save vendor',exact:true}).click();await expect(dialog).toHaveCount(0);
  const same=await api('/master-data/companies/'+existing.id);assert.deepEqual(new Set(same.roles),new Set(['Customer','Vendor']));
  const matches=await api('/master-data/companies?search='+encodeURIComponent(existing.name));assert.equal(matches.items.length,1);
  await c.close();console.log('PASS existing customer adds Vendor without a duplicate identity or lost relationships');
 }catch(e){if(page&&!page.isClosed()){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error((await page.locator('body').innerText()).slice(-5000));}throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
