import { test, expect } from '../frontend/node_modules/playwright/test';
import fs from 'node:fs';

test('salary revision, half-day LOP, bonus, recovery, correction, repeat generation and locked-input protection', async ({page,request},info)=>{
  const api=process.env.PAYROLL_QA_API!;
  const login=await request.post(`${api}/auth/login`,{data:{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'}});
  const tokens=await login.json();
  const headers={Authorization:`Bearer ${tokens.access_token}`,'X-Suite-Organization':'1','X-Suite-Branch':'1'};
  const access=await request.get(`${api}/access/me`,{headers});
  const user={id:tokens.user_id,email:tokens.email,role:tokens.role,is_superuser:true,access:await access.json()};
  await page.addInitScript(({tokens,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:tokens.access_token,refreshToken:tokens.refresh_token,user,isAuthenticated:true},version:0})),{tokens,user});
  const post=async(path:string,data:unknown)=>{const r=await request.post(api+path,{headers,data,maxRetries:path==='/payroll/inputs/attendance'?2:0});expect(r.ok(),await r.text()).toBeTruthy();return r.json();};
  const month=info.project.name==='desktop'?3:4, length=month===3?31:30;
  const prefix=`2027-${String(month).padStart(2,'0')}`;
  const department=await post('/company/departments/',{name:`QA Combination ${info.project.name}`,branch_id:1});
  const designation=await post('/company/designations/',{name:'QA Combination Analyst',department_id:department.id});
  const employee=await post('/employees/',{first_name:'Synthetic',last_name:`Combination ${info.project.name}`,date_of_joining:`${prefix}-01`,branch_id:1,department_id:department.id,designation_id:designation.id,create_user_account:false});
  await post('/payroll/salary',{employee_id:employee.id,ctc:'360000',basic:'12000',hra:'6000',effective_from:`${prefix}-01`});
  await post('/payroll/salary',{employee_id:employee.id,ctc:'372000',basic:'12400',hra:'6200',effective_from:`${prefix}-16`});
  const componentsResponse=await request.get(`${api}/payroll/components`,{headers});
  if(!(await componentsResponse.json()).length)await post('/payroll/components',{name:'QA Base',code:'QA-BASE',component_type:'Earning',calculation_type:'Fixed',amount:0});
  const group=await post('/payroll/setup/pay-groups',{name:`QA Combination ${info.project.name}`,code:`QA-COMB-${info.project.name}`,working_pattern:'5_day'});
  const period=await post('/payroll/setup/periods',{pay_group_id:group.id,month,year:2027,financial_year:'2026-27',period_start:`${prefix}-01`,period_end:`${prefix}-${length}`,payroll_date:`${prefix}-${length}`});
  let work=0;for(let d=1;d<=length;d++){const weekday=new Date(Date.UTC(2027,month-1,d)).getUTCDay();if(weekday!==0&&weekday!==6)work++;}
  const attendance=(lop:number)=>({period_id:period.id,employee_id:employee.id,working_days:work,present_days:work-lop,payable_days:work-lop,lop_days:lop,source_status:'Approved'});
  await post('/payroll/inputs/attendance',attendance(.5));
  await page.goto('/hrms/payroll');
  await page.getByRole('button',{name:'Run Payroll',exact:true}).first().click();
  const card=page.locator('div').filter({has:page.getByText('Process payroll for a specific month',{exact:true})}).filter({has:page.getByRole('spinbutton')}).last();
  await card.getByLabel('Payroll month').selectOption(String(month));await card.getByRole('spinbutton').fill('2027');
  const generate=async()=>{
    const waiting=page.waitForResponse(r=>r.url().endsWith('/payroll/run')&&r.request().method()==='POST');
    await card.getByRole('button',{name:'Run Payroll',exact:true}).click();let response=await waiting;
    if(response.status()!==201){const forced=page.waitForResponse(r=>r.url().endsWith('/payroll/run')&&r.request().method()==='POST');await page.getByRole('button',{name:'Force Run',exact:true}).click();response=await forced;}
    expect(response.status(),await response.text()).toBe(201);return response.json();
  };
  const run=await generate();
  const records=async()=>{const response=await request.get(`${api}/payroll/runs/${run.id}/records`,{headers});expect(response.ok()).toBeTruthy();return (await response.json()).find((r:any)=>r.employee_id===employee.id);};
  const round=(n:number)=>Math.round(n*100)/100;
  const monthly=round((30000*15+31000*(length-15))/length);
  const before=await records();expect(Number(before.gross_salary)).toBeCloseTo(round(monthly-monthly*.5/work),2);
  for(const [input_type,component_name,amount] of [['Bonus','QA bonus',1000],['Deduction','QA recovery',250]] as const){
    const input=await post(`/payroll/runs/${run.id}/manual-inputs`,{employee_id:employee.id,input_type,component_name,amount});
    const approved=await request.put(`${api}/payroll/manual-inputs/${input.id}/review`,{headers,data:{action:'approve'}});expect(approved.ok(),await approved.text()).toBeTruthy();
  }
  const pending=await post(`/payroll/runs/${run.id}/manual-inputs`,{employee_id:employee.id,input_type:'Bonus',component_name:'QA pending',amount:500});
  await post('/payroll/inputs/attendance',attendance(1.5));
  expect((await generate()).id).toBe(run.id);
  const corrected=await records();
  expect(Number(corrected.gross_salary)).toBeCloseTo(round(monthly-monthly*1.5/work+1000),2);
  expect(Number(corrected.total_deductions)-Number(before.total_deductions)).toBe(250);
  expect((await generate()).id).toBe(run.id);
  const repeated=await records();expect(repeated.net_salary).toBe(corrected.net_salary);
  const table=page.getByRole('button',{name:'Table view',exact:true});if(await table.isVisible())await table.click();
  const expand=page.getByRole('button',{name:'Expand loaded groups',exact:true});if(await expand.isVisible())await expand.click();
  await page.getByText(`${month===3?'March':'April'} 2027`,{exact:true}).last().click();
  for(const action of ['Force approve','Lock']){
    const waiting=page.waitForResponse(r=>r.url().endsWith(`/payroll/runs/${run.id}/approve`)&&r.request().method()==='PUT');
    await page.getByRole('button',{name:action,exact:true}).first().click();const response=await waiting;expect(response.status(),await response.text()).toBe(200);
  }
  const blockedInput=await request.post(`${api}/payroll/inputs/attendance`,{headers,data:attendance(0),maxRetries:2});expect(blockedInput.status()).toBe(400);
  const blockedReview=await request.put(`${api}/payroll/manual-inputs/${pending.id}/review`,{headers,data:{action:'approve'}});expect(blockedReview.status()).toBe(400);
  const slipResponse=await request.get(`${api}/payroll/payslip?employee_id=${employee.id}&month=${month}&year=2027`,{headers});expect(slipResponse.ok(),await slipResponse.text()).toBeTruthy();
  const slip=await slipResponse.json();expect(slip.net_salary).toBe(corrected.net_salary);
  const unlock=await post(`/payroll/runs/${run.id}/unlock-requests`,{reason:'QA authorized attendance correction'});
  const reviewed=await request.put(`${api}/payroll/unlock-requests/${unlock.id}/review`,{headers,data:{action:'approve',remarks:'QA correction approved'}});expect(reviewed.ok(),await reviewed.text()).toBeTruthy();
  await post('/payroll/inputs/attendance',attendance(0));
  const afterUnlockRun=await generate();expect(afterUnlockRun.id).toBe(run.id);
  const summary=page.getByText('Selected run',{exact:true}).locator('..').locator('..').locator('..');
  await expect(summary.getByText(`₹${Math.round(Number(afterUnlockRun.total_net)).toLocaleString('en-IN')}`,{exact:true})).toBeVisible();
  const afterUnlock=await records();expect(Number(afterUnlock.gross_salary)).toBeCloseTo(monthly+1000,2);
  const snapshotsResponse=await request.get(`${api}/payroll/runs/${run.id}/calculation-snapshots`,{headers});expect(snapshotsResponse.ok()).toBeTruthy();
  const snapshots=await snapshotsResponse.json();
  expect(snapshots.some((s:any)=>s.employee_id===employee.id&&Math.abs(Number(s.result_json?.gross_salary)-Number(corrected.gross_salary))<.01)).toBeTruthy();
  fs.writeFileSync(`.tmp/payroll-postgresql-combination-${info.project.name}.json`,JSON.stringify({monthly,work,before,corrected,repeated,slip,afterUnlock,snapshotCount:snapshots.length,lockedInputStatus:blockedInput.status(),lockedReviewStatus:blockedReview.status()},null,2));
  await page.screenshot({path:`.tmp/payroll-postgresql-combination-${info.project.name}.png`,fullPage:true});
});
