import json,time,sqlite3
from pathlib import Path
import httpx,psycopg
root=Path(__file__).resolve().parents[1];out=root/'.local/creation-live';tag=str(int(time.time()));name='Creation prerequisite '+tag
c=httpx.Client(base_url='http://127.0.0.1:1596/api/v1',timeout=90);r=c.post('/auth/login',json={'email':'admin@suiteqa.example.com','password':'SuiteQA@12345'});r.raise_for_status();a=r.json();c.headers.update({'Authorization':'Bearer '+a['access_token'],'X-Suite-Branch':'1'});emp=a.get('employee_id') or 1
results=json.loads((out/'gap-prerequisite-results.json').read_text(encoding='utf8')) if (out/'gap-prerequisite-results.json').exists() else []
def rows(v):return v.get('items',[]) if isinstance(v,dict) else v

def save(ep,body,table=None,client=None,headers=None):
 previous=next((r for r in reversed(results) if r['endpoint']==ep),None)
 if previous and previous['status']=='saved-readback-pass':return {'id':previous.get('id')}
 client=client or c;r=client.post(ep,json=body,headers=headers);v=r.json();item={'endpoint':ep,'httpStatus':r.status_code,'status':'needs-resolution'}
 if r.is_success:
  ident=v.get('id',v.get('userId',v.get('user_id'))) if isinstance(v,dict) else None
  if ident is None and isinstance(v,dict) and isinstance(v.get('user'),dict):ident=v['user'].get('id')
  item['id']=ident;item['responseKeys']=list(v) if isinstance(v,dict) else []
  if table and ident is not None:
   with sqlite3.connect(str(out/'verification.sqlite')) as db:exists=db.execute('SELECT id FROM "'+table+'" WHERE id=?',(ident,)).fetchone()
   item['status']='saved-readback-pass' if exists else 'saved-needs-readback';item['readback']='SQLite '+table
  else:
   read=client.get(ep,headers=headers)
   def find(x):return isinstance(x,dict) and (str(x.get('id'))==str(ident) or any(find(y) for y in x.values() if isinstance(y,(list,dict)))) or isinstance(x,list) and any(find(y) for y in x)
   item['status']='saved-readback-pass' if read.is_success and ident is not None and find(read.json()) else 'saved-needs-readback'
 else:item['detail']=r.text[:700]
 results.append(item);(out/'gap-prerequisite-results.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(ep,item['status'],r.status_code,flush=True);return v
step=c.post('/access/step-up',json={'password':'SuiteQA@12345'});step.raise_for_status();h={'X-Access-Step-Up':step.json()['token']}
save('/access/control/super-admins',{'companyId':1,'email':'creation-super-'+tag+'@example.com','password':'CreationQA@12345','reason':'Isolated creation verification'},'users',headers=h)
save('/access/users',{'companyId':1,'name':name,'email':'creation-managed-'+tag+'@example.com','password':'CreationQA@12345','invite':False,'reason':'Isolated creation verification'},'users',headers=h)
if not any(r['endpoint']=='/exit/checklist' and r['status']=='saved-readback-pass' for r in results):
 x=c.post('/exit/records',json={'employee_id':emp,'exit_type':'Resignation','reason':'Isolated verification'});x.raise_for_status();save('/exit/checklist',{'exit_record_id':x.json()['id'],'task_name':name},'exit_checklist_items')
x=c.post('/lms/certifications',json={'employee_id':emp,'title':name,'renewal_required':True});x.raise_for_status();save('/lms/certification-renewals',{'certification_id':x.json()['id'],'notes':name,'due_on':'2027-01-20'},'certification_renewals')
save('/payroll/reports',{'name':name,'report_type':'payroll_variance'},'payroll_report_definitions')
save('/payroll/salary-advances',{'employee_id':emp,'requested_amount':100,'requested_deduction_month':11,'requested_deduction_year':2026,'reason':name},'salary_advances')
banks=rows(c.get('/fam/bank-accounts').json());options=c.get('/fam/bank-rules/options').json()['ledgers'];counter=next((l for l in options if l['active'] and l['nature']=='expense' and l['ledger_type'] not in ['tax','bank','cash','customer','vendor']),None)
if not counter:
 groups=rows(c.get('/fam/ledger-groups').json());group=next(g for g in groups if str(g.get('nature','')).lower()=='expense');x=c.post('/fam/ledgers',json={'ledger_code':'CV'+tag,'ledger_name':name,'ledger_group_id':group['id'],'ledger_type':'general'});x.raise_for_status();counter=x.json()
save('/fam/bank-rules',{'name':name,'bank_account_id':banks[0]['id'],'counter_ledger_id':counter['id'],'direction':'withdrawal','text':'QA '+tag})
save('/power-apps/integrations/connections',{'connector_id':'http','name':name,'auth_type':'none','config':{'hosts':['example.com']},'writes_enabled':False})
invite=c.post('/portals/invite',json={'email':'creation-partner-'+tag+'@example.com','display_name':name,'portal_type':'partner','partner_id':901,'permissions':['view','manage_commissions']});invite.raise_for_status();save('/partner-portal/commissions',{'reference':name,'amount':'12.50','currency':'INR'},headers={'X-Portal-Session':invite.json()['one_time_session_token']})
owner=httpx.Client(base_url='http://127.0.0.1:1597/api/v1',timeout=90);r=owner.post('/auth/platform/login',json={'email':'owner@creationqa.example.com','password':'CreationQA@12345'});r.raise_for_status();owner.headers['Authorization']='Bearer '+r.json()['access_token']
for ep,body,table in [('/platform/plans',{'code':'cv_'+tag,'name':name,'modules':['crm'],'seats':5,'storage_mib':100,'monthly_price_minor':100},'platform_plans'),('/platform/signups',{'applicant_type':'individual','name':name,'email':'creation-signup-'+tag+'@example.com','phone':'9876501234','phone_country_code':'+91','requested_modules':['crm'],'consent':True,'consent_evidence':'Synthetic QA consent'},'platform_signup_requests')]:
 v=save(ep,body,client=owner)
 if isinstance(v,dict) and v.get('id'):
  with psycopg.connect('host=127.0.0.1 port=55439 dbname=creation_owner_test user=creationqa') as db:exists=db.execute('SELECT id FROM '+table+' WHERE id=%s',(v['id'],)).fetchone()
  if exists:results[-1].update(status='saved-readback-pass',readback='PostgreSQL '+table)
(out/'gap-prerequisite-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
