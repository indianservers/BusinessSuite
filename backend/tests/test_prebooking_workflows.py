from datetime import timedelta, time
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.apps.srm.prebooking_workflows import (WaitlistInput, SeriesInput, ExpectedRevision, save_waitlist, preview_series, commit_series, cancel_waitlist, workflow_request_status, appointment_summary)
from app.apps.srm.industry_api import appointment_operation
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMSalesOrder
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_prebooking_shared_selection import selection
from tests.test_prebooking_resource_requirements import configure
from tests.test_srm_native_transaction_operations import native_writer


def series(basket):
    base=selection(basket)
    return SeriesInput(request_id=uuid4(),title='Weekly series',base=base,starts_at=[base.starts_at,base.starts_at+timedelta(days=7),base.starts_at+timedelta(days=14)])


def waiting(basket):
    base=selection(basket)
    return WaitlistInput(request_id=uuid4(),title='Waiting preference',customer_id=base.customer_id,service_id=base.service_id,
        from_date=base.starts_at.date(),until_date=base.starts_at.date()+timedelta(days=7),timezone='UTC',employee_id=base.booking.employee_id)


def test_waitlist_is_idempotent_non_reserving_and_optimistically_cancelled(db,scenario):
    user,branch,_,basket=scenario
    data=waiting(basket)
    with native_writer(db,user,branch):
        saved=save_waitlist(data,db,user)
        assert saved['status']=='waiting'
        assert db.query(IndustryRecord).filter_by(kind='appointment').count()==0
        assert all(db.query(model).count()==0 for model in [SRMInvoice,SRMReceipt,SRMSalesOrder])
        assert save_waitlist(data,db,user)['id']==saved['id']
        assert workflow_request_status(data.request_id,db,user)['result']['id']==saved['id']
        altered=data.model_copy(update={'notes':'Changed preference'})
        with pytest.raises(HTTPException) as changed:save_waitlist(altered,db,user)
        assert changed.value.status_code==409
        cancelled=cancel_waitlist(saved['id'],ExpectedRevision(expected_revision=saved['revision']),db,user)
        assert cancelled['status']=='cancelled'
        with pytest.raises(HTTPException):cancel_waitlist(saved['id'],ExpectedRevision(expected_revision=saved['revision']),db,user)


def test_waitlist_rejects_unqualified_employee_missing_fixed_resource_and_foreign_resource(db,scenario):
    user,branch,_,basket=scenario
    data=waiting(basket)
    draft=selection(basket)
    with native_writer(db,user,branch):
        configure(db,user,draft.service_id,draft.booking,['room'])
        with pytest.raises(HTTPException):save_waitlist(data.model_copy(update={'employee_id':999999}),db,user)
        with pytest.raises(HTTPException):save_waitlist(data.model_copy(update={'flexible_resources':False}),db,user)
        with pytest.raises(HTTPException):save_waitlist(data.model_copy(update={'resource_ids':[999999]}),db,user)
        assert db.query(IndustryRecord).filter_by(kind='prebooking_waitlist').count()==0


def test_series_preview_excludes_conflict_commit_is_atomic_idempotent_and_no_money(db,scenario):
    user,branch,_,basket=scenario
    data=series(basket)
    with native_writer(db,user,branch):
        occupied=appointment_operation(data.base,db,user)
        preview=preview_series(data,db,user)
        assert [r['available'] for r in preview['occurrences']]==[False,True,True]
        data.included=[1,2]
        result=commit_series(data,db,user)
        assert len(result['appointments'])==2
        assert commit_series(data,db,user)==result
        assert db.query(IndustryRecord).filter_by(kind='appointment').count()==3
        assert workflow_request_status(data.request_id,db,user)['result']['id']==result['id']
        assert all(db.query(model).count()==0 for model in [SRMInvoice,SRMReceipt,SRMSalesOrder])
        summary=appointment_summary(occupied['id'],db,user)
        assert summary['row']['id']==occupied['id']
        assert summary['timezone']=='UTC'
        with pytest.raises(HTTPException):commit_series(data.model_copy(update={'included':[2]}),db,user)


def test_series_rolls_back_all_occurrences_if_later_write_fails(db,scenario,monkeypatch):
    import app.apps.srm.prebooking_workflows as workflows
    user,branch,_,basket=scenario
    data=series(basket)
    actual=workflows.appointment_operation
    called=[]
    def racing(item,*args,**kwargs):
        called.append(item.request_id)
        if len(called)==2:raise HTTPException(409,'Concurrent change')
        return actual(item,*args,**kwargs)
    monkeypatch.setattr(workflows,'appointment_operation',racing)
    with native_writer(db,user,branch):
        with pytest.raises(HTTPException):commit_series(data,db,user)
        assert db.query(IndustryRecord).filter(IndustryRecord.kind.in_(['appointment','prebooking_series'])).count()==0


def test_workflow_limits_and_context_recovery(db,scenario):
    user,branch,_,basket=scenario
    data=series(basket)
    with pytest.raises(ValidationError):SeriesInput(**{**data.model_dump(),'included':[99]})
    with pytest.raises(ValidationError):SeriesInput(**{**data.model_dump(),'starts_at':[data.starts_at[0]]*2})
    with pytest.raises(ValidationError):WaitlistInput(**{**waiting(basket).model_dump(),'window_from':time(17),'window_until':time(9)})
    with native_writer(db,user,branch):
        saved=save_waitlist(waiting(basket),db,user)
        row=db.get(IndustryRecord,saved['id'])
        row.created_by=user.id+999
        db.flush()
        assert workflow_request_status(row.request_id,db,user)=={'state':'not_found'}
        with pytest.raises(HTTPException):cancel_waitlist(row.id,ExpectedRevision(expected_revision=1),db,user)
        db.rollback()


def test_workflow_http_mount_and_authorized_eligibility(client,db,scenario):
    from app.apps.srm.prebooking_workflows import eligibility_explanation
    from app.apps.srm.service_checkout_models import ServiceSpecialistEligibility
    from app.models.employee import Employee
    user,branch,source,basket=scenario
    data=waiting(basket)
    response=client.post('/api/v1/srm/industry/prebooking-workflows/waitlist',headers=source[0],json=data.model_dump(mode='json'))
    assert response.status_code==201,response.text
    request=client.get('/api/v1/srm/industry/prebooking-workflows/requests/'+str(data.request_id),headers=source[0])
    assert request.status_code==200 and request.json()['state']=='confirmed'
    recurring=series(basket)
    preview=client.post('/api/v1/srm/industry/prebooking-workflows/series/preview',headers=source[0],json=recurring.model_dump(mode='json'))
    assert preview.status_code==200,preview.text
    committed=client.post('/api/v1/srm/industry/prebooking-workflows/series',headers=source[0],json=recurring.model_dump(mode='json'))
    assert committed.status_code==201,committed.text
    assert len(committed.json()['appointments'])==3
    replay=client.post('/api/v1/srm/industry/prebooking-workflows/series',headers=source[0],json=recurring.model_dump(mode='json'))
    assert replay.status_code==201 and replay.json()['id']==committed.json()['id']
    with native_writer(db,user,branch):
        eligible=eligibility_explanation(data.service_id,data.employee_id,db,user)
        assert eligible['eligible'] is True
        db.query(ServiceSpecialistEligibility).update({'active':False});db.flush()
        excluded=eligibility_explanation(data.service_id,data.employee_id,db,user)
        assert 'inactive' in ' '.join(excluded['reasons'])
        employee=db.get(Employee,data.employee_id);employee.status='Terminated';db.flush()
        assert 'status' in ' '.join(eligibility_explanation(data.service_id,data.employee_id,db,user)['reasons'])
        with pytest.raises(HTTPException):eligibility_explanation(data.service_id,999999,db,user)


def test_pack_workflows_anchor_every_source_and_reject_revoked_role(db,scenario):
    from sqlalchemy import select
    from tests.test_service_checkout import enable_audited_pack,audited_pack_writer
    from app.business_packs.models import PackRecordOwnership
    from app.apps.srm.service_checkout import save_policy,save_eligibility
    from app.apps.srm.service_checkout_schemas import PolicyInput,EligibilityInput
    user,branch,source,basket=scenario
    context,grant,provider,_=enable_audited_pack(db,user,branch,source)
    data=series(basket)
    wait=waiting(basket)
    with audited_pack_writer(db,user,branch,context):
        policy=save_policy(PolicyInput(service_product_id=data.base.service_id,default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
        eligibility=save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=provider.data['employee_id']),db,user)
        b=data.base.booking
        b.provider_resource_id=provider.id;b.policy_id=policy['id'];b.expected_policy_revision=policy['revision'];b.eligibility_id=eligibility['id'];b.expected_eligibility_revision=eligibility['revision']
        data.base.resource_ids=[provider.id]
        waiting_row=save_waitlist(wait,db,user)
        created=commit_series(data,db,user)
        assert workflow_request_status(data.request_id,db,user)['state']=='confirmed'
        keys={str(waiting_row['id']),str(created['id']),*[str(row['id']) for row in created['appointments']]}
        anchors=db.connection().execute(select(PackRecordOwnership.resource_key).where(PackRecordOwnership.context_id==context.id,PackRecordOwnership.resource_table=='srm_industry_records')).scalars().all()
        assert keys<=set(anchors)
    grant.active=False;db.commit()
    with pytest.raises(HTTPException),audited_pack_writer(db,user,branch,context):save_waitlist(wait,db,user)
