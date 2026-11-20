import {test,expect,type Page} from '../frontend/node_modules/playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
const output=resolve('../output/plan-ui-polish');mkdirSync(output,{recursive:true});
async function login(page:Page){
 await page.goto('/login?redirect=/srm/products-services');
 await page.getByPlaceholder('you@company.com').fill('browser-audit@example.com');await page.getByPlaceholder('Enter your password').fill('BrowserAudit@2026');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page).not.toHaveURL(/\/login/,{timeout:30000});await page.waitForFunction(()=>!location.pathname.includes('/continue')||document.querySelector('h1')?.textContent==='Choose your company');
 if(await page.getByRole('heading',{name:'Choose your company',exact:true}).isVisible())await page.getByRole('button',{name:/^Workflow Test Company/}).click();
 await page.waitForURL(url=>!url.pathname.includes('/continue'));await page.goto('/srm/products-services');await expect(page.getByRole('group',{name:'Catalog type',exact:true})).toBeVisible();
}
async function request(page:Page,path:string,body?:unknown){return page.evaluate(async({path,body})=>{
 const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
 const response=await fetch('/api/v1'+path,{method:body?'POST':'GET',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'},...(body?{body:JSON.stringify(body)}:{})});
 const data=await response.json();if(!response.ok)throw new Error(`${response.status}: ${JSON.stringify(data)}`);return data;
},{path,body});}
test('polished customer workspace, responsive layouts, theme and action windows',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});await login(page);
 const customer=await request(page,'/master-data/companies?source=crm',{name:'Alex Morgan · UI review '+Date.now(),entityKind:'Individual',roles:['Customer'],status:'Active'});
 const plans:any[]=[];
 for(const [index,name] of ['Studio Plus','Care Essentials','Workplace Access'].entries()){
  const offering=await request(page,'/catalog/items?source=srm',{kind:index===1?'subscription':'membership',name,code:'POLISH-'+Date.now()+'-'+index,price:index===1?1499:6999,currency:'INR',tax:0,status:'Active',plan:{duration:{unit:'month',count:6},activation:'purchase',tier:index===0?'Premium':'Standard',allow_pause:true,beneficiary_limit:1,benefits:[{key:'sessions',label:index===1?'Consultations':'Included sessions',type:'sessions',allowance:20,value:0},{key:'access',label:'Member access',type:'access',allowance:null,value:0}],renewal:{mode:'manual',reminder_days:[30,7,1]},billing:{mode:'prepaid',recurring:index===1,automation:false,interval_count:1,interval_unit:'month',timezone:'Asia/Kolkata'}}});
  const plan=await request(page,'/customer-plans?source=crm',{kind:offering.kind,offering_id:offering.id,customer_id:customer.id,request_key:'polish-issue-'+crypto.randomUUID()});plans.push(plan);
  if(index===0){const detail=await request(page,`/customer-plans/${plan.id}?source=crm`);await request(page,`/customer-plans/entitlements/${detail.benefits[0].id}/consume?source=crm`,{quantity:12,reference:'Studio visit · local UI review',request_key:'polish-usage-'+crypto.randomUUID()});}
 }
 for(const width of [1600,768,390]){
  await page.setViewportSize({width,height:width===390?844:1100});await page.goto(`/crm/customer-360?customer=${customer.id}`);await page.getByText('Memberships & subscriptions',{exact:true}).click();const workspace=page.locator('.cp-workspace');await workspace.getByRole('button',{name:'Studio Plus · Premium',exact:true}).click();const detail=page.getByRole('region',{name:'Selected customer plan'});await expect(detail).toContainText('8 of 20 sessions remaining');await expect(detail.getByRole('button',{name:'Renew',exact:true})).toBeEnabled();await expect(detail.getByRole('button',{name:'Activate',exact:true})).toBeDisabled();await expect(detail.getByText('Only pending plans need activation.',{exact:true}).first()).toHaveClass('sr-only');if(width===390){await detail.screenshot({path:resolve(output,`workspace-${width}.png`)});await page.screenshot({path:resolve(output,'mobile-viewport.png')});}else await workspace.screenshot({path:resolve(output,`workspace-${width}.png`)});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await detail.getByText('Action availability & plan changes',{exact:true}).click();await expect(detail.locator('.cp-help').filter({hasText:'Action availability & plan changes'}).getByText(/Only pending plans need activation/)).toBeVisible();await detail.getByText('Action availability & plan changes',{exact:true}).click();
  await detail.getByRole('button',{name:'Renew',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.getByLabel('New expiry date',{exact:true}).fill('2029-12-01');await expect(dialog.getByRole('button',{name:'Renew membership',exact:true})).toBeEnabled();await page.screenshot({path:resolve(output,`renewal-${width}.png`)});await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  if(width===1600){await page.evaluate(()=>document.documentElement.classList.add('dark'));await workspace.screenshot({path:resolve(output,'workspace-dark.png')});await page.evaluate(()=>document.documentElement.classList.remove('dark'));}
 }
 writeFileSync(resolve(output,'browser-errors.json'),JSON.stringify(errors,null,2));expect(errors).toEqual([]);
});
