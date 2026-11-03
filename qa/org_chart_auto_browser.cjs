const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const f=require('./record_pages_fixtures.cjs');const fs=require('node:fs'),path=require('node:path');
const origin=process.env.ORG_CHART_QA_ORIGIN || 'http://127.0.0.1:5198';
const output=path.resolve('docs/qa/org-chart-auto');fs.mkdirSync(output,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const results=[];
try{for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:width===1440?1000:844},hasTouch:true});
 await context.addInitScript(({login,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','6');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:1,email:login.email,role:'admin',is_superuser:true,access}},version:0}));},f);
 const calls=[],errors=[];let fail=true,slowDepartment=false,releaseInitial;const initial=new Promise(resolve=>releaseInitial=resolve);let first=true;
 await context.route('**/api/v1/**',async route=>{
  const u=new URL(route.request().url()),p=u.pathname.replace('/api/v1','');let data;
  if(p==='/company/org-chart'){
   const params=Object.fromEntries(u.searchParams);calls.push(params);
   if(first){first=false;await initial;}
   if(slowDepartment && params.department_id==='1')await new Promise(resolve=>setTimeout(resolve,600));
   if(params.grade_band_id==='8'&&fail)return route.fulfill({status:503,json:{detail:'Temporary failure'}});
   data=params.grade_band_id==='9'?[]:[{position_id:1,position_code:'CEO',title:`D${params.department_id||'all'} L${params.location_id||'all'} G${params.grade_band_id||'all'}`,manager_position_id:null,incumbent_employee_id:1,employee_name:'Ananya Rao',department_name:'Engineering',status:'Active',is_vacant:false},{position_id:2,position_code:'ENG',title:'Delivery Engineer',manager_position_id:1,department_name:'Engineering',status:'Active',is_vacant:true}];
  }else if(p==='/company/departments/'||p==='/company/departments')data=[{id:1,name:'Engineering'},{id:2,name:'Operations'}];
  else if(p==='/company/locations')data=[{id:2,name:'Hyderabad'}];
  else if(p==='/company/grade-bands')data=[{id:3,name:'Senior'},{id:8,name:'Retry grade'},{id:9,name:'Empty grade'}];
  else data=f.response(u.pathname);
  return route.fulfill({json:data});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/hrms/employees?operation=%2Fhrms%2Forg-chart');
 await expect(page.getByRole('heading',{name:'Real-Time Org Chart',exact:true})).toBeVisible();
 await expect.poll(()=>calls.length).toBe(1);await expect(page.getByRole('status').filter({hasText:'Loading organization chart'})).toBeVisible();await expect(page.getByRole('button',{name:'Load chart',exact:true})).toHaveCount(0);releaseInitial();
 const chart=page.getByRole('img',{name:'Organization chart',exact:true});await expect(chart).toContainText('Dall Lall Gall');await expect(chart.locator('path')).toHaveCount(1);
 const department=page.getByLabel('Filter by department',{exact:true}),location=page.getByLabel('Filter by location',{exact:true}),grade=page.getByLabel('Filter by grade band',{exact:true});
 await department.selectOption('1');await expect(chart).toContainText('D1 Lall Gall');
 await location.selectOption('2');await expect(chart).toContainText('D1 L2 Gall');
 await grade.selectOption('3');await expect(chart).toContainText('D1 L2 G3');
 expect(calls.at(-1)).toEqual({department_id:'1',location_id:'2',grade_band_id:'3'});
 await grade.selectOption('9');await expect(chart).toContainText('No positions match the selected filters.');await expect(page.getByRole('button',{name:'PNG',exact:true})).toBeDisabled();
 await grade.selectOption('8');await expect(page.getByRole('alert')).toContainText('organization chart could not be loaded');fail=false;await page.getByRole('button',{name:'Retry chart',exact:true}).click();await expect(chart).toContainText('D1 L2 G8');
 await grade.selectOption('');await location.selectOption('');await department.selectOption('');await expect(chart).toContainText('Dall Lall Gall');
 slowDepartment=true;await department.selectOption('1');await department.selectOption('2');await expect(chart).toContainText('D2 Lall Gall');await page.waitForTimeout(750);await expect(chart).toContainText('D2 Lall Gall');await expect(chart).not.toContainText('D1 Lall Gall');
 const count=calls.length;await page.getByRole('button',{name:'Refresh chart',exact:true}).click();await expect.poll(()=>calls.length).toBeGreaterThan(count);await expect(chart).toContainText('D2 Lall Gall');
 await expect(page.getByRole('button',{name:'PNG',exact:true})).toBeEnabled();expect(errors).toEqual([]);
 const overflow=await page.locator('#suite-main').evaluate(el=>el.scrollWidth>el.clientWidth+1);expect(overflow).toBe(false);
 await page.mouse.move(0,0);await page.screenshot({path:path.join(output,`org-chart-${width}.png`)});results.push({width,passed:true,requests:calls.length});await context.close();console.log('PASS org chart',width,'initial load, all filters, clear, empty, error/retry, refresh, rapid changes, mobile fit');
}fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,api:'Browser fixtures; no record mutations'},null,2));}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
