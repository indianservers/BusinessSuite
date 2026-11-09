import json,time,uuid,sqlite3
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'.local/creation-live';spec=json.loads((out/'openapi.json').read_text(encoding='utf8'));mapping=json.loads((out/'endpoint-contract-cases.json').read_text(encoding='utf8'))['mapping'];tag=str(int(time.time()));name='Creation contract '+tag
client=httpx.Client(base_url='http://127.0.0.1:1596/api/v1',timeout=120)
r=client.post('/auth/login',json={'email':'admin@suiteqa.example.com','password':'SuiteQA@12345'});r.raise_for_status();actor=r.json();client.headers.update({'Authorization':'Bearer '+actor['access_token'],'X-Suite-Branch':'1'});employee=actor.get('employee_id') or 1

def schema(s):
 if '$ref' in s:return spec['components']['schemas'][s['$ref'].split('/')[-1]]
 return s

def sample(s,k=''):
 s=schema(s)
 if 'default' in s:return s['default']
 if 'anyOf' in s:return sample(next(x for x in s['anyOf'] if x.get('type')!='null'),k)
 if 'enum' in s:return s['enum'][0]
 t=s.get('type','object')
 if t=='object':return {k:sample(v,k) for k,v in s.get('properties',{}).items() if k in s.get('required',[])}
 if t=='array':return [sample(s.get('items',{}),k)]*max(s.get('minItems',0),0)
 if t=='boolean':return True
 if t in ['integer','number']:return max(s.get('minimum',1),s.get('exclusiveMinimum',0)+1)
 if s.get('format')=='date':return '2027-01-20'
 if s.get('format')=='date-time':return '2027-01-20T09:00:00Z'
 if s.get('format')=='uuid':return str(uuid.uuid4())
 if 'email' in k.lower():return 'creation-'+tag+'@example.invalid'
 if k.lower() in ['code','reference','key']:return 'cv_'+tag
 return name

overrides={
 '/ai/provider-settings':{'provider_name':'mock','model_name':'mock-1','enabled':False},
 '/platform/plans':{'code':'cv_'+tag,'name':name,'modules':['crm'],'seats':5,'storage_mib':100,'monthly_price_minor':100},
 '/access/users':{'companyId':1,'name':name,'email':'managed-'+tag+'@example.invalid','password':'CreationQA@12345','invite':False,'reason':'Isolated creation verification'},
 '/access/control/super-admins':{'companyId':1,'email':'super-'+tag+'@example.invalid','password':'CreationQA@12345','reason':'Isolated creation verification'},
 '/platform/signups':{'applicant_type':'individual','name':name,'email':'signup-'+tag+'@example.invalid','phone':'9876501234','phone_country_code':'IN','requested_modules':['crm'],'consent':True,'consent_evidence':'QA consent'},
 '/payroll/accounting/ledgers':{'name':name,'code':'CV'+tag,'ledger_type':'Expense'},
 '/payroll/accounting/gl-mappings':{'component_name':'CV'+tag,'component_type':'Earning'},
 '/payroll/bonus-policies':{'name':name,'amount_value':100},
 '/payroll/budgets':{'month':11,'year':2026,'budget_amount':100},
 '/payroll/reports':{'name':name,'report_type':'Payroll Summary'},
 '/payroll/salary-advances':{'employee_id':employee,'amount':100,'repayment_months':1},
 '/payroll/salary-revisions/bulk':{'name':name,'effective_from':'2027-01-01','lines':[{'employee_id':employee,'new_ctc':120000}]},
 '/project-management/tags':{'name':name,'color':'#7632ff'},
 '/project-management/file-folders':{'name':name,'project_id':1},
 '/project-management/note-folders':{'name':name},
 '/project-management/custom-fields':{'name':name,'field_type':'text','scope':'company'},
 '/project-management/task-types':{'name':'CV'+tag},
 '/project-management/planner/events':{'title':name,'start_at':'2027-01-20T09:00:00Z','end_at':'2027-01-20T10:00:00Z'},
 '/crm/file-workspace/folders':{'name':name},
 '/crm/email-templates':{'name':name,'subject':'Verification only','body':'No delivery is requested.'},
 '/attendance/holidays':{'name':name,'holiday_date':'2027-01-20'},
 '/engagement/surveys':{'title':name,'question':'Verification?','options_json':['Yes','No']},
 '/hrms/tax-declaration/categories':{'financialYear':'2026-2027','code':'CV'+tag,'name':name,'section':'80C','maxLimit':150000},
 '/pipeline-workspaces/srm/pipelines':{'name':name,'stages':[{'id':'qa','name':'QA stage','probability':10,'color':'#7632ff'}]},
 '/auth/roles':{'name':'cv_'+tag,'description':'Isolated test role','permissions':[]},
}

def contains(v,ident):
 if isinstance(v,dict):return str(v.get('id'))==str(ident) or any(contains(a,ident) for a in v.values() if isinstance(a,(dict,list)))
 if isinstance(v,list):return any(contains(a,ident) for a in v)
 return False

results=[];retry=set(json.loads((out/'gap-retry.json').read_text())) if (out/'gap-retry.json').exists() else None
for ep,tests in sorted(mapping.items()):
 if tests or retry is not None and ep not in retry:continue
 op=spec['paths'].get('/api/v1'+ep,spec['paths'].get('/api/v1'+ep+'/',{})).get('post',{});body=overrides.get(ep) or sample(op.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema',{}))
 item={'endpoint':ep,'status':'pending'}
 try:
  response=client.post(ep,json=body);item['httpStatus']=response.status_code
  if not response.is_success:item.update(status='needs-resolution',detail=response.text[:800])
  else:
   data=response.json();ident=data.get('id') if isinstance(data,dict) else None;item['id']=ident
   target=ep+'/'+str(ident);read=client.get(target) if ident is not None else None
   if read is not None and read.is_success and contains(read.json(),ident):item.update(status='saved-readback-pass',readback=target)
   else:
    read=client.get(ep)
    if ident is not None and read.is_success and contains(read.json(),ident):item.update(status='saved-readback-pass',readback=ep)
    else:item.update(status='saved-needs-readback',detail='Write succeeded; canonical readback needs an entity-specific adapter.')
 except Exception as exc:item.update(status='needs-resolution',detail=type(exc).__name__+': '+str(exc)[:250])
 results.append(item);(out/'gap-contract-results.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(ep,item['status'],item.get('httpStatus'),flush=True)
