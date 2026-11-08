"""Real HTTP CRUD and RBAC contracts against the disposable 1592 fixture only."""
import json,os,re,time,urllib.request,urllib.error
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/os.environ.get('AUDIT_OUTPUT','outputs/crud-permissions-121');BASE=os.environ.get('AUDIT_BASE_URL','http://127.0.0.1:1592');SCHEMA=json.loads((ROOT/'outputs/crud-permissions-121/openapi.json').read_text(encoding='utf-8'));RESULTS=[];REF={};TAG=str(int(time.time()))[-7:];TODAY=date.today().isoformat()
if os.environ.get('CRUD_RETRY') and (OUT/'resource-contracts.json').exists():RESULTS=[r for r in json.loads((OUT/'resource-contracts.json').read_text(encoding='utf-8')) if r['status']=='passed']

if os.environ.get('CRUD_RECHECK'):
    recheck=set(os.environ['CRUD_RECHECK'].split('|'));RESULTS=[r for r in RESULTS if r['resource'] not in recheck]

def req(method,path,body=None,actor='admin'):
    headers={'Content-Type':'application/json'}
    if actor in AUTH:headers['Authorization']='Bearer '+AUTH[actor]['access_token']
    data=json.dumps(body).encode() if body is not None else None
    q=urllib.request.Request(BASE+'/api/v1'+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(q,timeout=45) as r:status=r.status;raw=r.read().decode();typ=r.headers.get('Content-Type','')
    except urllib.error.HTTPError as e:status=e.code;raw=e.read().decode();typ=e.headers.get('Content-Type','')
    except Exception as e:return 0,{'error':str(e)}
    try:value=json.loads(raw)
    except ValueError:value={'raw':raw[:200],'content_type':typ}
    return status,value
AUTH={}
for actor,email,pwd in [('admin','admin@suiteqa.example.com','SuiteQA@12345'),('reader','reader@crudqa.example.com','CrudQA@12345'),('outsider','outsider@crudqa.example.com','CrudQA@12345')]:
    s,b=req('POST','/auth/login',{'email':email,'password':pwd},actor=None)
    if s!=200:raise RuntimeError(f'{actor} login failed: {s} {b}')
    AUTH[actor]=b

def items(body):
    if isinstance(body,list):return body
    if isinstance(body,dict):
        for key in ['items','records','data','rows','results']:
            if isinstance(body.get(key),list):return body[key]
    return []
def snapshot():
    (OUT/'resource-contracts.json').write_text(json.dumps(RESULTS,indent=2,default=str),encoding='utf-8')
def check(row,label,status,expected,body=None):
    ok=status in expected;row['checks'].append({'operation':label,'status':status,'expected':expected,'passed':ok,**({'response':body} if not ok else {})});return ok

def methods(path):
    actual='/api/v1'+path.split('?')[0]
    for pattern,ops in SCHEMA['paths'].items():
        if re.fullmatch(re.sub(r'\{[^}]+\}',r'[^/]+',pattern),actual):return ops
    return {}

def seed(key,path,payload):
    status,body=req('POST',path,payload)
    if status not in [200,201]:raise RuntimeError(f'Seed {key}: {status} {body}')
    REF[key]=body;return body

def case(name,path,payload,patch,detail=None,private=True,allow_personal=False,deactivate=False,delete_version=False):
    if any(r['resource']==name and r['status']=='passed' for r in RESULTS):return
    row={'resource':name,'collection':path,'checks':[],'crud':{}};RESULTS.append(row)
    try:
        status,body=req('GET',path);check(row,'read collection',status,[200],body);row['crud']['R']='passed' if status==200 else 'failed'
        status,body=req('GET',path,actor=None);check(row,'anonymous read denied',status,[401,403],body)
        if not allow_personal:
            status,body=req('POST',path,payload,actor='reader');check(row,'read-only create denied',status,[401,403,404],body)
        status,body=req('POST',path,payload);row['crud']['C']='passed' if check(row,'create',status,[200,201],body) else 'failed'
        if status not in [200,201]:return
        ident=body.get('id') or body.get('item',{}).get('id');row['id']=ident
        if not ident:row['checks'].append({'operation':'create returns identifier','passed':False,'response':body});return
        resource=detail.format(id=ident) if detail else path.rstrip('/')+'/'+str(ident)
        ops=methods(resource)
        if 'get' in ops:
            status,read=req('GET',resource);check(row,'read created record',status,[200],read)
            if private:
                status,b=req('GET',resource,actor='outsider');check(row,'cross-company record read denied',status,[403,404],b)
            if allow_personal:
                status,b=req('GET',resource,actor='reader');check(row,'other-user private record read denied',status,[403,404],b)
        else:
            status,read=req('GET',path)
            found=any(str(r.get('id'))==str(ident) for r in items(read))
            row['checks'].append({'operation':'created record appears in collection','passed':status==200 and found,'status':status})
        method='PATCH' if 'patch' in ops else 'PUT' if 'put' in ops else None
        current=body
        if method:
            update={**(payload if method=='PUT' else {}),**patch}
            if delete_version:update['version']=body['version']
            if name=='Power Apps automations':update['expected_version']=body['version']
            status,b=req(method,resource,update,actor='reader');check(row,'read-only update denied',status,[401,403,404],b)
            if private:
                status,b=req(method,resource,update,actor='outsider');check(row,'cross-company update denied',status,[403,404],b)
            status,current=req(method,resource,update);row['crud']['U']='passed' if check(row,'update',status,[200],current) else 'failed'
            if status==200:
                observed=current
                if 'get'in ops:
                    _,observed=req('GET',resource)
                else:
                    _,collection=req('GET',path)
                    observed=next((r for r in items(collection) if str(r.get('id'))==str(ident)),{})
                missing={k:v for k,v in patch.items() if observed.get(k)!=v and observed.get(re.sub(r'(?<!^)(?=[A-Z])','_',k).lower())!=v and observed.get(re.sub(r'_([a-z])',lambda m:m[1].upper(),k))!=v}
                row['checks'].append({'operation':'updated values persisted','passed':not missing,**({'mismatch':missing,'response':observed} if missing else {})})
        else:row['crud']['U']='N/A: no direct update endpoint'
        if 'delete' in ops:
            delete_resource=resource+('&' if '?' in resource else '?')+'expected_version='+str(current.get('version',body.get('version'))) if name=='Power Apps automations' else resource
            status,b=req('DELETE',delete_resource,actor='reader');check(row,'read-only delete denied',status,[401,403,404],b)
            if private:
                status,b=req('DELETE',delete_resource,actor='outsider');check(row,'cross-company delete denied',status,[403,404],b)
            delete_path=delete_resource
            status,b=req('DELETE',delete_path,{'version':current.get('version',body.get('version'))} if delete_version else None);row['crud']['D']='passed' if check(row,'delete',status,[200,204],b) else 'failed'
            if status in [200,204]:
                status,b=req('GET',path);found=next((x for x in items(b) if str(x.get('id'))==str(ident)),None)
                deleted=found is None or bool(found.get('deleted_at') or found.get('is_deleted') or found.get('deletedAt') or found.get('enabled') is False or found.get('visible') is False or found.get('active') is False)
                row['checks'].append({'operation':'deleted record absent from active collection','status':status,'passed':status==200 and deleted})
        elif deactivate and method:
            update={**payload,**patch,'active':False}
            status,b=req(method,resource,update);check(row,'deactivate instead of destructive delete',status,[200],b);row['crud']['D']='N/A: retained record; deactivation tested'
            if status==200:
                if 'get' in ops:
                    observed_status,observed=req('GET',resource);inactive=observed_status==200 and observed.get('active') is False
                else:
                    observed_status,observed=req('GET',path);found=next((r for r in items(observed) if str(r.get('id'))==str(ident)),None);inactive=observed_status==200 and (found is None or found.get('active') is False)
                row['checks'].append({'operation':'deactivation persisted','passed':inactive})
        else:row['crud']['D']='N/A: no destructive delete endpoint'
    except Exception as e:row['checks'].append({'operation':'contract execution','passed':False,'error':str(e)})
    finally:
        row['status']='passed' if row['checks'] and all(c['passed'] for c in row['checks']) else 'failed';snapshot();print(name,row['status'],flush=True)

# Stable reference records are distinct from records deleted by CRUD cases.
project=seed('project','/project-management/projects',{'workspace_id':1,'name':'CRUD reference '+TAG,'project_key':'CR'+TAG,'status':'Active'})
REF['task']=seed('task',f"/project-management/projects/{project['id']}/tasks",{'title':'Reference task '+TAG,'task_key':'REF'+TAG})
groups=req('GET','/fam/ledger-groups')[1];group=next(x for x in items(groups) if x.get('nature')=='asset');REF['group']=group
seed('department','/company/departments/',{'name':'Acceptance '+TAG,'code':'D'+TAG,'branch_id':1})
seed('designation','/company/designations/',{'name':'Acceptance role '+TAG,'code':'D'+TAG,'department_id':REF['department']['id']})
REF['employee']=seed('employee','/employees/',{'first_name':'Reference','last_name':'CRUD '+TAG,'date_of_joining':TODAY,'employee_id':'CR'+TAG})
REF['engagement']=seed('engagement','/srm/engagements',{'name':'Reference engagement '+TAG,'customer_id':101})
REF['ledger']=seed('ledger','/fam/ledgers',{'ledger_code':'RL'+TAG,'ledger_name':'Reference ledger '+TAG,'ledger_group_id':group['id'],'ledger_type':'bank'})

case('PMS clients','/project-management/clients',{'name':'CRUD client '+TAG},{'name':'Updated client '+TAG})
case('PMS projects','/project-management/projects',{'workspace_id':1,'name':'CRUD project '+TAG,'project_key':'CP'+TAG},{'name':'Updated project '+TAG})
case('PMS tasks',f"/project-management/projects/{project['id']}/tasks",{'title':'CRUD task '+TAG,'task_key':'CT'+TAG},{'title':'Updated task '+TAG},detail='/project-management/tasks/{id}')
case('PMS risks','/project-management/risks',{'project_id':project['id'],'title':'CRUD risk '+TAG,'probability':2,'impact':3},{'title':'Updated risk '+TAG})
case('PMS time logs','/project-management/time-logs',{'project_id':project['id'],'log_date':TODAY,'duration_minutes':30,'description':'CRUD log '+TAG},{'description':'Updated log '+TAG},detail='/project-management/time-logs/{id}')
case('PMS private notes','/project-management/notes',{'project_id':project['id'],'title':'CRUD note '+TAG,'content':'Private test content'},{'title':'Updated note '+TAG},allow_personal=True,delete_version=True)
for entity,payload,patch in [
 ('leads',{'firstName':'CRUD','lastName':TAG,'fullName':'CRUD '+TAG,'email':'crud'+TAG+'@example.com'},{'firstName':'Updated'}),
 ('contacts',{'firstName':'CRUD contact','lastName':TAG,'fullName':'CRUD contact '+TAG,'email':'contact'+TAG+'@example.com'},{'firstName':'Updated contact'}),
 ('companies',{'name':'CRUD company '+TAG},{'name':'Updated company '+TAG}),
 ('deals',{'name':'CRUD deal '+TAG,'pipelineId':1,'stageId':1,'amount':100},{'name':'Updated deal '+TAG}),
 ('tickets',{'ticketNumber':'T'+TAG,'subject':'CRUD ticket '+TAG},{'subject':'Updated ticket '+TAG}),
 ('campaigns',{'name':'CRUD campaign '+TAG,'campaignType':'Email'},{'name':'Updated campaign '+TAG}),
 ('quotations',{'quoteNumber':'Q'+TAG,'issueDate':TODAY,'expiryDate':(date.today()+timedelta(days=30)).isoformat()},{'notes':'Updated quote '+TAG}),
 ('products',{'name':'CRUD product '+TAG,'sku':'SKU'+TAG,'unitPrice':10},{'name':'Updated product '+TAG})]:
 case('CRM '+entity,'/crm/'+entity,payload,patch)
case('HRMS employees','/employees/',{'first_name':'CRUD','last_name':TAG,'employee_id':'EC'+TAG,'date_of_joining':TODAY},{'first_name':'Updated'},detail='/employees/{id}')
case('HRMS recruitment','/recruitment/jobs',{'title':'CRUD role '+TAG,'description':'Acceptance job'},{'title':'Updated role '+TAG})
case('HRMS performance','/performance/cycles',{'name':'CRUD cycle '+TAG,'review_period_start':TODAY,'review_period_end':(date.today()+timedelta(days=30)).isoformat()},{'name':'Updated cycle '+TAG})
case('HRMS assets','/assets/',{'asset_tag':'A'+TAG,'name':'CRUD asset '+TAG},{'name':'Updated asset '+TAG},detail='/assets/{id}')
case('HRMS timesheet projects','/timesheets/projects',{'code':'TP'+TAG,'name':'CRUD timesheet project '+TAG},{'name':'Updated project '+TAG})
case('FAM ledger groups','/fam/ledger-groups',{'group_name':'CRUD group '+TAG,'group_code':'G'+TAG,'nature':'asset'},{'group_name':'Updated group '+TAG})
case('FAM ledgers','/fam/ledgers',{'ledger_code':'L'+TAG,'ledger_name':'CRUD ledger '+TAG,'ledger_group_id':group['id']},{'ledger_name':'Updated ledger '+TAG})
case('FAM parties','/fam/parties',{'party_type':'customer','party_code':'P'+TAG,'legal_name':'CRUD party '+TAG},{'legal_name':'Updated party '+TAG},deactivate=True)
case('FAM bank accounts','/fam/bank-accounts',{'ledger_id':REF['ledger']['id'],'bank_name':'CRUD bank '+TAG,'account_number_masked':'****1234'},{'bank_name':'Updated bank '+TAG},deactivate=True)
for resource,payload,patch in [
 ('stock-groups',{'group_code':'SG'+TAG,'group_name':'CRUD stock group '+TAG},{'group_name':'Updated stock group '+TAG}),
 ('units',{'unit_code':'U'+TAG,'unit_name':'CRUD unit '+TAG},{'unit_name':'Updated unit '+TAG}),
 ('warehouses',{'warehouse_code':'W'+TAG,'warehouse_name':'CRUD warehouse '+TAG},{'warehouse_name':'Updated warehouse '+TAG}),
 ('items',{'sku':'I'+TAG,'item_name':'CRUD item '+TAG},{'item_name':'Updated item '+TAG})]:
 case('Inventory '+resource,'/fam/inventory/'+resource,payload,patch,deactivate=True)
case('Sales orders','/srm/sales-orders',{'title':'CRUD order '+TAG,'customer_id':101},{'title':'Updated order '+TAG})
case('Contracts','/srm/contracts',{'title':'CRUD contract '+TAG,'customer_id':101},{'title':'Updated contract '+TAG})
case('Engagements','/srm/engagements',{'name':'CRUD engagement '+TAG,'customer_id':101},{'name':'Updated engagement '+TAG})
case('Billing plans','/srm/billing-plans',{'name':'CRUD billing '+TAG,'engagement_id':REF['engagement']['id'],'milestones':[{'name':'Acceptance milestone','amount':100,'due_date':TODAY}]},{'name':'Updated billing '+TAG})
case('Analytics reports','/analytics/reports',{'name':'CRUD report '+TAG,'module_name':'crm_deals','visibility':'private'},{'name':'Updated report '+TAG})
case('Analytics dashboards','/analytics/dashboards',{'name':'CRUD dashboard '+TAG,'visibility':'private'},{'name':'Updated dashboard '+TAG})
module=seed('custom_module','/customization/modules',{'module_api_name':'crud_'+TAG,'module_label':'CRUD record','plural_label':'CRUD records'})
case('Customization modules','/customization/modules',{'module_api_name':'crud2_'+TAG,'module_label':'CRUD module','plural_label':'CRUD modules'},{'module_label':'Updated CRUD module'})
case('Customization fields','/customization/fields',{'module_name':'crud_'+TAG,'field_api_name':'name','field_label':'CRUD name','field_type':'text'},{'field_label':'Updated CRUD name'})
for resource,payload,patch in [
 ('layouts',{'module_name':'crud_'+TAG,'name':'CRUD layout '+TAG},{'name':'Updated layout '+TAG}),
 ('views',{'module_name':'crud_'+TAG,'name':'CRUD view '+TAG,'columns_json':['name'],'shared':True},{'name':'Updated view '+TAG}),
 ('kanban',{'module_name':'crud_'+TAG,'name':'CRUD board '+TAG,'group_by_field':'status'},{}),
 ('validation-rules',{'module_name':'crud_'+TAG,'name':'CRUD validation '+TAG,'condition_json':{'field':'name','operator':'is_empty'},'error_message':'Required'},{}),
 ('buttons',{'module_name':'crud_'+TAG,'label':'CRUD button '+TAG,'name':'CRUD button '+TAG,'action_type':'open_url','action_config_json':{'url':'https://example.test'}},{}),
 ('related-lists',{'module_name':'crud_'+TAG,'related_module_name':'crm_deals','label':'CRUD related '+TAG},{}),
 ('picklists',{'api_name':'pick_'+TAG,'label':'CRUD picklist '+TAG,'values':[{'value':'one','label':'One'}]},{})]:
 case('Customization '+resource,'/customization/'+resource,payload,patch)
case('Communication email templates','/communication/email-templates',{'name':'CRUD email '+TAG,'subject':'Test subject','body_text':'Synthetic template'},{'subject':'Updated test subject'})
case('Communication webforms','/communication/webforms',{'name':'CRUD form '+TAG,'public_slug':'crud-'+TAG,'target_module':'lead','fields_json':[]},{'name':'Updated form '+TAG})
case('Communication campaigns','/communication/campaigns',{'name':'CRUD campaign '+TAG,'type':'email','status':'draft'},{'name':'Updated campaign '+TAG})
case('AI handoff notes','/ai-agents/handoff-notes',{'module':'CRM','summary':'CRUD handoff '+TAG},{'status':'resolved'},detail='/ai-agents/handoff-notes/{id}/status')
case('Power Apps automations','/power-apps/automations?environment=development',{'name':'CRUD automation '+TAG},{'name':'Updated automation '+TAG},detail='/power-apps/automations/{id}?environment=development')
(OUT/'reference-records.json').write_text(json.dumps({k:v for k,v in REF.items()},indent=2),encoding='utf-8')
print(json.dumps({'resources':len(RESULTS),'passed':sum(r['status']=='passed' for r in RESULTS),'failed':[r['resource'] for r in RESULTS if r['status']=='failed']},indent=2),flush=True)
