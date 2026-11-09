const {chromium,expect}=require('playwright/test');
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const base=process.env.HRMS_QA_URL||'http://127.0.0.1:5125';
const sections=['workforce','attendance','leave','payroll','onboarding','probation','exits','compliance'];
const context={business_date:'2026-11-08',timezone:'Asia/Kolkata',currency:'USD',scope:'Permitted workforce',personal:false,sections,permissions:['employee_create','leave_apply','leave_approve','reports_view','payroll_view','payroll_run','recruitment_view'],superuser:true,departments:[{id:1,name:'Engineering'}],locations:[{id:1,name:'HQ'}],employment_types:['Full-time']};
function body(section,url){
 const common={section,context:{as_of:'2026-11-08T08:30:00Z',business_date:'2026-11-08',timezone:'Asia/Kolkata',from_date:url.searchParams.get('from_date'),to_date:url.searchParams.get('to_date'),previous_from:'2026-09-10',previous_to:'2026-10-09'},rows:[{id:'1',employee_id:1,name:'Alex Rao',detail:section==='payroll'?'Missing bank details: IFSC':'Review required',date:'2026-11-08',status:section==='attendance'?'Present':section==='leave'?'Pending':'Overdue',href:'/hrms/employees/1'}],total_rows:1,notes:['Verified scoped records; today and operational deadlines use the company timezone.']};
 const metrics={workforce:{total:12,active:10,headcount:12,previous_headcount:11,joined:1},attendance:{present:7,wfh:2,absent:1,on_leave:1,not_marked:1,rate:90,denominator:10,present_equivalent:9,week_days:4,week_hours:32,missing_punches:1},leave:{pending:1,available_days:14,oldest_days:8,starting_soon:1},payroll:{net:900,previous_net:800,latest_run:5,status:'locked',issue_count:1},onboarding:{overdue:1,upcoming:2},probation:{overdue:1,upcoming:1},exits:{open:2,blocked:1},compliance:{overdue:1,upcoming:1}}[section];
 const series={workforce:[{department:'Engineering',count:10}],attendance:[{status:'Present',count:7},{status:'WFH',count:2}],leave:[{date:'2026-11-08',on_leave:1,without_handover:1}],payroll:[{month:'2026-11-01',gross:1000,net:900}]}[section]||[];
 return {...common,metrics,series};
}
(async()=>{const browser=await chromium.launch();const output=path.resolve(__dirname,'../../docs/qa/hrms-dashboard-enhancements');fs.mkdirSync(output,{recursive:true});
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));let failAttendance=false;const requests=[];
  await page.route('**/api/**',async route=>{const url=new URL(route.request().url());requests.push(url);
   if(url.pathname.endsWith('/hrms-dashboard/context'))return route.fulfill({json:context});
   if(url.pathname.includes('/hrms-dashboard/')){const section=url.pathname.split('/').pop();if(section==='attendance'&&failAttendance)return route.fulfill({status:503,json:{detail:'Simulated outage'}});return route.fulfill({json:body(section,url)});}
   if(url.pathname.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,selected:1,branches:[{id:1,name:'Main',code:'MAIN',can_write:true}],manage_access:false,all_branches:false}});
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/hrms-dashboard-qa.html');await expect(page.getByRole('heading',{name:'HRMS dashboard',exact:true})).toBeVisible();
  await expect(page.locator('.hrd-section')).toHaveCount(8);await expect(page.getByText('Missing bank details: IFSC',{exact:true})).toBeVisible();
  await expect(page.locator('.hrd-metrics')).toContainText('$900');await expect(page.locator('.hrd-metrics')).not.toContainText('INR');
  await page.getByLabel('Department',{exact:true}).selectOption('1');await page.getByLabel('Employment type',{exact:true}).selectOption('Full-time');
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();await expect.poll(()=>requests.filter(u=>u.pathname.includes('/hrms-dashboard/')&&!u.pathname.endsWith('/context')&&u.searchParams.get('department_id')==='1').length).toBeGreaterThanOrEqual(8);
  await page.locator('.hrd-metrics').getByRole('link',{name:'7',exact:true}).click();await expect(page.locator('#hrd-details')).toContainText('Alex Rao');
  assert.ok(requests.some(u=>u.searchParams.get('record_status')==='Present'&&u.searchParams.get('record_date')==='2026-11-08'));
  failAttendance=true;await page.getByRole('button',{name:'Refresh dashboard',exact:true}).click();await expect(page.locator('.hrd-section').filter({has:page.getByRole('heading',{name:'Attendance',exact:true})})).toContainText('Previous values are stale');
  await expect(page.getByRole('heading',{name:'Workforce',exact:true})).toBeVisible();failAttendance=false;
  await page.locator('.hrd-section').filter({has:page.getByRole('heading',{name:'Attendance',exact:true})}).getByRole('button',{name:'Retry section'}).click();
  await expect(page.locator('.hrd-section').filter({has:page.getByRole('heading',{name:'Attendance',exact:true})})).not.toContainText('Previous values are stale');
  await page.getByRole('button',{name:'Reset filters'}).click();await expect(page.getByLabel('Department',{exact:true})).toHaveValue('');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'page overflow');
  await page.screenshot({path:path.join(output,`hrms-${width}.png`),fullPage:true});assert.deepEqual(errors,[]);await page.close();console.log(`PASS ${width}: all sections, currency, filters, exact drilldown, partial/stale failure, recovery, overflow`);
 }
 const employee=await browser.newPage();const employeeRequests=[];
 await employee.route('**/api/**',async route=>{const url=new URL(route.request().url());employeeRequests.push(url.pathname);if(url.pathname.endsWith('/context'))return route.fulfill({json:{...context,scope:'My records',personal:true,superuser:false,sections:['attendance','leave','onboarding','compliance'],permissions:['attendance_view','leave_view','leave_apply','payroll_view']}});if(!url.pathname.includes('/hrms-dashboard/'))return route.fulfill({json:[]});const section=url.pathname.split('/').pop();return route.fulfill({json:body(section,url)});});
 await employee.goto(base+'/hrms-dashboard-qa.html?actor=employee');await expect(employee.getByText('My Week:',{exact:false})).toBeVisible();
 assert.equal(employeeRequests.some(p=>/\/(payroll|workforce|exits|probation)$/.test(p)),false);assert.equal(employeeRequests.some(p=>p.includes('/recruitment/')),false);
 await expect(employee.getByRole('link',{name:'Run payroll',exact:true})).toHaveCount(0);await expect(employee.getByRole('heading',{name:'My documents & recognition'})).toBeVisible();await employee.close();console.log('PASS employee-only requests and personal weekly summary');
 const failure=await browser.newPage();
 await failure.route('**/api/**',async route=>{const url=new URL(route.request().url());if(url.pathname.endsWith('/hrms-dashboard/context'))return route.fulfill({json:{...context,sections:['workforce','attendance','payroll'],permissions:[],superuser:false}});if(url.pathname.endsWith('/attendance')||url.pathname.endsWith('/payroll'))return route.fulfill({status:503,json:{detail:'Test first-load outage'}});return route.fulfill({json:body('workforce',url)});});
 await failure.goto(base+'/hrms-dashboard-qa.html');await expect(failure.locator('.hrd-metrics')).toContainText('Unavailable');await expect(failure.locator('.hrd-metrics')).not.toContainText('No completed run');await expect(failure.getByRole('heading',{name:'Workforce',exact:true})).toBeVisible();await failure.close();console.log('PASS initial failures never appear as zero, no-run or ready');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
