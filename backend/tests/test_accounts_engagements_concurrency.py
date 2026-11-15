"""Native committed Accounts engagement UUIDs serialize without duplicate births."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live,race
from tests.test_business_suite_pos_concurrency import seed
from tests.test_business_pack_http_integration import native_actor,grant
from tests.srm_test_utils import seed_invoice_parties
from app.branches.models import BranchOwnership
from app.apps.srm.models import SRMProduct,SRMEngagement
from app.business_packs.models import PackMasterAvailability
from app.business_packs.accounting_firm.models import AccountsEngagementCommand
from app.access.models import AccessPolicy

BASE='/api/v1/srm/accounts/engagements'


def configured(live):
    product=seed(live)
    with live.factory() as db:
        warehouse=db.get(SRMProduct,product).default_warehouse_id
        branch=db.query(BranchOwnership).filter_by(company_id=1,resource_table='srm_warehouses',resource_key=str(warehouse)).one().branch_id
        seed_invoice_parties(db)
        headers,actor=native_actor(db,branch)
        context,_=grant(db,actor,branch,'accounting_firm','engagement_manager')
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table='crm_companies',resource_key='101',active=True))
        db.commit()
        return {**headers,'X-Suite-Pack-Context':str(context.id)},actor.id


def body():return {'request_key':str(uuid4()),'client_id':101,'name':'Native concurrent client service'}


def test_exact_parallel_engagement_command_has_one_native_source(live):
    headers,_=configured(live);data=body()
    call=lambda:live.client.post(BASE,headers=headers,json=data)
    responses=race(call,call)
    assert [response.status_code for response in responses]==[201,201],[response.text for response in responses]
    assert responses[0].json()==responses[1].json()
    with live.factory() as db:
        assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==1


def test_same_uuid_competing_engagement_payloads_cannot_adopt_or_duplicate(live):
    headers,_=configured(live);data=body()
    responses=race(lambda:live.client.post(BASE,headers=headers,json=data),
        lambda:live.client.post(BASE,headers=headers,json={**data,'name':'Different intended service'}))
    assert sorted(response.status_code for response in responses)==[201,409],[response.text for response in responses]
    with live.factory() as db:
        assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==1


def test_native_create_revoked_during_real_company_wait_cannot_birth_engagement(live,monkeypatch):
    from app.business_packs.accounting_firm import engagements
    from app.core.company_writer import lock_company_writer
    headers,actor=configured(live);waiting=Event();original=engagements.lock_tenant
    def observed(db,user):
        waiting.set();return original(db,user)
    monkeypatch.setattr(engagements,'lock_tenant',observed)
    with live.factory() as blocker:
        lock_company_writer(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(lambda:live.client.post(BASE,headers=headers,json=body()))
            assert waiting.wait(timeout=20),'Engagement did not reach actual native company writer wait'
            policy=AccessPolicy.__table__
            row=blocker.connection().execute(select(policy.c.id,policy.c.grants).where(policy.c.company_id==1,policy.c.user_id==actor)).mappings().one()
            grants={**row['grants'],'srm':{**row['grants']['srm'],'actions':['view']}}
            blocker.connection().execute(policy.update().where(policy.c.id==row['id']).values(grants=grants,version=policy.c.version+1))
            blocker.commit()
            response=pending.result(timeout=40)
            assert response.status_code==403,response.text
    with live.factory() as db:
        assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==0
