"""Actual PostgreSQL Company births preserve native duplicates and fresh authority."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import MappingProxyType
from uuid import uuid4
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live,race
from tests.test_settings_hub import actor
from tests.test_business_pack_http_integration import grant
from app.models.company import Branch
from app.branches.models import BranchGrant
from app.access.models import AccessPolicy
from app.apps.crm.models import CRMCompany

BASE='/api/v1/master-data/companies?source=crm'


def configured(live,monkeypatch):
    from app.business_packs import common_core,company_master_core
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        **company_master_core.candidate_operations(common_core.CoreOperation)}))
    with live.factory() as db:
        branch=Branch(company_id=1,name='Company source race '+uuid4().hex,is_active=True);db.add(branch);db.flush()
        headers,user=actor(db,role='cmp-race-'+uuid4().hex,permissions=['crm_admin'],admin=True)
        user.organization_id=1
        db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=user.id,can_write=True))
        db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={'crm':{'enabled':True,
            'permissions':['crm_admin'],'actions':['view','create','edit'],'scope':'organization'}}));db.commit()
        grant(db,user,branch.id,'accounting_firm','engagement_manager')
        return {**headers,'X-Suite-Branch':str(branch.id)},user.id


def test_concurrent_same_native_company_keeps_genuine_duplicate_reference(live,monkeypatch):
    headers,_=configured(live,monkeypatch)
    data={'name':'Concurrent canonical Company '+uuid4().hex,'entityKind':'Company','roles':['Customer']}
    responses=race(lambda:live.client.post(BASE,headers=headers,json=data),lambda:live.client.post(BASE,headers=headers,json=data))
    assert sorted(r.status_code for r in responses)==[201,409],[r.text for r in responses]
    assert next(r for r in responses if r.status_code==409).json()['detail']['matches']
    with live.factory() as db:assert db.query(CRMCompany).filter_by(name=data['name']).count()==1


def test_native_company_create_revoked_during_actual_company_writer_wait(live,monkeypatch):
    from app.core import company_writer
    headers,user_id=configured(live,monkeypatch);waiting=Event();original=company_writer.lock_company_writer
    def observed(db,company):
        waiting.set();return original(db,company)
    monkeypatch.setattr(company_writer,'lock_company_writer',observed)
    data={'name':'Revoked native Company '+uuid4().hex,'entityKind':'Company','roles':['Customer']}
    with live.factory() as blocker:
        original(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(lambda:live.client.post(BASE,headers=headers,json=data))
            assert waiting.wait(timeout=20),'Native Company did not reach company writer'
            policy=AccessPolicy.__table__
            row=blocker.connection().execute(select(policy.c.id,policy.c.grants).where(policy.c.company_id==1,policy.c.user_id==user_id)).mappings().one()
            grants={**row['grants'],'crm':{**row['grants']['crm'],'actions':['view']}}
            blocker.connection().execute(policy.update().where(policy.c.id==row['id']).values(grants=grants,version=policy.c.version+1));blocker.commit()
            response=pending.result(timeout=40);assert response.status_code==403,response.text
    with live.factory() as db:assert db.query(CRMCompany).filter_by(name=data['name']).count()==0
