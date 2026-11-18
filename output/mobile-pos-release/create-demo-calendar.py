from dotenv import load_dotenv
load_dotenv('/srv/business-suite/shared/backend.env')
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from uuid import uuid5,NAMESPACE_URL
from app.core.security import create_access_token
import httpx,json
from pathlib import Path
h={'Authorization':'Bearer '+create_access_token(1,timedelta(minutes=10)),'X-Suite-Organization':'1','X-Suite-Branch':'1'}
report={'company_id':1,'branch_id':1,'employees':[],'resources':[],'bookings':[]}
def uid(label):return str(uuid5(NAMESPACE_URL,'https://besterp.app/demo-calendar-20261117/'+label))
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',headers=h,timeout=45,follow_redirects=True) as client:
 def get(path):
  r=client.get(path);r.raise_for_status();return r.json()
 def post(path,data):
  r=client.post(path,json=data)
  if r.status_code>=400:raise RuntimeError(path+' '+str(r.status_code)+' '+r.text[:1200])
  return r.json()
 customers=get('/srm/business/customers')['items'];customer=next((v for v in customers if v.get('name')=='DEMO Calendar Customer'),None)
 if not customer:customer=post('/srm/business/customers',{'name':'DEMO Calendar Customer'})
 report['customer_id']=customer['id'];print('Demo customer ready',customer['id'],flush=True)
 resources=get('/srm/industry/records?kind=resource')['items']
 for n in [1,2]:
  name='DEMO Calendar Staff '+str(n);employees=get('/srm/industry/employee-options?search=DEMO%20Calendar')['items'];emp=next((e for e in employees if e['name']==name),None)
  if not emp:emp=post('/employees/',{'first_name':'DEMO Calendar','last_name':'Staff '+str(n),'date_of_joining':'2026-11-17','branch_id':1,'timezone':'Asia/Kolkata','bio':'Synthetic employee for the requested calendar preview. No login or contact details.','work_categories':['Service support']})
  report['employees'].append(emp['id'])
  title='DEMO Calendar Specialist '+str(n);resource=next((r for r in resources if r['title']==title),None)
  if not resource:resource=post('/srm/industry/resources',{'request_id':uid('provider-'+str(n)),'title':title,'resource_type':'technician','employee_id':emp['id'],'timezone':'Asia/Kolkata','weekdays':[0,1,2,3,4,5],'opens':'09:00:00','closes':'18:00:00'})
  report['resources'].append(resource['id']);print('Demo provider ready',resource['id'],flush=True)
 days=[18,19,20,21,23];slots=[(9,30),(11,0),(13,30),(15,0)]
 for index in range(20):
  day=days[index//4];hour,minute=slots[index%4];start=datetime(2026,11,day,hour,minute,tzinfo=ZoneInfo('Asia/Kolkata'));provider=report['resources'][index%2]
  data={'request_id':uid('booking-'+str(index+1)),'title':f'DEMO Calendar Booking {index+1:02d}','customer_id':customer['id'],'service_id':9,'resource_ids':[provider],'starts_at':start.isoformat(),'duration_minutes':30 if index%2==0 else 45,'create_pms_task':False,'notes':'Synthetic demo booking created at your request to preview Calendar and Gantt. No payment or invoice.'}
  booking=post('/srm/industry/appointments',data);report['bookings'].append({'id':booking['id'],'title':data['title'],'starts_at':start.isoformat()});print('Created/verified',data['title'],booking['id'],flush=True)
 projection=get('/employees/planned-services?from_at=2026-11-17T00%3A00%3A00%2B05%3A30&until_at=2026-11-24T00%3A00%3A00%2B05%3A30&limit=100')
 ids={row['appointment_id'] for row in projection['items']};assert all(b['id'] in ids for b in report['bookings']),str(ids)
 report['verified_in_schedule']=len(report['bookings']);Path('/srv/business-suite/shared/mobile-pos-20261117-173930/demo-calendar-records.json').write_text(json.dumps(report,indent=2));print('VERIFIED 20 demo calendar bookings',flush=True)
