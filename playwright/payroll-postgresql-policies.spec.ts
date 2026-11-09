import { test, expect } from '../frontend/node_modules/playwright/test';
import fs from 'node:fs';

test('configure all six policies, resolve attendance blockers, calculate fixed divisor and preserve versioned history',async({page,request},info)=>{
  test.setTimeout(180000);
  const api=process.env.PAYROLL_QA_API!;
  const login=await request.post(`${api}/auth/login`,{data:{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'}});
  expect(login.ok()).toBeTruthy();const tokens=await login.json();
  const headers={Authorization:`Bearer ${tokens.access_token}`,'X-Suite-Organization':'1','X-Suite-Branch':'1'};
  const access=await request.get(`${api}/access/me`,{headers});const user={id:tokens.user_id,email:tokens.email,role:tokens.role,is_superuser:true,access:await access.json()};
  await page.addInitScript(({tokens,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:tokens.access_token,refreshToken:tokens.refresh_token,user,isAuthenticated:true},version:0})),{tokens,user});
  const post=async(path:string,data:unknown)=>{const r=await request.post(api+path,{headers,data,maxRetries:path==='/payroll/inputs/attendance'?2:0});expect(r.ok(),await r.text()).toBeTruthy();return r.json();};
  const month=info.project.name==='desktop'?5:6;const prefix=`2027-${String(month).padStart(2,'0')}`;
  const department=await post('/company/departments/',{name:`QA Policies ${info.project.name}`,branch_id:1});
  const designation=await post('/company/designations/',{name:`QA Policies ${info.project.name}`,department_id:department.id});
  const employee=await post('/employees/',{first_name:'Synthetic',last_name:`Policy ${info.project.name}`,date_of_joining:'2020-01-01',branch_id:1,department_id:department.id,designation_id:designation.id,create_user_account:false});
  await post('/payroll/salary',{employee_id:employee.id,ctc:'360000',basic:'12000',hra:'6000',effective_from:'2020-01-01'});
  const components=await request.get(`${api}/payroll/components`,{headers});if(!(await components.json()).length)await post('/payroll/components',{name:'QA Base',code:'QA-BASE',component_type:'Earning',amount:0});
  const group=await post('/payroll/setup/pay-groups',{name:`QA Policies ${info.project.name}`,code:`QA-POL-${info.project.name}`,working_pattern:'5_day',working_days_per_week:5});
  const length=new Date(Date.UTC(2027,month,0)).getUTCDate();let work=0;for(let day=1;day<=length;day++){const d=new Date(Date.UTC(2027,month-1,day)).getUTCDay();if(d!==0&&d!==6)work++;}
  const period=await post('/payroll/setup/periods',{pay_group_id:group.id,month,year:2027,financial_year:'2027-28',period_start:`${prefix}-01`,period_end:`${prefix}-${length}`,payroll_date:`${prefix}-${length}`});
  await page.goto('/hrms/payroll');await page.getByRole('button',{name:'Payroll Policies',exact:true}).click();
  await page.getByLabel('Policy pay group',{exact:true}).selectOption(String(group.id));
  await expect(page.getByLabel('Missing attendance policy')).toHaveValue('block');await expect(page.getByLabel('Conflicting leave policy')).toHaveValue('block');
  await page.getByLabel('Enable sandwich leave',{exact:true}).check();
  await page.getByLabel('LOP divisor',{exact:true}).selectOption('fixed_30');
  await page.getByLabel('Joining and exit divisor').selectOption('fixed_26');await page.getByLabel('Proration day basis').selectOption('working_days');
  await page.getByLabel('hra LOP',{exact:true}).uncheck();
  await page.getByLabel('Policy effective from').fill(`${prefix}-01`);await page.getByLabel('Policy change reason').fill('QA recommended defaults with explicit fixed divisors');
  const publish=page.waitForResponse(r=>r.url().endsWith(`/payroll/setup/pay-groups/${group.id}/policies`)&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Publish payroll policy',exact:true}).click();const saved=await publish;expect(saved.status(),await saved.text()).toBe(201);const version=await saved.json();
  await page.reload();await page.getByLabel('Policy pay group',{exact:true}).selectOption(String(group.id));
  await expect(page.getByLabel('LOP divisor',{exact:true})).toHaveValue('fixed_30');await expect(page.getByLabel('Enable sandwich leave',{exact:true})).toBeChecked();
  await page.getByRole('button',{name:'Run Payroll',exact:true}).first().click();
  await page.getByLabel('Payroll pay group',{exact:true}).selectOption(String(group.id));await page.getByLabel('Payroll month',{exact:true}).selectOption(String(month));
  const card=page.locator('div').filter({has:page.getByText('Process payroll for a specific month',{exact:true})}).filter({has:page.getByRole('spinbutton')}).last();await card.getByRole('spinbutton').fill('2027');
  const generate=async()=>{const next=page.waitForResponse(r=>r.url().endsWith('/payroll/run')&&r.request().method()==='POST');await card.getByRole('button',{name:'Run Payroll',exact:true}).click();let response=await next;if(response.status()!==201){const forced=page.waitForResponse(r=>r.url().endsWith('/payroll/run')&&r.request().method()==='POST');await page.getByRole('button',{name:'Force Run',exact:true}).click();response=await forced;}expect(response.status(),await response.text()).toBe(201);return response.json();};
  const run=await generate();
  const blocked=await request.put(`${api}/payroll/runs/${run.id}/approve`,{headers,data:{action:'approve',force_approve:true}});expect(blocked.status()).toBe(400);expect(await blocked.text()).toContain('Unresolved attendance');
  const people=await request.get(`${api}/employees/?limit=100`,{headers});expect(people.ok()).toBeTruthy();
  for(const person of (await people.json()).items){
    if(person.date_of_joining&&person.date_of_joining>`${prefix}-${length}`)continue;
    const loss=person.id===employee.id?1:0;
    await post('/payroll/inputs/attendance',{period_id:period.id,employee_id:person.id,working_days:work,present_days:work-loss,payable_days:work-loss,lop_days:loss,source_status:'Approved',resolution_note:'QA HR reviewed and resolved attendance for this period'});
  }
  const corrected=await generate();expect(corrected.id).toBe(run.id);
  const recordsResponse=await request.get(`${api}/payroll/runs/${run.id}/records`,{headers});const records=await recordsResponse.json();const record=records.find((r:any)=>r.employee_id===employee.id);
  // Independently: 12,000 - 400 Basic + 6,000 HRA + 12,000 - 400 Other.
  expect(Number(record.gross_salary)).toBe(29200);
  expect(Number(record.earnings.find((c:any)=>c.component_name==='Basic').amount)).toBe(11600);expect(Number(record.earnings.find((c:any)=>c.component_name==='House Rent Allowance').amount)).toBe(6000);
  expect(corrected.policy_snapshot.groups[String(group.id)].version_id).toBe(version.id);
  await page.getByRole('button',{name:'Payroll Policies',exact:true}).click();await page.getByLabel('Policy pay group',{exact:true}).selectOption(String(group.id));
  await page.getByLabel('LOP divisor',{exact:true}).selectOption('fixed_26');await page.getByLabel('Policy effective from').fill('2027-07-01');await page.getByLabel('Policy change reason').fill('QA future version must preserve existing payroll');
  const second=page.waitForResponse(r=>r.url().endsWith(`/payroll/setup/pay-groups/${group.id}/policies`)&&r.request().method()==='POST');await page.getByRole('button',{name:'Publish payroll policy',exact:true}).click();expect((await second).status()).toBe(201);
  await expect(page.getByText('QA future version must preserve existing payroll',{exact:true})).toBeVisible();
  await page.screenshot({path:`.tmp/payroll-policies-${info.project.name}.png`,fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.getByRole('button',{name:'Run Payroll',exact:true}).first().click();const replay=await generate();expect(replay.policy_snapshot.groups[String(group.id)].version_id).toBe(version.id);
  const expand=page.getByRole('button',{name:'Expand loaded groups',exact:true});if(await expand.isVisible())await expand.click();await page.getByText(`${month===5?'May':'June'} 2027`,{exact:true}).last().click();
  for(const action of ['Force approve','Lock']){const waiting=page.waitForResponse(r=>r.url().endsWith(`/payroll/runs/${run.id}/approve`)&&r.request().method()==='PUT');const button=page.getByRole('button',{name:action,exact:true}).first();await expect(button).toBeEnabled();await button.click();const response=await waiting;expect(response.status(),await response.text()).toBe(200);}
  const history=await request.get(`${api}/payroll/setup/pay-groups/${group.id}/policies`,{headers});expect((await history.json()).versions.length).toBe(2);
  const invalid=await request.post(`${api}/payroll/setup/pay-groups/${group.id}/policies`,{headers,data:{effective_from:`${prefix}-01`,reason:'QA forbidden historical edit',rules:version.rules}});expect(invalid.status()).toBe(409);
  fs.writeFileSync(`.tmp/payroll-policies-${info.project.name}.json`,JSON.stringify({version,corrected,record,blockedApproval:blocked.status(),historicalEdit:invalid.status(),replayedVersion:replay.policy_snapshot.groups[String(group.id)].version_id},null,2));
});
