from datetime import date, timedelta
from decimal import Decimal
import pytest
from app.apps.crm.models import CRMCompany
from app.shared.plan_models import CustomerPlan, CustomerEntitlement, UsageLedger, PlanLifecycleEvent
from app.shared import plan_presentation
from tests.test_shared_catalog import headers, create, item, ROOT
from tests.test_catalog_offerings import config, purchased
from test_identity_utils import own_workflow_records

BASE='/api/v1/customer-plans'


def test_snapshot_names_balances_and_action_explanations(client,db,headers):
    plan,payload=purchased(client,db,headers)
    detail=client.get(f'{BASE}/{plan["id"]}?source=pms',headers=headers).json()
    assert detail['name']=='Enterprise offering'
    assert detail['display_status']=='active'
    assert detail['benefit_summary'][0]['allowance']=='20'
    assert Decimal(str(detail['benefit_summary'][0]['remaining']))==20
    assert detail['actions']['pause']['available']
    assert not detail['actions']['resume']['available'] and detail['actions']['resume']['reason']
    assert not detail['actions']['change']['available']
    offering=client.get(f'{ROOT}/items/membership/{plan["offering_id"]}?source=pms',headers=headers).json()
    offering['name']='New catalog name'
    response=client.put(f'{ROOT}/items/membership/{offering["id"]}?source=pms',headers=headers,json={k:v for k,v in offering.items() if k!='id'})
    assert response.status_code==200,response.text
    assert client.get(f'{BASE}/{plan["id"]}?source=pms',headers=headers).json()['name']=='Enterprise offering'
    readonly=plan_presentation.actions(db.get(CustomerPlan,plan['id']),False)
    assert all(not a['available'] and a['reason'] for a in readonly.values())


@pytest.mark.parametrize('status,activation,start_offset,end_offset,expected',[
    ('pending','first_use',0,30,'awaiting_first_use'),('pending','approval',0,30,'pending_approval'),
    ('active','purchase',1,31,'scheduled'),('active','purchase',-30,0,'expired'),
    ('paused','purchase',-1,30,'paused'),('suspended','purchase',-1,30,'suspended'),
    ('cancelled','purchase',-30,-1,'cancelled'),
])
def test_display_states_and_filters_match_without_mutating(client,db,headers,status,activation,start_offset,end_offset,expected):
    offering=create(client,headers,item('subscription',plan=config(activation=activation)))
    buyer=CRMCompany(name='State buyer',organization_id=1);db.add(buyer);own_workflow_records(db,buyer);db.flush()
    plan=CustomerPlan(organization_id=1,offering_id=offering['id'],customer_id=buyer.id,kind='subscription',number='STATE-PLAN',source_key='state-test-0001',status=status,start_date=date.today()+timedelta(days=start_offset),end_date=date.today()+timedelta(days=end_offset),configuration=offering['plan'],beneficiaries=[],price_snapshot={})
    db.add(plan);db.commit()
    args={'source':'pms','customer_id':buyer.id,'view':'all','status':expected,'kind':'subscription'}
    result=client.get(BASE,headers=headers,params=args)
    assert result.status_code==200,result.text
    assert result.json()['total']==1 and result.json()['items'][0]['display_status']==expected
    assert client.get(BASE,headers=headers,params={**args,'kind':'membership'}).json()['total']==0
    assert db.get(CustomerPlan,plan.id).status==status


def test_expiry_balance_filters_and_pagination(client,db,headers):
    plan,payload=purchased(client,db,headers)
    args={'source':'pms','customer_id':plan['customer_id'],'view':'all'}
    assert client.get(BASE,headers=headers,params={**args,'balance':'available'}).json()['total']==1
    assert client.get(BASE,headers=headers,params={**args,'balance':'exhausted'}).json()['total']==0
    b=db.query(CustomerEntitlement).filter_by(plan_id=plan['id']).one();b.remaining=0;db.commit()
    assert client.get(BASE,headers=headers,params={**args,'balance':'exhausted'}).json()['total']==1
    assert client.get(BASE,headers=headers,params={**args,'expiry_from':plan['end_date'],'expiry_to':plan['end_date']}).json()['total']==1
    assert client.get(BASE,headers=headers,params={**args,'expiry_from':'2099-01-01'}).json()['total']==0
    assert client.get(BASE,headers=headers,params={**args,'expiry_from':'2029-01-01','expiry_to':'2028-01-01'}).status_code==422
    assert client.get(BASE,headers=headers,params={**args,'page':2,'per_page':1}).json()['items']==[]
    db.get(CustomerPlan,plan['id']).organization_id=99;db.commit()
    assert client.get(BASE,headers=headers,params=args).json()['total']==0


def test_readable_usage_reversals_and_paged_actor_history(client,db,headers):
    plan,_=purchased(client,db,headers)
    b=db.query(CustomerEntitlement).filter_by(plan_id=plan['id']).one()
    used=client.post(f'{BASE}/entitlements/{b.id}/consume?source=pms',headers=headers,json={'quantity':3,'reference':'Recorded source order 123','request_key':'ux-history-use-001'})
    assert used.status_code==200,used.text
    reverse=client.post(f'{BASE}/usage/{used.json()["id"]}/reverse?source=pms',headers=headers,json={'request_key':'ux-history-reverse-001'})
    assert reverse.status_code==200,reverse.text
    renew=client.post(f'{BASE}/{plan["id"]}/lifecycle?source=pms',headers=headers,json={'action':'renew','revision':1,'until':'2029-12-31','request_key':'ux-history-renew-001'})
    assert renew.status_code==200,renew.text
    detail=client.get(f'{BASE}/{plan["id"]}?source=pms&per_page=1',headers=headers).json()
    assert detail['usage_total']==2 and detail['history_total']==2
    assert detail['usage'][0]['benefit_name']=='Swimming sessions'
    assert detail['usage'][0]['actor']=='testadmin@test.com'
    assert detail['usage'][0]['source_reference']=='Recorded source order 123'
    assert detail['usage'][0]['reverses_id']==used.json()['id']
    assert 'expiry' in detail['history'][0]['description'] and '2029-12-31' in detail['history'][0]['description']
    assert detail['history'][0]['actor']=='testadmin@test.com'
    second=client.get(f'{BASE}/{plan["id"]}?source=pms&per_page=1&usage_page=2&history_page=2',headers=headers).json()
    assert second['usage'][0]['reversed_by_id']==reverse.json()['id']
    assert second['history'][0]['description']=='Assigned plan'
    assert db.query(UsageLedger).count()==2 and db.query(PlanLifecycleEvent).count()==2
    db.refresh(b);assert b.remaining==Decimal('20')
