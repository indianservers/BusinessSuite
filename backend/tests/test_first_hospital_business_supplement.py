from uuid import uuid4
from sqlalchemy import select
from app.models.company import Branch
from tests.test_public_signup import platform_store,platform_headers,activate,login,PASSWORD
ROOT='/api/v1/access/settings/business-packs'

def test_fresh_approved_hospital_native_doctor_patient_and_appointment(client,db,platform_store,platform_headers,monkeypatch,request):
    from sqlalchemy import event
    import json,re
    from pathlib import Path
    engine=db.get_bind().engine
    def observe_database_error(value):
        original=value.original_exception;diag=getattr(original,'diag',None)
        primary=getattr(diag,'message_primary','') or ''
        result={'type':type(original).__name__,'sqlstate':getattr(original,'pgcode',None),
            'primary':primary if primary.startswith('operator does not exist:') else type(original).__name__,
            'tables':sorted(set(re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z_0-9]*)',value.statement or '',re.I)))}
        (Path(__file__).resolve().parents[2]/'native-database-error-shape.json').write_text(json.dumps(result,indent=2))
    event.listen(engine,'handle_error',observe_database_error)
    request.addfinalizer(lambda:event.remove(engine,'handle_error',observe_database_error))
    from app.main import app
    from sqlalchemy.orm import Session
    # Production auditing has its own control Session, not the active HRMS Core Session.
    # Share only this disposable fixture's outer transaction via a real savepoint.
    monkeypatch.setattr(app.state,'audit_session_factory',lambda:Session(bind=db.get_bind(),join_transaction_mode='create_savepoint'))
    monkeypatch.setattr(app.state,'audit_close_session',True)
    monkeypatch.setattr(app.state,'audit_commit',True)
    from app.core.middleware.audit import AuditLogMiddleware
    import traceback
    audit_failures=[]
    original_persist=AuditLogMiddleware._persist
    def observed_persist(self,request,*args,**kwargs):
        try:return original_persist(self,request,*args,**kwargs)
        except Exception as error:
            audit_failures.append({'path':request.url.path,'type':type(error).__name__,
                'frames':[(frame.name,frame.lineno) for frame in traceback.extract_tb(error.__traceback__)]})
            raise
    monkeypatch.setattr(AuditLogMiddleware,'_persist',observed_persist)
    from app.db.init_db import init_db
    from app.core.config import settings
    monkeypatch.setattr(settings,'BOOTSTRAP_ADMIN_EMAIL','bootstrap-native@example.com')
    monkeypatch.setattr(settings,'BOOTSTRAP_ADMIN_PASSWORD',PASSWORD)
    init_db(db,seed_demo=False)  # Actual deployed catalog/bootstrap; no demo accounts or actor grants.
    email='first-clinic-'+uuid4().hex[:8]+'@example.com'
    submitted=client.post('/api/v1/auth/signup',json={'applicant_type':'company','name':'Clinic Owner',
        'company_name':'First Clinic','email':email,'phone':'+919876543210','requested_modules':['hrms','srm'],'consent':True})
    assert submitted.status_code==202,submitted.text
    from app.platform_owner.models import PlatformSignupRequest
    row=platform_store.query(PlatformSignupRequest).filter_by(email=email).one()
    pending=client.post('/api/v1/auth/login',json={'email':email,'password':PASSWORD})
    assert pending.status_code==401,pending.text
    assert 'access_token' not in pending.json()
    approved=client.post(f'/api/v1/platform/signups/{row.id}/review',headers=platform_headers,json={'decision':'approve',
        'reason':'Reviewed native first clinic setup','version':row.version,'modules':['hrms','srm'],
        'checklist':{'identity':True,'duplicates':True,'modules':True}})
    assert approved.status_code==200,approved.text
    activate(client,approved.json())
    headers=login(client,email)
    platform_store.refresh(row);company=row.company_id
    headers.update({'X-Suite-Organization':str(company)})
    identity=client.get('/api/v1/access/me',headers=headers);assert identity.status_code==200,identity.text
    current=identity.json()
    # Native Company Admin control only; no implicit operational pack grant.
    branch=client.post('/api/v1/branches',headers=headers,json={'name':'New clinic operations','code':'CLINIC','reason':'Explicit empty branch setup'})
    assert branch.status_code==201,branch.text
    native_branch=db.connection().execute(select(Branch.company_id,Branch.is_active).where(Branch.id==branch.json()['id'])).one()
    assert tuple(native_branch)==(company,True)
    bid=branch.json()['id'];headers['X-Suite-Branch']=str(bid)
    draft=client.post(ROOT+'/activations',headers=headers,json={'pack_key':'hospital','expected_revision':0,'reason':'Prepare clinic workflows'})
    assert draft.status_code==201,draft.text
    a=draft.json()
    context=client.post(ROOT+'/contexts',headers=headers,json={'activation_id':a['id'],'activation_revision':a['revision'],
        'branch_id':bid,'expected_revision':0,'reason':'Prepare exact clinic context'})
    assert context.status_code==201,context.text
    c=context.json()
    service=client.post('/api/v1/srm/inventory/items',headers=headers,json={'sku':'CONS-'+uuid4().hex[:10],
        'item_name':'General consultation','product_type':'service','track_inventory':False,'sales_rate':100,'gst_rate':18})
    assert service.status_code==201,service.text
    from app.models.audit import AuditLog
    native_audit=db.connection().execute(select(AuditLog.entity_type,AuditLog.entity_id).where(
        AuditLog.organization_id==company,AuditLog.endpoint=='/srm/inventory/items',AuditLog.method=='POST')).one()
    assert tuple(native_audit)==('canonical:srm_product_created',service.json()['id'])
    shared=client.put(ROOT+f"/contexts/{c['id']}/masters",headers=headers,json={'kind':'products','id':service.json()['id'],
        'active':True,'expected_context_revision':c['revision'],'expected_revision':0,'reason':'Explicit consultation availability'})
    assert shared.status_code==200,shared.text
    config=client.get(ROOT+'/configuration',headers=headers);assert config.status_code==200,config.text
    c=next(x for x in config.json()['contexts'] if x['id']==c['id'])
    from app.models.user import User
    user=db.query(User).filter_by(email=email).one()
    granted=client.put(ROOT+f"/contexts/{c['id']}/grants/{user.id}",headers=headers,json={'context_revision':c['revision'],
        'role':'hospital_manager','active':True,'expected_revision':0,'reason':'Explicit operational manager grant'})
    assert granted.status_code==200,granted.text
    ready=client.get(ROOT+'/readiness',headers=headers,params={'pack_key':'hospital','branch_id':bid})
    if ready.status_code==200 and not ready.json()['ready']:
        # Development evidence only: schema names/types/FKs, never record bodies.
        from sqlalchemy import inspect
        from app.db.base_class import Base
        from pathlib import Path
        import json
        inspector=inspect(db.connection())
        missing=sorted(set(inspector.get_table_names())-set(Base.metadata.tables)-{'alembic_version'})
        details={name:{'columns':[{'name':column['name'],'type':str(column['type']),'nullable':column['nullable']}
            for column in inspector.get_columns(name)],'foreign_keys':[{'columns':key['constrained_columns'],
            'parent':key['referred_table'],'parent_columns':key['referred_columns']} for key in inspector.get_foreign_keys(name)]} for name in missing}
        (Path(__file__).resolve().parents[2]/'early-native-physical-inventory-delta.json').write_text(json.dumps(details,indent=2))
    assert ready.status_code==200 and ready.json()['ready'],ready.text
    parent=client.post(ROOT+f"/activations/{a['id']}/activate",headers=headers,json={'expected_revision':a['revision'],'reason':'Activate reviewed clinic release'})
    assert parent.status_code==200,parent.text
    enabled=client.post(ROOT+f"/contexts/{c['id']}/activate",headers=headers,json={'expected_revision':c['revision'],
        'activation_revision':parent.json()['revision'],'reason':'Activate verified empty clinic branch'})
    assert enabled.status_code==200,enabled.text
    selected={**headers,'X-Suite-Pack-Context':str(c['id'])}
    actual=client.get('/api/v1/srm/industry/capabilities',headers=selected)
    assert actual.status_code==200,actual.text
    assert actual.json()['operational_scope']['context_id']==c['id']
    assert actual.json()['operational_scope']['pack_key']=='hospital'
    assert actual.json()['checkout_create'] is True

    doctor=client.post('/api/v1/employees/',headers=selected,json={'employee_id':'DOC-'+uuid4().hex[:12],
        'first_name':'Fictional','last_name':'Doctor','branch_id':bid,'date_of_joining':'2026-01-01','create_user_account':False})
    assert doctor.status_code==201,doctor.text
    shared_employee=client.put(ROOT+f"/contexts/{c['id']}/masters",headers=selected,json={'kind':'employees','id':doctor.json()['id'],
        'active':True,'expected_context_revision':enabled.json()['revision'],'expected_revision':0,'reason':'Explicit canonical Doctor availability'})
    assert shared_employee.status_code==200,shared_employee.text
    provider=client.post('/api/v1/srm/industry/resources',headers=selected,json={'request_id':str(uuid4()),'title':'Fictional consultation Doctor',
        'resource_type':'doctor','employee_id':doctor.json()['id'],'timezone':'Asia/Kolkata','weekdays':list(range(7)),'opens':'09:00','closes':'19:00'})
    assert provider.status_code==201,provider.text
    patient=client.post('/api/v1/srm/pos/customers',headers=selected,json={'name':'Fictional First Patient','address':'Fictional Clinic Lane',
        'city':'Mumbai','state':'Maharashtra','country':'IN'})
    assert patient.status_code==201,patient.text
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    starts=(datetime.now(ZoneInfo('Asia/Kolkata'))+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
    appointment=client.post('/api/v1/srm/industry/appointments',headers=selected,json={'request_id':str(uuid4()),'title':'Fictional first consultation',
        'customer_id':patient.json()['id'],'service_id':service.json()['id'],'resource_ids':[provider.json()['id']],
        'starts_at':starts.isoformat(),'duration_minutes':30})
    assert appointment.status_code==201,appointment.text
    assert appointment.json()['status']=='booked'
    planned=client.get(f"/api/v1/employees/{doctor.json()['id']}/planned-services",headers=selected,
        params={'from_at':(starts-timedelta(hours=1)).isoformat(),'until_at':(starts+timedelta(hours=1)).isoformat()})
    assert planned.status_code==200,planned.text
    assert len(planned.json()['items'])==1 and planned.json()['items'][0]['planned_minutes']==30
    from app.models.timesheet import TimesheetEntry
    from app.apps.project_management.models import PMSTimeLog
    assert db.query(TimesheetEntry).count()==db.query(PMSTimeLog).count()==0
    from decimal import Decimal
    payment_path=f"/api/v1/srm/industry/appointments/{appointment.json()['id']}/payments"
    partial={'request_id':str(uuid4()),'expected_revision':appointment.json()['revision'],'amount':'30.00',
        'payment_method':'bank_transfer','reference_number':'Fictional first hospital payment'}
    first=client.post(payment_path,headers=selected,json=partial)
    assert first.status_code==201,first.text
    assert Decimal(first.json()['balance'])==Decimal('88.00') and len(first.json()['receipts'])==1
    replay=client.post(payment_path,headers=selected,json=partial)
    assert replay.status_code==201,replay.text
    assert replay.json()==first.json()
    final=client.post(payment_path,headers=selected,json={'request_id':str(uuid4()),'expected_revision':first.json()['revision'],
        'amount':'88.00','payment_method':'bank_transfer','reference_number':'Fictional final hospital payment'})
    assert final.status_code==201,final.text
    assert Decimal(final.json()['balance'])==0 and Decimal(final.json()['advance'])==Decimal('118.00')
    assert len(final.json()['receipts'])==2
    assert db.query(TimesheetEntry).count()==db.query(PMSTimeLog).count()==0
    from app.access.models import AccessPolicy,AccessMembership
    from app.apps.crm.models import CRMCompany
    policy=db.query(AccessPolicy).filter_by(company_id=company,user_id=user.id).one()
    policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'actions':['view']}}
    policy.version+=1
    db.query(AccessMembership).filter_by(company_id=company,user_id=user.id).one().is_admin=False
    db.commit()
    count=db.query(CRMCompany).count()
    denied=client.post('/api/v1/srm/pos/customers',headers=selected,json={'name':'Blocked roleless native policy',
        'address':'Fictional Clinic Lane','city':'Mumbai','state':'Maharashtra','country':'IN'})
    assert denied.status_code==403,denied.text
    assert db.query(CRMCompany).count()==count
    assert audit_failures==[],audit_failures
