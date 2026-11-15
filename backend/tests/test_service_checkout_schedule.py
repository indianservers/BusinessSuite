"""Grouped reschedule changes the native plan and typed occurrence atomically."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import update
from app.apps.srm.service_checkout import checkout,grouped_schedule,reschedule_grouped,servicecheckout_state,save_eligibility
from app.apps.srm.service_checkout_schemas import GroupedRescheduleInput,EligibilityInput
from app.apps.srm.service_checkout_models import POSServiceOccurrence,POSCheckoutLine
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMSalesOrder,SRMInvoice
from app.models.employee import Employee
from app.services.planned_services import planned_services
from tests.test_service_checkout import enable_audited_pack,audited_pack_writer,scenario,catalog,directory_identity,enable_pack
from tests.test_srm_native_transaction_operations import native_writer


def group(db,scenario):
    user,branch,catalog,basket=scenario
    result=checkout(basket(False),db,user)
    ident=next(line['appointment_id'] for line in result['lines'] if line['appointment_id'])
    return result,ident


def move(current,*,hours=2):
    booking={**current['booking'],'starts_at':datetime.fromisoformat(current['booking']['starts_at'])+timedelta(hours=hours)}
    return GroupedRescheduleInput.model_validate({'expected_appointment_revision':current['appointment_revision'],
        'expected_occurrence_revision':current['occurrence_revision'],'booking':booking,'additional_resource_ids':current['additional_resource_ids']})


def test_readonly_schedule_get_no_finance_or_customer_and_atomic_move(db,scenario):
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        result,ident=group(db,scenario)
        db.info['security_write_request']=False
        current=grouped_schedule(ident,db,user)
        assert set(current)=={'appointment_id','service_id','provider_timezone','appointment_revision','occurrence_id','occurrence_revision','booking','additional_resource_ids'}
        assert not any(word in json.dumps(current) for word in ('customer','invoice','amount','price','paid'))
        db.info['security_write_request']=True
        before=servicecheckout_state(db,user,db.info['branch_context'],result['id'])
        moved=reschedule_grouped(ident,move(current),db,user)
        assert moved['appointment_revision']==current['appointment_revision']+1
        assert moved['occurrence_revision']==current['occurrence_revision']+1
        assert grouped_schedule(ident,db,user)==moved
        assert servicecheckout_state(db,user,db.info['branch_context'],result['id'])==before
        occurrence=db.get(POSServiceOccurrence,current['occurrence_id']);native=db.get(IndustryRecord,ident)
        assert native.starts_at==occurrence.starts_at and native.ends_at==occurrence.ends_at
        assert 'service_checkout_reschedule' not in db.info


def test_change_employee_add_resource_updates_planned_projection_not_actual_hours(db,scenario):
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        result,ident=group(db,scenario);current=grouped_schedule(ident,db,user)
        old_employee=current['booking']['employee_id']
        employee=Employee(employee_id='NEW-'+uuid4().hex,first_name='New',last_name='Specialist',branch_id=branch,
            date_of_joining=datetime.now().date(),status='Active')
        db.add(employee);db.flush()
        original=db.get(IndustryRecord,current['booking']['provider_resource_id'])
        provider=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='New provider',status='active',request_id=str(uuid4()),created_by=user.id,
            data={**original.data,'employee_id':employee.id})
        chair=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Extra chair',status='active',request_id=str(uuid4()),created_by=user.id,
            data={**original.data,'employee_id':None,'resource_type':'chair'})
        db.add_all([provider,chair]);db.commit()
        eligible=save_eligibility(EligibilityInput(policy_id=current['booking']['policy_id'],expected_policy_revision=current['booking']['expected_policy_revision'],
            provider_resource_id=provider.id,employee_id=employee.id),db,user)
        data=move(current);data.booking.provider_resource_id=provider.id;data.booking.employee_id=employee.id
        data.booking.eligibility_id=eligible['id'];data.booking.expected_eligibility_revision=eligible['revision'];data.additional_resource_ids=[chair.id]
        moved=reschedule_grouped(ident,data,db,user)
        assert moved['booking']['employee_id']==employee.id and moved['additional_resource_ids']==[chair.id]
        begin=data.booking.starts_at-timedelta(days=1);end=begin+timedelta(days=3)
        old=planned_services(db,user,db.info['branch_context'],old_employee,begin,end)
        new=planned_services(db,user,db.info['branch_context'],employee.id,begin,end)
        assert ident not in {x['appointment_id'] for x in old['items']}
        item=next(x for x in new['items'] if x['appointment_id']==ident)
        assert datetime.fromisoformat(item['starts_at'])==data.booking.starts_at and item['planned_minutes']==30
        from app.models.timesheet import TimesheetEntry
        from app.apps.project_management.models import PMSTimesheet
        assert db.query(TimesheetEntry).count()==db.query(PMSTimesheet).count()==0

@pytest.mark.parametrize('case',['appointment_revision','occurrence_revision','policy_revision','eligibility_revision','wrong_employee','unknown_provider','past','conflict'])
def test_invalid_reschedule_keeps_both_canonical_rows_unchanged(db,scenario,case):
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        result,ident=group(db,scenario);current=grouped_schedule(ident,db,user);data=move(current)
        if case=='appointment_revision':data.expected_appointment_revision+=1
        elif case=='occurrence_revision':data.expected_occurrence_revision+=1
        elif case=='policy_revision':data.booking.expected_policy_revision+=1
        elif case=='eligibility_revision':data.booking.expected_eligibility_revision+=1
        elif case=='wrong_employee':data.booking.employee_id=999999
        elif case=='unknown_provider':data.booking.provider_resource_id=999999
        elif case=='past':data.booking.starts_at=datetime.now(timezone.utc)-timedelta(days=1)
        elif case=='conflict':data.booking.starts_at=datetime.fromisoformat(current['booking']['starts_at'])+timedelta(hours=1)
        with pytest.raises(HTTPException):reschedule_grouped(ident,data,db,user)
        assert grouped_schedule(ident,db,user)==current
        assert db.query(SRMSalesOrder).count()==db.query(SRMInvoice).count()==1
        assert 'service_checkout_reschedule' not in db.info


def test_reschedule_outer_rollback_and_schedule_drift_fail_closed(db,scenario):
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        result,ident=group(db,scenario);current=grouped_schedule(ident,db,user)
        with pytest.raises(RuntimeError):
            with db.begin_nested():
                reschedule_grouped(ident,move(current),db,user,commit=False)
                raise RuntimeError('caller rollback')
        assert grouped_schedule(ident,db,user)==current
        db.connection().execute(update(IndustryRecord.__table__).where(IndustryRecord.id==ident).values(
            starts_at=datetime.fromisoformat(current['booking']['starts_at'])+timedelta(hours=2)))
        db.expire_all()
        with pytest.raises(HTTPException) as error:servicecheckout_state(db,user,db.info['branch_context'],result['id'])
        assert error.value.status_code==409
        with pytest.raises(HTTPException) as error:grouped_schedule(ident,db,user)
        assert error.value.status_code==409


def test_bill_note_preserved_separately_from_line_note(db,scenario):
    user,branch,catalog,basket=scenario;data=basket(False);data.note='Bill-level instruction';data.lines[0].note='Line-level instruction'
    with native_writer(db,user,branch):result=checkout(data,db,user)
    assert db.get(SRMSalesOrder,result['sales_order_id']).terms==data.note
    from app.apps.srm.models import SRMSalesOrderLine
    assert db.query(SRMSalesOrderLine).filter_by(sales_order_id=result['sales_order_id']).order_by(SRMSalesOrderLine.id).first().metadata_json['note']==data.lines[0].note


def test_schedule_does_not_auto_acknowledge_changed_policy(db,scenario):
    from app.apps.srm.service_checkout_models import ServiceBookingPolicy
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        result,ident=group(db,scenario);current=grouped_schedule(ident,db,user)
        policy=db.get(ServiceBookingPolicy,current['booking']['policy_id']);policy.allow_duration_override=True;db.commit()
        assert policy.revision!=current['booking']['expected_policy_revision']
        assert grouped_schedule(ident,db,user)['booking']['expected_policy_revision']==current['booking']['expected_policy_revision']
        with pytest.raises(HTTPException) as error:reschedule_grouped(ident,move(current),db,user)
        assert error.value.status_code==409
        data=move(current);data.booking.expected_policy_revision=policy.revision
        assert reschedule_grouped(ident,data,db,user)['booking']['expected_policy_revision']==policy.revision


def pack_group(db,scenario):
    from app.apps.srm.service_checkout import save_policy
    from app.apps.srm.service_checkout_schemas import PolicyInput
    user,branch,catalog,basket=scenario
    context,grant,provider,register=enable_audited_pack(db,user,branch,catalog)
    data=basket(False);data.pos_session_id=register.id
    with audited_pack_writer(db,user,branch,context):
        policy=save_policy(PolicyInput(service_product_id=catalog[2][1],default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
        eligibility=save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=provider.data['employee_id']),db,user)
        for line in data.lines:
            if line.booking:
                line.booking.provider_resource_id=provider.id
                line.booking.policy_id=policy['id'];line.booking.expected_policy_revision=policy['revision']
                line.booking.eligibility_id=eligibility['id'];line.booking.expected_eligibility_revision=eligibility['revision']
        result=checkout(data,db,user)
    return context,grant,result,next(x['appointment_id'] for x in result['lines'] if x['appointment_id'])

@pytest.mark.parametrize('case',['revoked','role','foreign_source'])
def test_group_schedule_pack_scope_rechecked_for_each_action(db,scenario,case):
    from app.business_packs.models import PackActivation,PackContext,PackRecordOwnership
    user,branch,catalog,basket=scenario
    context,grant,result,ident=pack_group(db,scenario)
    with audited_pack_writer(db,user,branch,context):current=grouped_schedule(ident,db,user)
    if case=='revoked':grant.active=False;db.commit()
    elif case=='role':grant.role='cashier';db.commit()
    else:
        other=PackActivation(company_id=1,pack_key='restaurant',pack_version=1,state='active');db.add(other);db.flush()
        foreign=PackContext(company_id=1,branch_id=branch,activation_id=other.id,pack_key='restaurant',pack_version=1,state='active');db.add(foreign);db.flush()
        db.connection().execute(update(PackRecordOwnership.__table__).where(PackRecordOwnership.resource_table=='srm_industry_records',PackRecordOwnership.resource_key==str(ident)).values(context_id=foreign.id));db.commit()
    with native_writer(db,user,branch):
        with pytest.raises(HTTPException) as error:grouped_schedule(ident,db,user)
        assert error.value.status_code==403
        with pytest.raises(HTTPException) as error:reschedule_grouped(ident,move(current),db,user)
        assert error.value.status_code==403


def test_group_schedule_http_contract_and_non_authoritative_hints(client,db,scenario):
    from app.apps.srm.service_checkout_api import router
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):result,ident=group(db,scenario)
    appointment=db.get(IndustryRecord,ident)
    assert appointment.data['pos_checkout_id']==result['id'] and appointment.data['pos_occurrence_id']>0
    before=list(client.app.router.routes);client.app.include_router(router,prefix='/api/v1')
    try:
        path=f'/api/v1/srm/service-checkout/appointments/{ident}/schedule'
        response=client.get(path,headers=catalog[0]);assert response.status_code==200,response.text
        current=response.json();assert current['service_id']==catalog[2][1]
        response=client.post(path,headers=catalog[0],json=move(current).model_dump(mode='json'))
        assert response.status_code==200,response.text
        assert set(response.json())=={'appointment','schedule'} and response.json()['appointment']['id']==ident
        assert response.json()['schedule']['occurrence_revision']==current['occurrence_revision']+1
    finally:client.app.router.routes[:]=before


def test_native_scheduler_can_move_without_financial_permission(db,scenario):
    from tests.test_settings_hub import actor
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):result,ident=group(db,scenario)
    _,scheduler=actor(db,role='srm_sales_manager',permissions=['srm_manage'],admin=True);scheduler.organization_id=1
    with native_writer(db,scheduler,branch):
        current=grouped_schedule(ident,db,scheduler)
        assert reschedule_grouped(ident,move(current),db,scheduler)['appointment_revision']==current['appointment_revision']+1
        with pytest.raises(HTTPException) as error:servicecheckout_state(db,scheduler,db.info['branch_context'],result['id'])
        assert error.value.status_code==403

@pytest.mark.parametrize('field',['customer_id','invoice_id'])
def test_corrupted_grouped_appointment_identity_rejects_schedule(db,scenario,field):
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        result,ident=group(db,scenario);current=grouped_schedule(ident,db,user)
        db.connection().execute(update(IndustryRecord.__table__).where(IndustryRecord.id==ident).values(**{field:None if field=='customer_id' else result['invoice']['id']}))
        db.expire_all()
        with pytest.raises(HTTPException) as error:grouped_schedule(ident,db,user)
        assert error.value.status_code==409
        with pytest.raises(HTTPException) as error:reschedule_grouped(ident,move(current),db,user)
        assert error.value.status_code==409
        with pytest.raises(HTTPException) as error:servicecheckout_state(db,user,db.info['branch_context'],result['id'])
        assert error.value.status_code==409
