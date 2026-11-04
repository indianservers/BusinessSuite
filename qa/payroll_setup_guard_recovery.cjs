// Requires the disposable backend/scripts/serve_ux_qa.py fixture on loopback :1562.
const assert=require('node:assert/strict');
(async()=>{
 const root='http://127.0.0.1:1562/api/v1';
 const login=await (await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})})).json();
 const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
 async function request(path,method='GET',body){return fetch(root+path,{method,headers,body:body?JSON.stringify(body):undefined});}
 async function api(path,method='GET',body){const r=await request(path,method,body);const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;}
 const payload={month:11,year:2026,force_run:true};
 let blocked=await request('/payroll/run','POST',payload);assert.equal(blocked.status,409,await blocked.text());
 const component=await api('/payroll/components','POST',{name:'Setup recovery allowance',code:'QA'+Date.now(),component_type:'Earning',amount:0});
 assert.equal((await api('/access/setup')).moduleItems.find(i=>i.id==='salary-components').ready,true);
 const first=await api('/payroll/run','POST',payload);assert.equal(first.branch_id,1);
 const checks=await api('/payroll/runs/'+first.id+'/pre-run-checks');assert.ok(Array.isArray(checks)&&checks.length>0);
 const repeated=await api('/payroll/run','POST',payload);assert.equal(repeated.id,first.id);
 assert.equal((await api('/payroll/runs/'+first.id+'/pre-run-checks')).length,checks.length);
 await api('/payroll/components/'+component.id,'DELETE');
 assert.equal((await api('/access/setup')).moduleItems.find(i=>i.id==='salary-components').ready,false);
 blocked=await request('/payroll/run','POST',payload);assert.equal(blocked.status,409,await blocked.text());assert.equal(blocked.headers.get('x-suite-setup-required'),'1');
 console.log('PASS payroll mandatory block, setup repair, scoped rerun and missing-component recovery; force_run cannot bypass setup');
})().catch(e=>{console.error(e);process.exit(1)});
