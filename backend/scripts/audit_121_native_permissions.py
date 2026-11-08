"""Read-only actor probes for the individual native UI lifecycle endpoints."""
import json,sqlite3,uuid,requests
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/crud-permissions-121-final';BASE='http://127.0.0.1:1582/api/v1'
s=requests.Session()
r=s.post(BASE+'/auth/login',json={'email':'reader@crudqa.example.com','password':'CrudQA@12345'},timeout=30);r.raise_for_status();actor=r.json();headers={'Authorization':'Bearer '+actor['access_token']};employee=actor['employee_id']
db=sqlite3.connect('file:'+str(ROOT/'.local/crud121-1582.sqlite')+'?mode=ro',uri=True)
def ident(table):return db.execute('SELECT id FROM '+table+' ORDER BY id DESC LIMIT 1').fetchone()[0]
project=ident('pms_projects');task=ident('pms_tasks');invoice=ident('srm_invoices');goal=ident('performance_goals');voucher=ident('fam_vouchers');report=ident('analytics_reports');sheet=ident('timesheets');claim=ident('expense_claims');asset_assignment=ident('asset_assignments');certificate=ident('employee_certificates')
today=date.today().isoformat();tomorrow=(date.today()+timedelta(days=1)).isoformat()
checks=[
 ('POST','/project-management/work/tasks/'+str(task)+'/start',{}),
 ('POST','/project-management/work/tasks/'+str(task)+'/progress',{'progress_percent':50,'notes':'Denied reader change'}),
 ('POST','/project-management/work/tasks/'+str(task)+'/submissions',{'notes':'Denied reader evidence','draft':False,'confirmed':True}),
 ('PATCH','/project-management/management/tasks/'+str(task),{'status':'In Progress'}),
 ('POST','/attendance/bulk-entry',{'entries':[{'employee_id':employee,'date':today,'status':'WFH','hours_worked':8,'ot_hours':0}]}),
 ('POST','/attendance/locks',{'month':date.today().month,'year':date.today().year,'reason':'Denied reader lock'}),
 ('PUT',f'/assets/assignments/{asset_assignment}/acknowledge',None),
 ('PUT',f'/assets/assignments/{asset_assignment}/return?condition_at_return=Good',None),
 ('PUT',f'/documents/certificates/{certificate}/verify',{'verification_status':'Verified','verification_notes':'Denied reader verification'}),
 ('POST','/performance/goals',{'employee_id':employee,'cycle_id':1,'title':'Denied self goal','target_date':tomorrow}),
 ('PUT',f'/performance/goals/{goal}',{'status':'Completed'}),
 ('POST','/leave/apply',{'employee_id':employee,'leave_type_id':1,'from_date':tomorrow,'to_date':tomorrow,'reason':'Denied reader request'}),
 ('POST',f'/timesheets/{sheet}/entries',{'date':today,'hours':1,'description':'Denied reader hours'}),
 ('PUT',f'/timesheets/{sheet}/submit',{}),
 ('PUT',f'/timesheets/{sheet}/review',{'status':'Approved','comments':'Denied reader review'}),
 ('POST','/expenses/claims',{'category':'Test','expense_date':today,'claim_amount':'1.00','currency':'INR','business_purpose':'Denied self expense'}),
 ('PUT',f'/expenses/claims/{claim}/manager-review',{'decision':'approved','notes':'Denied reader review'}),
 ('PUT',f'/expenses/claims/{claim}/finance-review',{'decision':'approved','notes':'Denied reader review'}),
 ('PUT',f'/expenses/claims/{claim}/reimburse',{'payment_reference':'NO-TRANSFER-DENIED','notes':'Denied reader action'}),
 ('POST','/payroll/run',{'month':date.today().month,'year':date.today().year,'force_run':False}),
 ('POST','/srm/invoices/manual',{'customer_id':101,'request_id':str(uuid.uuid4()),'lines':[{'description':'Denied reader invoice','quantity':1,'unit_price':1}]}),
 ('POST',f'/srm/invoices/{invoice}/approve',{}),
 ('POST',f'/srm/business/invoices/{invoice}/payments',{'request_id':str(uuid.uuid4()),'amount':'1','reference':'NO-TRANSFER-DENIED','payment_method':'bank_transfer','receipt_date':today}),
 ('POST',f'/fam/vouchers/{voucher}/post',{}),
 ('POST',f'/fam/vouchers/{voucher}/reverse',{}),
 ('POST','/fam/opening-balances/post',{'financial_year_id':1}),
 ('POST',f'/analytics/reports/{report}/run',{}),
 ('POST',f'/analytics/reports/{report}/export',{'export_type':'csv'}),
 ('POST','/integrations/whatsapp/templates',{'name':'denied_reader','language':'en_US','category':'UTILITY','body':'Denied reader template'})
]
results=[]
for method,path,body in checks:
 response=s.request(method,BASE+path,headers=headers,json=body,timeout=30)
 results.append({'method':method,'path':path,'actor':'reader','status':response.status_code,'passed':response.status_code in [401,403,404]})
 print(method,path,response.status_code,flush=True)
response=s.post(BASE+'/documents/certificates',headers=headers,data={'employee_id':employee,'category':'Training','certificate_type':'Test','title':'Denied own certificate'},files={'file':('denied.txt',b'Synthetic permission probe','text/plain')},timeout=30)
results.append({'method':'POST','path':'/documents/certificates','actor':'reader-own-profile','status':response.status_code,'passed':response.status_code in [401,403,404]})
(OUT/'native-action-permissions.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps({'checks':len(results),'passed':sum(x['passed'] for x in results),'failed':[x for x in results if not x['passed']]}))
