from datetime import date
from app.apps.srm.models import SRMEngagement,SRMBillingPlan,SRMBillingMilestone,SRMInvoice,SRMAuditLog
from tests.test_contact_directory import directory_identity
from tests.srm_test_utils import seed_invoice_parties,auth_headers_for


def engagement(client,headers,name='QA lifecycle'):
    response=client.post('/api/v1/srm/engagements',headers=headers,json={'name':name,'customer_id':101,'budget_amount':4000})
    assert response.status_code==201,response.text
    return response.json()['id']


def test_222_223_amend_approve_period_and_bill_once(client,db,superuser_headers,directory_identity):
    seed_invoice_parties(db)
    eid=engagement(client,superuser_headers)
    response=client.post('/api/v1/srm/billing-plans',headers=superuser_headers,json={'engagement_id':eid,'name':'QA-222','billing_type':'milestone','total_amount':4000,'milestones':[{'name':'Initial','amount':4000,'due_date':'2026-11-15'}]})
    assert response.status_code==201,response.text
    plan=response.json();pid=plan['id'];mid=plan['milestones'][0]['id']
    patch={'amount':'4500','due_date':'2026-12-15','reason':'Approved scope amendment','expected_amount':'4000','expected_due_date':'2026-11-15'}
    assert client.patch(f'/api/v1/srm/billing-milestones/{mid}',headers=superuser_headers,json=patch).status_code==200
    assert client.patch(f'/api/v1/srm/billing-milestones/{mid}',headers=superuser_headers,json=patch).status_code==409
    db.expire_all();assert float(db.get(SRMBillingPlan,pid).total_amount)==4500
    client.post(f'/api/v1/srm/billing-plans/{pid}/activate',headers=superuser_headers)
    client.post(f'/api/v1/srm/billing-milestones/{mid}/approve',headers=superuser_headers)
    for start,end,count in [('2026-11-01','2026-11-30',0),('2026-12-01','2026-12-31',1)]:
        result=client.get(f'/api/v1/srm/billing-plans/{pid}/eligibility',headers=superuser_headers,params={'date_from':start,'date_to':end})
        assert result.status_code==200,result.text
        assert len(result.json()['milestones'])==count
    patch.update(expected_amount='4500',expected_due_date='2026-12-15',due_date=date.today().isoformat())
    response=client.patch(f'/api/v1/srm/billing-milestones/{mid}',headers=superuser_headers,json=patch)
    assert response.status_code==200 and response.json()['status']=='pending'
    assert client.post(f'/api/v1/srm/invoices/draft-from-billing-milestone/{mid}',headers=superuser_headers).status_code==400
    assert client.post(f'/api/v1/srm/billing-milestones/{mid}/approve',headers=superuser_headers).status_code==200
    invoice=client.post(f'/api/v1/srm/invoices/draft-from-billing-milestone/{mid}',headers=superuser_headers)
    assert invoice.status_code==201,invoice.text
    assert float(invoice.json()['total_amount'])==4500
    assert client.post(f'/api/v1/srm/invoices/draft-from-billing-milestone/{mid}',headers=superuser_headers).status_code==409
    assert client.patch(f'/api/v1/srm/billing-milestones/{mid}',headers=superuser_headers,json=patch).status_code==409
    db.expire_all();assert db.query(SRMInvoice).filter_by(engagement_id=eid).count()==1
    assert db.query(SRMAuditLog).filter_by(entity_type='billing_milestone',entity_id=mid,action='amended').count()==2


def test_224_cancellation_blocks_all_handoffs_and_mutations(client,db,superuser_headers):
    eid=engagement(client,superuser_headers,'QA-224')
    assert client.post(f'/api/v1/srm/engagements/{eid}/lifecycle/cancel',headers=superuser_headers,json={'reason':'Outside agreed scope'}).status_code==200
    assert client.post(f'/api/v1/srm/engagements/{eid}/create-pms-project',headers=superuser_headers).status_code==409
    assert client.post('/api/v1/srm/billing-plans',headers=superuser_headers,json={'engagement_id':eid,'name':'Forbidden','total_amount':100}).status_code==409
    assert client.post(f'/api/v1/srm/invoices/draft-from-engagement/{eid}',headers=superuser_headers).status_code==409
    assert client.patch(f'/api/v1/srm/engagements/{eid}',headers=superuser_headers,json={'name':'Bypass'}).status_code==409
    assert client.post(f'/api/v1/srm/engagements/{eid}/status/created',headers=superuser_headers).status_code==409
    db.expire_all();assert db.get(SRMEngagement,eid).status=='cancelled'
    assert db.query(SRMBillingPlan).filter_by(engagement_id=eid).count()==0
    assert db.query(SRMInvoice).filter_by(engagement_id=eid).count()==0


def test_225_close_reopen_preserves_history_and_requires_authorization(client,db,superuser_headers):
    eid=engagement(client,superuser_headers,'QA-225')
    plan=SRMBillingPlan(organization_id=1,engagement_id=eid,name='Completed history',status='completed',total_amount=100)
    db.add(plan);db.flush();mid=SRMBillingMilestone(billing_plan_id=plan.id,name='Historical',amount=100,status='invoiced',invoice_draft_id=999)
    db.add(mid);db.commit();pid=plan.id;mid_id=mid.id
    assert client.post(f'/api/v1/srm/engagements/{eid}/lifecycle/close',headers=superuser_headers,json={'reason':'Closed by mistake'}).status_code==200
    assert client.post(f'/api/v1/srm/engagements/{eid}/status/created',headers=superuser_headers).status_code==409
    assert client.post(f'/api/v1/srm/engagements/{eid}/lifecycle/reopen',headers=superuser_headers,json={'reason':'Additional delivery authorized'}).status_code==200
    assert client.patch(f'/api/v1/srm/engagements/{eid}',headers=superuser_headers,json={'name':'New permitted activity'}).status_code==200
    db.expire_all();assert db.get(SRMBillingMilestone,mid_id).invoice_draft_id==999
    assert db.get(SRMBillingPlan,pid).status=='completed'
    assert db.query(SRMBillingPlan).filter_by(engagement_id=eid).count()==1
    assert db.query(SRMAuditLog).filter_by(entity_type='engagement',entity_id=eid,action='reopen').one().actor_user_id is not None
    viewer=auth_headers_for(client,db,'qa-lifecycle-viewer@example.com','srm_viewer',permissions=['srm_view'])
    assert client.post(f'/api/v1/srm/engagements/{eid}/lifecycle/close',headers=viewer,json={'reason':'Unauthorized'}).status_code==403


def test_lifecycle_blocks_dependencies(client,db,superuser_headers):
    eid=engagement(client,superuser_headers)
    db.add(SRMBillingPlan(organization_id=1,engagement_id=eid,name='Open work',status='active',total_amount=100));db.commit()
    for action in ['cancel','close']:
        assert client.post(f'/api/v1/srm/engagements/{eid}/lifecycle/{action}',headers=superuser_headers,json={'reason':'Invalid closure'}).status_code==409
