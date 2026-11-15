"""Salon native workforce, keyed service bookings and money remain canonical."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import json
import pytest
from app.core.security import create_access_token
from app.models.user import User,Permission
from app.models.employee import Employee
from app.access.models import AccessPolicy,AccessMembership
from app.branches.models import BranchGrant
from app.business_packs.models import PackMasterAvailability
from tests.test_business_pack_http_integration import hospital_http,grant,native_actor,create
from tests.test_service_checkout import scenario,catalog,directory_identity


def allowed(client,method,path,headers,body=None,status=200):
    result=client.request(method,path,headers=headers,**({'json':body} if body is not None else {}))
    assert result.status_code==status,(path,result.text)
    return result.json()


@pytest.fixture
def salon_native(client,db,hospital_http,superuser_headers):
    from app.apps.srm.models import SRMProduct
    hospital_headers,manager,branch,hospital_context,_,hospital_payload=hospital_http
    for name in ['employee_view','timesheet_view']:
        permission=db.query(Permission).filter_by(name=name).first()
        if permission is None:permission=Permission(name=name,module='hrms');db.add(permission);db.flush()
        if permission not in manager.role.permissions:manager.role.permissions.append(permission)
    policy=db.query(AccessPolicy).filter_by(user_id=manager.id,company_id=1).one()
    policy.grants={**policy.grants,'hrms':{'enabled':True,'permissions':['employee_view','timesheet_view'],'actions':['view'],'scope':'organization'}}
    salon,role=grant(db,manager,branch,'salon','salon_manager')
    headers={**hospital_headers,'X-Suite-Pack-Context':str(salon.id)}
    department=allowed(client,'POST','/api/v1/company/departments/',superuser_headers,{'branch_id':branch,'name':'Salon services'},201)
    designation=allowed(client,'POST','/api/v1/company/designations/',superuser_headers,{'department_id':department['id'],'name':'Stylist'},201)
    employees=[];workers=[];worker_headers=[]
    for index,name in enumerate(['Nia','Tara']):
        born=allowed(client,'POST','/api/v1/employees/',superuser_headers,{
            'employee_id':'SALON-'+uuid4().hex[:12],'first_name':name,'last_name':'Salon QA','branch_id':branch,
            'department_id':department['id'],'designation_id':designation['id'],'date_of_joining':'2024-01-01','create_user_account':True,'user_email':uuid4().hex+'@example.com','user_password':'FictionalSalon!2026'},201)
        employee=db.get(Employee,born['id']);worker=db.get(User,employee.user_id)
        assert worker is not None and not worker.is_superuser
        worker.organization_id=1
        names=['srm_admin','employee_view','timesheet_view']
        for name in names:
            permission=db.query(Permission).filter_by(name=name).first()
            if permission is None:permission=Permission(name=name,module='srm' if name=='srm_admin' else 'hrms');db.add(permission);db.flush()
            if permission not in worker.role.permissions:worker.role.permissions.append(permission)
        db.add(BranchGrant(company_id=1,branch_id=branch,user_id=worker.id,can_write=True))
        if not db.query(AccessMembership).filter_by(company_id=1,user_id=worker.id).first():db.add(AccessMembership(company_id=1,user_id=worker.id,active=True))
        db.add(AccessPolicy(company_id=1,user_id=worker.id,status='active',grants={
            'srm':{'enabled':True,'permissions':['srm_admin'],'actions':['view','create','edit','approve'],'scope':'own'},
            'hrms':{'enabled':True,'permissions':['employee_view','timesheet_view'],'actions':['view'],'scope':'own'}}))
        grant(db,worker,branch,'salon','stylist',salon)
        workers.append(worker);employees.append(employee)
        worker_headers.append({'Authorization':'Bearer '+create_access_token(worker.id),'X-Suite-Organization':'1','X-Suite-Branch':str(branch),'X-Suite-Pack-Context':str(salon.id)})
    service=db.get(SRMProduct,hospital_payload['lines'][0]['product_id'])
    for table,ident in [('crm_companies',101),('srm_products',service.id),*[('employees',employee.id) for employee in employees]]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=salon.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    extra=allowed(client,'POST','/api/v1/catalog/items?source=srm',headers,{
        'kind':'service','name':'Salon colour finish','code':'SALON-COLOUR-'+uuid4().hex[:12],'price':150,'tax':18,'currency':'INR','unit':'service','status':'Active'},201)
    providers=[]
    for index,employee in enumerate(employees):
        providers.append(allowed(client,'POST','/api/v1/srm/industry/resources',headers,{
            'request_id':str(uuid4()),'title':employee.first_name+' stylist','resource_type':'stylist','employee_id':employee.id,
            'timezone':'UTC','weekdays':list(range(7)),'opens':'00:00:00','closes':'23:59:00'},201))
    policies=[];eligibilities={}
    for service_id,minutes in [(service.id,30),(extra['id'],60)]:
        policy=allowed(client,'PUT','/api/v1/srm/service-checkout/policies',headers,{'service_product_id':service_id,'default_duration_minutes':minutes,
            'min_duration_minutes':15,'max_duration_minutes':90,'booking_required':True,'allow_duration_override':True})
        policies.append(policy)
        for index,provider in enumerate(providers):
            eligible=allowed(client,'PUT','/api/v1/srm/service-checkout/eligibility',headers,{'policy_id':policy['id'],'expected_policy_revision':policy['revision'],
                'provider_resource_id':provider['id'],'employee_id':employees[index].id})
            eligibilities[(service_id,index)]=eligible
    register=allowed(client,'POST','/api/v1/srm/pos/sessions',headers,{'opening_cash':0,'register_name':'Fictional salon counter','branch':'Salon branch'},201)
    register_id=register.get('id') or register.get('session',{}).get('id');assert register_id
    start=(datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
    specifications=[(service.id,0,30,start),(service.id,1,45,start),(extra['id'],0,60,start+timedelta(minutes=90))]
    lines=[]
    for service_id,index,minutes,when in specifications:
        p=next(value for value in policies if value['service_product_id']==service_id);e=eligibilities[(service_id,index)]
        lines.append({'client_line_key':str(uuid4()),'line_kind':'booked_service','product_id':service_id,'booking':{
            'policy_id':p['id'],'expected_policy_revision':p['revision'],'eligibility_id':e['id'],'expected_eligibility_revision':e['revision'],
            'provider_resource_id':providers[index]['id'],'employee_id':employees[index].id,'starts_at':when.isoformat(),'duration_minutes':minutes}})
    payload={'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register_id,'lines':lines,
        'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'100'},{'payment_key':str(uuid4()),'method':'card','amount':'313','reference':'Fictional terminal'}]}
    cashier_headers,cashier=native_actor(db,branch);grant(db,cashier,branch,'salon','cashier',salon)
    cashier_headers={**cashier_headers,'X-Suite-Pack-Context':str(salon.id)}
    db.commit()
    return SimpleNamespace(db=db,client=client,headers=headers,manager=manager,branch=branch,context=salon.id,employees=employees,
        workers=workers,worker_headers=worker_headers,providers=providers,policies=policies,services=[service.id,extra['id']],
        payload=payload,hospital_headers=hospital_headers,hospital_payload=hospital_payload,cashier_headers=cashier_headers,start=start)


def test_salon_native_roles_plans_terms_and_payment_status_policies(salon_native):
    from app.apps.srm.models import SRMReceipt,SRMInvoice
    from app.models.timesheet import TimesheetEntry
    from app.apps.project_management.models import PMSTimeLog
    n=salon_native;c=n.client;db=n.db
    hospital=create(c,n.hospital_headers,n.hospital_payload)
    result=create(c,n.headers,n.payload)
    assert len(result['lines'])==3 and len({row['client_line_key'] for row in result['lines']})==3
    assert result['invoice']['balance']=='0.00' and Decimal(result['invoice']['total'])==413
    assert sorted(Decimal(row['amount']) for row in result['receipts'])==[100,313]
    terms=allowed(c,'GET','/api/v1/access/settings/business-profile/effective',n.headers)
    assert terms['packKey']=='salon' and terms['terms']['provider']==['Stylist','Stylists'] and terms['terms']['customer']==['Customer','Customers']
    hospital_terms=allowed(c,'GET','/api/v1/access/settings/business-profile/effective',n.hospital_headers)
    assert hospital_terms['terms']['provider']==['Doctor','Doctors'] and hospital_terms['terms']['customer']==['Patient','Patients']
    assert c.get('/api/v1/srm/service-checkout/'+str(hospital['id']),headers=n.headers).status_code==404
    params={'from_at':(n.start-timedelta(days=1)).isoformat(),'until_at':(n.start+timedelta(days=1)).isoformat()}
    plan=c.get(f'/api/v1/employees/{n.employees[0].id}/planned-services',headers=n.worker_headers[0],params=params)
    assert plan.status_code==200,plan.text
    assert sorted(row['planned_minutes'] for row in plan.json()['items'])==[30,60]
    foreign_plan=c.get(f'/api/v1/employees/{n.employees[1].id}/planned-services',headers=n.worker_headers[0],params=params)
    assert foreign_plan.status_code==404,foreign_plan.text
    own=allowed(c,'GET','/api/v1/srm/industry/records?kind=appointment',n.worker_headers[0])
    own_ids={row['id'] for row in own['items']};expected={result['lines'][index]['appointment_id'] for index in (0,2)}
    assert own_ids==expected
    assert c.post(f"/api/v1/srm/service-checkout/{result['id']}/payments",headers=n.worker_headers[0],json={'expected_revision':result['revision'],'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'1'}}).status_code==403
    schedule=c.get('/api/v1/srm/service-checkout/options',headers=n.cashier_headers,params={'service_id':n.services[0]})
    assert schedule.status_code==403,schedule.text
    before=[(row.id,row.amount,row.status) for row in db.query(SRMReceipt)]
    appointment=result['lines'][0]['appointment_id']
    rejected=c.post(f'/api/v1/srm/industry/records/{appointment}/transition',headers=n.headers,json={'expected_revision':1,'status':'no_show','reason':'Future no-show must be rejected'})
    assert rejected.status_code==409,rejected.text
    cancelled=allowed(c,'POST',f'/api/v1/srm/industry/records/{appointment}/transition',n.headers,{'expected_revision':1,'status':'cancelled','reason':'Customer cancelled paid appointment'})
    assert cancelled['status']=='cancelled'
    assert [(row.id,row.amount,row.status) for row in db.query(SRMReceipt)]==before
    assert db.get(SRMInvoice,result['invoice']['id']).balance_amount==0
    unpaid={**n.payload,'request_id':str(uuid4()),'payments':[],'lines':[{**n.payload['lines'][0],'client_line_key':str(uuid4()),'booking':{**n.payload['lines'][0]['booking'],'starts_at':(n.start+timedelta(days=1)).isoformat()}}]}
    due=create(c,n.headers,unpaid);assert Decimal(due['invoice']['balance'])==118
    a=due['lines'][0]['appointment_id'];allowed(c,'POST',f'/api/v1/srm/industry/records/{a}/transition',n.headers,{'expected_revision':1,'status':'cancelled','reason':'Customer cancelled unpaid appointment'})
    assert db.get(SRMInvoice,due['invoice']['id']).balance_amount==118 and [(row.id,row.amount,row.status) for row in db.query(SRMReceipt)]==before
    past=allowed(c,'POST','/api/v1/srm/industry/appointments',n.headers,{'request_id':str(uuid4()),'title':'Fictional missed salon visit','customer_id':101,'service_id':n.services[0],
        'resource_ids':[n.providers[0]['id']],'starts_at':(n.start-timedelta(days=3)).isoformat(),'duration_minutes':30},201)
    no_show=allowed(c,'POST',f"/api/v1/srm/industry/records/{past['id']}/transition",n.headers,{'expected_revision':1,'status':'no_show','reason':'Customer did not attend'})
    assert no_show['status']=='no_show' and no_show['invoice_id'] is None
    assert db.query(TimesheetEntry).count()==db.query(PMSTimeLog).count()==0


def test_salon_real_native_browser_three_bookings_profiles_and_timesheets(salon_native,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.models import SRMInvoice,SRMReceipt,SRMProduct
    from app.apps.srm.service_checkout_models import POSServiceCheckout,POSServiceOccurrence
    from app.models.timesheet import TimesheetEntry
    from app.apps.project_management.models import PMSTimeLog
    from app.business_packs.runtime import RUNTIME_SUPPORT
    n=salon_native;db=n.db
    buyer=db.get(CRMCompany,101)
    specs=[{'product_id':line['product_id'],'service_name':db.get(SRMProduct,line['product_id']).item_name,
        'employee_id':line['booking']['employee_id'],'starts_at':line['booking']['starts_at'],'minutes':line['booking']['duration_minutes']} for line in n.payload['lines']]
    before=(db.query(TimesheetEntry).count(),db.query(PMSTimeLog).count())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','salon-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':n.headers['Authorization'].split(' ',1)[1],'branch':str(n.branch),'context':str(n.context),
        'customer_name':buyer.name,'employee_id':n.employees[0].id,'specs':specs}))
    test_control_center_real_browser(n.client,db,None,n.headers)
    checkout=db.query(POSServiceCheckout).one();invoice=db.get(SRMInvoice,checkout.invoice_id)
    assert invoice.total_amount==invoice.paid_amount==413 and invoice.balance_amount==0
    assert sorted(row.amount for row in db.query(SRMReceipt))==[100,313]
    rows=db.query(POSServiceOccurrence).order_by(POSServiceOccurrence.id).all()
    assert len(rows)==3 and [row.employee_id for row in rows]==[n.employees[0].id,n.employees[1].id,n.employees[0].id]
    assert (db.query(TimesheetEntry).count(),db.query(PMSTimeLog).count())==before
    assert not RUNTIME_SUPPORT
