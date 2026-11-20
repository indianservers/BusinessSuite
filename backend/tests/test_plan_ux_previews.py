from datetime import date
from decimal import Decimal
import pytest
from app.shared.plan_models import CustomerPlan, CustomerEntitlement, PlanLifecycleEvent, UsageLedger
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMInvoice, SRMReceipt
from tests.test_shared_catalog import headers, create, item, ROOT
from tests.test_catalog_offerings import config, purchased
from test_identity_utils import own_workflow_records


@pytest.mark.parametrize('duration,start,end,last', [
    ({'unit':'month','count':1},'2028-01-31','2028-02-29','2028-02-28'),
    ({'unit':'year','count':1},'2028-02-29','2029-02-28','2029-02-27'),
    ({'unit':'lifetime'},'2028-01-31',None,None),
    ({'unit':'custom','start':'2028-01-01','end':'2028-06-30'},'2028-02-01','2028-06-30','2028-06-29'),
])
def test_validity_preview_uses_the_assignment_calendar_without_writes(client,db,headers,duration,start,end,last):
    response=client.post('/api/v1/customer-plans/validity-preview?source=pms',headers=headers,json={'duration':duration,'activation':'selected_date','start_date':start,'billing_timezone':'Asia/Kolkata'})
    assert response.status_code==200,response.text
    data=response.json()
    assert (data['start_date'],data['end_date'],data['last_access_date'])==(start,end,last)
    assert data['billing_timezone']=='Asia/Kolkata'
    assert not data['automatic_billing_enabled'] and not data['reminder_delivery_enabled']
    assert db.query(CustomerPlan).count()==db.query(PlanLifecycleEvent).count()==0


def test_preview_requires_selected_date_and_handles_date_overflow(client,db,headers):
    for body in [ {'duration':{'unit':'month','count':1},'activation':'selected_date'}, {'duration':{'unit':'day','count':2},'start_date':'9999-12-31'} ]:
        response=client.post('/api/v1/customer-plans/validity-preview?source=pms',headers=headers,json=body)
        assert response.status_code==422,response.text
    first=client.post('/api/v1/customer-plans/validity-preview?source=pms',headers=headers,json={'duration':{'unit':'month','count':1},'activation':'first_use'})
    assert first.status_code==200 and first.json()['estimated'] is True


def test_assignment_preview_matches_issue_and_versioned_retries(client,db,headers):
    offering=create(client,headers,item('membership',plan=config(activation='selected_date',duration={'unit':'month','count':1})))
    buyer=CRMCompany(name='Preview buyer',organization_id=1)
    beneficiary=CRMCompany(name='Named beneficiary',email='beneficiary@example.com',organization_id=1)
    db.add_all([buyer,beneficiary]);own_workflow_records(db,buyer,beneficiary);db.commit()
    payload={'offering_id':offering['id'],'kind':'membership','customer_id':buyer.id,'start_date':'2028-01-31','beneficiaries':[beneficiary.id]}
    preview=client.post('/api/v1/customer-plans/assignment-preview?source=pms',headers=headers,json=payload)
    assert preview.status_code==200,preview.text
    data=preview.json()
    assert data['customer_name']=='Preview buyer' and data['end_date']=='2028-02-29'
    assert not data['payment_collected']
    assert db.query(CustomerPlan).count()==0
    command={**payload,'expected_offering_version':data['offering_version'],'request_key':'preview-issue-0001'}
    result=client.post('/api/v1/customer-plans?source=pms',headers=headers,json=command)
    assert result.status_code==201,result.text
    assert result.json()['start_date']==data['start_date'] and result.json()['end_date']==data['end_date']
    assert result.json()['beneficiaries']==[beneficiary.id]
    edited={key:value for key,value in offering.items() if key!='id'}
    edited['name']='Updated terms'
    changed=client.put(f"{ROOT}/items/membership/{offering['id']}?source=pms",headers=headers,json=edited)
    assert changed.status_code==200,changed.text
    retry=client.post('/api/v1/customer-plans?source=pms',headers=headers,json=command)
    assert retry.status_code==201 and retry.json()['id']==result.json()['id']
    stale=client.post('/api/v1/customer-plans?source=pms',headers=headers,json={**command,'request_key':'preview-issue-0002'})
    assert stale.status_code==409 and db.query(CustomerPlan).count()==1


def test_renew_and_cancel_previews_have_no_side_effects_and_describe_actual_changes(client,db,headers):
    plan,payload=purchased(client,db,headers)
    entitlement=db.query(CustomerEntitlement).filter_by(plan_id=plan['id']).one()
    consume=client.post(f'/api/v1/customer-plans/entitlements/{entitlement.id}/consume?source=pms',headers=headers,json={'quantity':3,'request_key':'preview-usage-001','reference':'preview-test'})
    assert consume.status_code==200,consume.text
    before=(db.query(PlanLifecycleEvent).count(),db.query(SRMInvoice).count(),db.query(SRMReceipt).count(),db.query(UsageLedger).count())
    command={'action':'renew','revision':1,'until':'2029-12-31'}
    response=client.post(f"/api/v1/customer-plans/{plan['id']}/lifecycle-preview?source=pms",headers=headers,json=command)
    assert response.status_code==200,response.text
    preview=response.json()
    assert preview['after']['end_date']=='2029-12-31'
    assert Decimal(str(preview['benefits'][0]['remaining']))==17
    assert preview['charge_amount']=='0' and not preview['invoice_created'] and not preview['payment_collected']
    assert db.get(CustomerPlan,plan['id']).end_date==date.fromisoformat(plan['end_date'])
    assert before==(db.query(PlanLifecycleEvent).count(),db.query(SRMInvoice).count(),db.query(SRMReceipt).count(),db.query(UsageLedger).count())
    renewed=client.post(f"/api/v1/customer-plans/{plan['id']}/lifecycle?source=pms",headers=headers,json={**command,'request_key':'preview-renew-001'})
    assert renewed.status_code==200 and renewed.json()['end_date']==preview['after']['end_date']
    cancellation={'action':'cancel','revision':2}
    review=client.post(f"/api/v1/customer-plans/{plan['id']}/lifecycle-preview?source=pms",headers=headers,json=cancellation)
    assert review.status_code==200,review.text
    assert review.json()['benefit_treatment']=='retained_unusable' and not review.json()['refund_created']
    assert review.json()['access_after']=='blocked' and db.get(CustomerPlan,plan['id']).status=='active'
    cancelled=client.post(f"/api/v1/customer-plans/{plan['id']}/lifecycle?source=pms",headers=headers,json={**cancellation,'request_key':'preview-cancel-001'})
    assert cancelled.status_code==200,cancelled.text
    db.refresh(entitlement)
    assert entitlement.remaining==17
    assert db.query(SRMInvoice).count()==before[1] and db.query(SRMReceipt).count()==before[2]


def test_preview_rejects_stale_revisions_and_foreign_plans(client,db,headers):
    plan,_=purchased(client,db,headers)
    endpoint=f"/api/v1/customer-plans/{plan['id']}/lifecycle-preview?source=pms"
    assert client.post(endpoint,headers=headers,json={'action':'cancel','revision':99}).status_code==409
    assert db.query(PlanLifecycleEvent).count()==1
    row=db.get(CustomerPlan,plan['id']);row.organization_id=99;db.commit()
    assert client.post(endpoint,headers=headers,json={'action':'cancel','revision':1}).status_code==404
