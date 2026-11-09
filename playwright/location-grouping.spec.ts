import {test,expect} from '../frontend/node_modules/playwright/test';
import {authenticateCrm} from './crm-core-test-utils';
const locations=[['Telangana','Hyderabad','500001'],['Maharashtra','Pune','411001'],['Karnataka','Bengaluru','560001'],['Telangana','Hyderabad','500001'],['','','']];
const people=locations.map(([state,city,pincode],i)=>({id:i+1,full_name:`Location Person ${i+1}`,name:`Location Company ${i+1}`,state,city,pincode,country:'India',status:'New',roles:['Customer'],tags:[],version:1,details:{},signals:{active:true,ageDays:1,priority:0,nextAction:'Follow up',followUpLabel:'No follow-up'},first_name:'Location',last_name:`Employee ${i+1}`,employee_id:`LOC-${i+1}`,employment_type:'Full-time',date_of_joining:'2026-01-01',present_state:state,present_city:city,present_pincode:pincode}));
for(const [name,url] of [['Leads','/crm/leads'],['Potential customers','/crm/potential-clients'],['Customers','/crm/customers'],['Employees','/hrms/employees']])test(`${name}: State, City and PIN grouping`,async({page})=>{
 await authenticateCrm(page);
 await page.addInitScript(()=>{const stored=JSON.parse(sessionStorage.getItem('hrms-auth')||'{}');if(stored.state?.user){stored.state.user.access={managed:false,companyId:1,companyName:"CRM test company",grants:{},modules:[],isAccessAdmin:true,isGlobalAdmin:true,memberships:[1],organizations:[{id:1,name:"CRM test company"}]};sessionStorage.setItem('hrms-auth',JSON.stringify(stored));}});
 await page.route('**/api/v1/crm/lead-management/**',route=>route.fulfill({json:route.request().url().endsWith('/settings')?{settings:{stages:[{name:'New',required:[],allowedNext:[]}],slaHours:24,staleDays:7,assignment:{mode:'manual',ownerIds:[],rules:[]},sequences:[],workflows:[]},owners:[],canManage:true,canAdmin:true,userId:100}:{items:people,total:5,page:1,perPage:40,summary:{total:5,active:5},byStage:{New:5},bySource:{},convertedBySource:{},lostReasons:{}}}));
 await page.route('**/api/v1/employees/**',route=>route.fulfill({json:route.request().url().includes('filter-options')?{}:route.request().url().includes('workbench/home')?{pending_counts:{}}:{items:people.map(({state,city,pincode,...employee})=>employee),total:5,pages:1,page:1}}));
 await page.route('**/api/v1/master-data/company-directory/query**',route=>{const q=JSON.parse(new URL(route.request().url()).searchParams.get('state')||'{}');const rows=people.filter(row=>(q.path||[]).every((p:any)=>(row as any)[p.field]===p.value));const field=q.grouping?.[q.path?.length||0];const groups=field?[...new Set(rows.map(row=>(row as any)[field]))].map(value=>({field,value,label:value||'Not set',count:rows.filter(row=>(row as any)[field]===value).length,aggregates:[],path:[...(q.path||[]),{field,value}]})):[];return route.fulfill({json:{rows:field?[]:rows,groups,total:5,pageTotal:field?groups.length:rows.length,page:1,pageSize:30,permissions:{edit:true,export:true},context:{canCreate:true}}});});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(url);

 const grid=page.locator('.udg').last();await expect(grid).toBeVisible();
 for(const field of ['State','City','PIN code']){
  for(const button of await grid.getByRole('button',{name:/^Remove grouping /}).all())await button.click();
  await grid.getByLabel('Add grouping column',{exact:true}).selectOption({label:field});
  const badges=grid.locator('.udg-group-row .suite-group-badge');await expect(badges).toHaveCount(4);
  expect((await badges.allTextContents()).sort()).toEqual(field==='State'?['Karnataka','Maharashtra','Not set','Telangana']:field==='City'?['Bengaluru','Hyderabad','Not set','Pune']:['411001','500001','560001','Not set']);
  const colors=await badges.evaluateAll(els=>els.map(e=>getComputedStyle(e).backgroundColor));expect(new Set(colors).size).toBe(4);
  const rgb=colors.map(color=>color.match(/\d+/g)!.slice(0,3).map(Number));
  for(let i=0;i<rgb.length;i++)for(let j=i+1;j<rgb.length;j++)expect(Math.hypot(...rgb[i].map((v,k)=>v-rgb[j][k]))).toBeGreaterThan(85);
  await expect(grid.locator('.udg-group-row .suite-group-count').filter({hasText:/^2$/})).toHaveCount(1);
  await grid.getByRole('button',{name:'Expand loaded groups',exact:true}).click();await expect(grid.locator('.udg-row')).toHaveCount(5);
  await grid.scrollIntoViewIfNeeded();
  await page.screenshot({path:`../outputs/location-grouping/${name.replaceAll(' ','-')}-${field.replaceAll(' ','-')}.png`});
  const rowColors=await grid.locator('.udg-row').evaluateAll(rows=>rows.map(row=>getComputedStyle(row).getPropertyValue('--record-group-accent').trim()));
  expect(new Set(rowColors).size).toBe(4);
  await page.evaluate(()=>document.documentElement.classList.add('dark'));
  const darkColors=await badges.evaluateAll(els=>els.map(e=>getComputedStyle(e).backgroundColor));expect(darkColors).toEqual(colors);
  await page.screenshot({path:`../outputs/location-grouping/${name.replaceAll(' ','-')}-${field.replaceAll(' ','-')}-dark.png`});
  await page.evaluate(()=>document.documentElement.classList.remove('dark'));
  await grid.getByRole('button',{name:'Collapse all' ,exact:true}).click();await expect(grid.locator('.udg-row')).toHaveCount(0);
 }
 await page.reload();await expect(grid.getByRole('button',{name:'Remove grouping PIN code',exact:true})).toBeVisible();
 expect(errors).toEqual([]);
});
