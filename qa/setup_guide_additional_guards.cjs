// Run before native module APIs populate defaults in the disposable QA fixture.
const assert=require('node:assert/strict');
(async()=>{
 const root='http://127.0.0.1:1562/api/v1';
 const login=await (await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})})).json();
 const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
 for(const [path,title] of [['/employees/','Departments'],['/attendance/bulk-entry','Work shifts'],['/leave/apply','Leave types'],['/payroll/run','Salary components'],['/payroll/runs/999999/worksheet/process','Salary components'],['/fam/vouchers/999999/post','Open financial year']]){
  const r=await fetch(root+path,{method:'POST',headers,body:'{}'});const data=await r.json();assert.equal(r.status,409,path+': '+JSON.stringify(data));assert.equal(r.headers.get('x-suite-setup-required'),'1');assert.ok(data.detail.includes(title),JSON.stringify(data));console.log('PASS mandatory guard',path,title);
 }
})().catch(e=>{console.error(e);process.exit(1)});
