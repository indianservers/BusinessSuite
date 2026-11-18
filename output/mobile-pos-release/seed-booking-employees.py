from dotenv import load_dotenv
load_dotenv('/srv/business-suite/shared/backend.env')
from datetime import timedelta
from uuid import uuid5,NAMESPACE_URL
from pathlib import Path
import json,httpx
import app.db.base
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import create_access_token
BASE=Path('/srv/business-suite/shared/sample-hrms-categories-20261118')
with SessionLocal() as db:
 actor=db.query(User).filter(User.email=='saisatish@indianservers.com',User.is_active.is_(True)).one();assert actor.is_superuser
 token=create_access_token(actor.id,timedelta(minutes=20))
headers={'Authorization':'Bearer '+token,'X-Suite-Organization':'1','X-Suite-Branch':'1'}
report={'employees':[],'services':[]}
parents={'Technical Services':['Computer Repair','Network Support','Device Setup'],'Consulting':['Business Consultation','Tax Consultation','IT Advisory'],'Maintenance':['Routine Inspection','Equipment Servicing','Safety Checks']}
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',headers=headers,timeout=90,follow_redirects=True) as c:
 def req(method,path,data=None):
  r=c.request(method,path,json=data)
  if r.status_code>=400:raise RuntimeError(f'{method} {path} {r.status_code} {r.text[:700]}')
  return r.json()
 specs=[(child,['DEMO '+parent+' > '+child]) for parent,children in parents.items() for child in children]+[('Multi Skilled',['DEMO Technical Services > Computer Repair','DEMO Consulting > Business Consultation'])]
 existing=req('GET','/srm/industry/employee-options?search=DEMO%20Booking')['items'];resources=req('GET','/srm/industry/records?kind=resource')['items']
 for index,(label,categories) in enumerate(specs,1):
  name='DEMO Booking '+label;emp=next((e for e in existing if e['name']==name),None)
  if not emp:emp=req('POST','/employees/',{'employee_id':f'DEMO-BOOK-{index:02d}','first_name':'DEMO Booking','last_name':label,'date_of_joining':'2026-11-18','branch_id':1,'timezone':'Asia/Kolkata','create_user_account':False,'bio':'Synthetic sample for requested POS booking checks. No login, payroll, contact, or personal details.','work_categories':categories})
  resource=next((r for r in resources if r['title']==name),None)
  if not resource:resource=req('POST','/srm/industry/resources',{'request_id':str(uuid5(NAMESPACE_URL,'https://besterp.app/demo-booking-staff-20261118/'+label)),'title':name,'resource_type':'employee','employee_id':emp['id'],'timezone':'Asia/Kolkata','weekdays':[0,1,2,3,4,5,6],'opens':'09:00:00','closes':'19:00:00'})
  report['employees'].append({'id':emp['id'],'name':name,'categories':categories,'provider_resource_id':resource['id']});print('Employee ready:',name,flush=True)
 catalog=req('GET','/catalog/items?source=srm&kind=service&limit=100');items=catalog.get('items',[]) if isinstance(catalog,dict) else catalog
 service_specs=[('Technical Visit','DEMO Technical Services'),('Computer Repair','DEMO Technical Services > Computer Repair'),('Tax Consultation','DEMO Consulting > Tax Consultation'),('Routine Inspection','DEMO Maintenance > Routine Inspection')]
 for index,(label,category) in enumerate(service_specs,1):
  name='DEMO Booking '+label;item=next((x for x in items if x['name']==name),None)
  if not item:item=req('POST','/catalog/items?source=srm',{'kind':'service','name':name,'code':f'DEMO-BOOK-SVC-{index:02d}','price':'100.00','currency':'INR','unit':'session','category':'DEMO Booking','tags':['demo'],'description':'Synthetic sample for mobile POS booking verification.','track_inventory':False})
  sid=item['id'];options=req('GET',f'/srm/service-checkout/options?service_id={sid}');policy=options.get('policy')
  if not policy:
   policy=req('PUT','/srm/service-checkout/policies',{'service_product_id':sid,'employee_categories':[category],'default_duration_minutes':30,'min_duration_minutes':30,'max_duration_minutes':30,'booking_required':True,'allow_duration_override':False,'active':True,'required_resource_types':[]})
  expected=[e for e in report['employees'] if any(v==category or v.startswith(category+' > ') for v in e['categories'])]
  existing_options=req('GET',f'/srm/service-checkout/options?service_id={sid}')
  linked={e['employee_id'] for e in existing_options['specialists']}
  for e in expected:
   if e['id'] not in linked:req('PUT','/srm/service-checkout/eligibility',{'policy_id':policy['id'],'expected_policy_revision':policy['revision'],'provider_resource_id':e['provider_resource_id'],'employee_id':e['id'],'active':True})
  final=req('GET',f'/srm/service-checkout/options?service_id={sid}');actual={e['employee_id'] for e in final['specialists']};assert actual=={e['id'] for e in expected},(name,actual,expected)
  wrong=next(e for e in report['employees'] if e not in expected);r=c.put('/srm/service-checkout/eligibility',json={'policy_id':policy['id'],'expected_policy_revision':policy['revision'],'provider_resource_id':wrong['provider_resource_id'],'employee_id':wrong['id'],'active':True});assert r.status_code==409,(r.status_code,r.text)
  result={'id':sid,'name':name,'category':category,'matching_employees':[e['name'] for e in expected],'unrelated_assignment_rejected':True,'options':final};report['services'].append(result);print('Service matching verified:',name,len(actual),flush=True)
 (BASE/'sample-booking-data.json').write_text(json.dumps(report,indent=2));print('VERIFIED',len(report['employees']),'employees',len(report['services']),'services',flush=True)

