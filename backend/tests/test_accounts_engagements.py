"""Real non-superuser native Accounts client engagement to independent review."""
from datetime import date
from uuid import uuid4
import pytest
from app.models.employee import Employee
from app.business_packs.accounting_firm.models import MODELS,AccountsEngagementCommand
from app.business_packs.models import PackMasterAvailability
from app.apps.srm.models import SRMEngagement
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_accounts_periods import body as period_body,send,prepared,revision,accounts

BASE='/api/v1/srm/accounts'


@pytest.fixture
def fresh_accounts(db,client,scenario):
    _,branch,_,_=scenario
    for model in MODELS:model.__table__.create(db.bind,checkfirst=True)
    headers,manager=native_actor(db,branch,actions=('view','create','edit','approve','assign'))
    assert not manager.is_superuser
    context,_=grant(db,manager,branch,'accounting_firm','engagement_manager')
    people={}
    for role in ('preparer','reviewer'):
        identity,user=native_actor(db,branch)
        grant(db,user,branch,'accounting_firm',role,context)
        with native_writer(db,manager,branch):
            person=Employee(employee_id='AC-BIRTH-'+uuid4().hex,first_name=role,last_name='QA',user_id=user.id,
                branch_id=branch,status='Active',date_of_joining=date(2025,1,1))
            db.add(person);db.commit()
        people[role]={'headers':{**identity,'X-Suite-Pack-Context':str(context.id)},'user':user,'employee':person.id}
    for table,ident in [('crm_companies',101),*[('employees',row['employee']) for row in people.values()]]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    return {'headers':{**headers,'X-Suite-Pack-Context':str(context.id)},'manager':manager,'context':context.id,'branch':branch,**people}


def engagement_input(**extra):
    return {'request_key':str(uuid4()),'client_id':101,'name':'Monthly accounts engagement',
        'currency':'INR','planned_start_date':'2026-01-01','planned_end_date':'2026-12-31',**extra}


def test_real_non_su_engagement_create_to_independent_period_review(client,db,fresh_accounts):
    case=fresh_accounts
    clients=client.get(BASE+'/clients',headers=case['headers'])
    assert clients.status_code==200,clients.text
    assert {'id':101,'name':clients.json()['items'][0]['name']} in clients.json()['items']
    body=engagement_input()
    response=client.post(BASE+'/engagements',headers=case['headers'],json=body)
    assert response.status_code==201,response.text
    created=response.json()
    assert client.post(BASE+'/engagements',headers=case['headers'],json=body).json()==created
    assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==1
    assert client.get(BASE+f"/engagements/{created['id']}",headers=case['headers']).json()==created
    listing=client.get(BASE+'/engagements',headers=case['headers'])
    assert listing.status_code==200,listing.text
    assert listing.json()['items']==[created]
    case={**case,'engagement':created['id']}
    row=send(client,case['headers'],'',period_body(case),status=201)
    row=prepared(client,case,row)
    approved=send(client,case['reviewer']['headers'],f"/{row['id']}/approve",revision(row)|{
        'expected_work_revision':row['work_revision'],'reason':'Independent actual review'})
    assert approved['state']=='approved'
    native=db.get(SRMEngagement,created['id'])
    assert native.customer_id==101 and native.assigned_user_id==case['manager'].id and native.project_manager_user_id==case['manager'].id
    from app.business_packs.accounting_firm.engagements import _births
    assert not _births


@pytest.mark.parametrize('extra',[{'customer_id':2},{'assigned_user_id':2},{'project_manager_user_id':2},
    {'engagement_number':'FORGED'},{'sales_order_id':2},{'contract_id':2},{'pms_project_id':2},
    {'organization_id':2},{'status':'active'},{'budget_amount':'100'},{'client_id':True},
    {'name':' '},{'planned_start_date':'2026-12-31','planned_end_date':'2026-01-01'}])
def test_strict_engagement_input_does_not_accept_native_identity_or_financial_overrides(extra):
    from app.business_packs.accounting_firm.schemas import EngagementCreate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):EngagementCreate.model_validate(engagement_input(**extra))


@pytest.mark.parametrize('role',['preparer','reviewer'])
def test_period_roles_with_native_create_cannot_create_engagements(client,db,fresh_accounts,role):
    case=fresh_accounts
    response=client.post(BASE+'/engagements',headers=case[role]['headers'],json=engagement_input())
    assert response.status_code==403,response.text
    assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==0


def test_missing_116_preserves_old_period_workflow_and_new_api_fails_actionably(client,db,accounts):
    if db.bind.dialect.name!='sqlite':pytest.skip('Older-schema compatibility simulation is SQLite only')
    AccountsEngagementCommand.__table__.drop(db.bind)
    row=send(client,accounts['headers'],'',period_body(accounts),status=201)
    assert row['state']=='draft'
    read=client.get(BASE+f"/periods/{row['id']}",headers=accounts['headers'])
    assert read.status_code==200,read.text
    new=client.get(BASE+'/engagements',headers=accounts['headers'])
    assert new.status_code==503 and '116' in new.text,new.text


@pytest.mark.parametrize('fault',['native_create','native_manage','client_unavailable','supplier_only','anonymous_control'])
def test_native_authority_and_actual_client_roles_are_not_inferred_from_pack_manager(client,db,fresh_accounts,fault):
    from sqlalchemy import select
    from app.access.models import AccessPolicy
    from app.apps.crm.models import CRMCompany
    from app.shared.master_data_models import BusinessRelationship
    case=fresh_accounts
    if fault in ('native_create','native_manage'):
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=case['manager'].id).one()
        grant={**policy.grants['srm']}
        if fault=='native_create':grant['actions']=['view']
        else:grant['permissions']=['srm_view']
        policy.grants={**policy.grants,'srm':grant};policy.version+=1
    elif fault=='client_unavailable':
        db.query(PackMasterAvailability).filter_by(context_id=case['context'],resource_table='crm_companies',resource_key='101').one().active=False
    elif fault=='supplier_only':
        db.connection().execute(CRMCompany.__table__.update().where(CRMCompany.id==101).values(account_type='Supplier'))
        db.connection().execute(BusinessRelationship.__table__.delete().where(BusinessRelationship.account_id==101,BusinessRelationship.role=='Customer'))
    else:
        # Existing native anonymous controls must never become unpaid clients.
        from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
        db.connection().execute(AnonymousCashAccount.__table__.insert().values(organization_id=1,branch_id=case['branch'],pack_context_id=case['context'],
            customer_id=101,account_label='Hostile control marker',jurisdiction_country='IN',revision=1,active=True,created_by=case['manager'].id))
    db.commit()
    response=client.post(BASE+'/engagements',headers=case['headers'],json=engagement_input())
    assert response.status_code==(403 if fault.startswith('native') else 404),response.text
    assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==0


@pytest.mark.parametrize('fault',['changed_retry','changed_native','late_audit','internal_commit'])
def test_engagement_replay_source_and_late_failure_are_atomic(client,db,fresh_accounts,monkeypatch,fault):
    from app.apps.srm.api import router as native
    from fastapi import HTTPException
    case=fresh_accounts;body=engagement_input()
    if fault in ('late_audit','internal_commit'):
        original=native._audit
        def interrupted(db,actor,entity,*args,**kwargs):
            if entity=='engagement':
                if fault=='internal_commit':db.commit()
                raise HTTPException(409,'Injected late canonical audit failure')
            return original(db,actor,entity,*args,**kwargs)
        monkeypatch.setattr(native,'_audit',interrupted)
        response=client.post(BASE+'/engagements',headers=case['headers'],json=body)
        assert response.status_code==409,response.text
        assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==0
    else:
        created=client.post(BASE+'/engagements',headers=case['headers'],json=body)
        assert created.status_code==201,created.text
        if fault=='changed_retry':
            response=client.post(BASE+'/engagements',headers=case['headers'],json={**body,'name':'Different work'})
        else:
            db.connection().execute(SRMEngagement.__table__.update().where(SRMEngagement.id==created.json()['id']).values(name='Tampered canonical source'))
            db.commit()
            response=client.get(BASE+f"/engagements/{created.json()['id']}",headers=case['headers'])
        assert response.status_code==409,response.text
        assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==1
    from app.business_packs.accounting_firm.engagements import _births
    assert not _births


def test_period_assignment_does_not_override_native_engagement_own_visibility(client,db,fresh_accounts):
    from app.access.models import AccessPolicy
    case=fresh_accounts
    created=client.post(BASE+'/engagements',headers=case['headers'],json=engagement_input())
    assert created.status_code==201,created.text
    row=send(client,case['headers'],'',period_body({**case,'engagement':created.json()['id']}),status=201)
    reviewer=case['reviewer']
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=reviewer['user'].id).one()
    policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'scope':'own'}};policy.version+=1;db.commit()
    listing=client.get(BASE+'/engagements',headers=reviewer['headers'])
    assert listing.status_code==200 and listing.json()['items']==[],listing.text
    for path in (f"/engagements/{created.json()['id']}",f"/periods/{row['id']}"):
        response=client.get(BASE+path,headers=reviewer['headers'])
        assert response.status_code==404,response.text



def test_native_existing_return_cannot_be_adopted_as_new_command(client,db,accounts,monkeypatch):
    from app.apps.srm.api import router as native
    monkeypatch.setattr(native,'create_engagement_operation',lambda *args,**kwargs:{'id':accounts['engagement']})
    response=client.post(BASE+'/engagements',headers=accounts['headers'],json=engagement_input())
    assert response.status_code==409,response.text
    assert db.query(SRMEngagement).count()==1 and db.query(AccountsEngagementCommand).count()==0


def test_creation_history_survives_native_close_but_new_period_does_not(client,db,fresh_accounts):
    case=fresh_accounts;body=engagement_input()
    created=client.post(BASE+'/engagements',headers=case['headers'],json=body)
    assert created.status_code==201,created.text
    current=created.json()
    db.connection().execute(SRMEngagement.__table__.update().where(SRMEngagement.id==current['id']).values(status='closed'))
    db.commit()
    detail=client.get(BASE+f"/engagements/{current['id']}",headers=case['headers'])
    assert detail.status_code==200 and detail.json()['status']=='closed',detail.text
    replay=client.post(BASE+'/engagements',headers=case['headers'],json=body)
    assert replay.status_code==201 and replay.json()==current,replay.text
    denied=client.post(BASE+'/periods',headers=case['headers'],json=period_body({**case,'engagement':current['id']}))
    assert denied.status_code==409,denied.text


def test_migration116_retains_native_engagement_and_existing_period_source(client,db,accounts):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    from sqlalchemy import inspect,select
    row=send(client,accounts['headers'],'',period_body(accounts),status=201)
    from app.business_packs.accounting_firm.models import AccountsPeriod,AccountsCommand
    saved={model.__tablename__:[dict(value) for value in db.connection().execute(select(model.__table__)).mappings()]
        for model in (SRMEngagement,AccountsPeriod,AccountsCommand)}
    assert db.query(AccountsEngagementCommand).count()==0
    db.commit()
    AccountsEngagementCommand.__table__.drop(db.bind)
    file=Path(__file__).resolve().parents[1]/'alembic_postgresql'/'versions'/'pg_20261115_116_accounts_engagements.py'
    spec=importlib.util.spec_from_file_location('accounts116migration',file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(get_bind=lambda:db.connection())
    module.upgrade();module.upgrade()
    inspector=inspect(db.connection())
    assert set(AccountsEngagementCommand.__table__.c.keys())=={column['name'] for column in inspector.get_columns(AccountsEngagementCommand.__tablename__)}
    assert {tuple(value['column_names']) for value in inspector.get_unique_constraints(AccountsEngagementCommand.__tablename__)}=={
        ('id','organization_id','branch_id','pack_context_id'),('organization_id','branch_id','pack_context_id','request_key'),('engagement_id',)}
    assert inspector.get_foreign_keys(AccountsEngagementCommand.__tablename__)
    module.downgrade()
    assert inspector.has_table(AccountsEngagementCommand.__tablename__)
    for model in (SRMEngagement,AccountsPeriod,AccountsCommand):
        assert [dict(value) for value in db.connection().execute(select(model.__table__)).mappings()]==saved[model.__tablename__]



def test_new_explicit_request_uuid_allows_new_engagement_with_same_payload(client,db,fresh_accounts):
    case=fresh_accounts;body=engagement_input()
    first=client.post(BASE+'/engagements',headers=case['headers'],json=body)
    second=client.post(BASE+'/engagements',headers=case['headers'],json={**body,'request_key':str(uuid4())})
    assert first.status_code==second.status_code==201,(first.text,second.text)
    assert first.json()['id']!=second.json()['id']
    assert db.query(SRMEngagement).count()==db.query(AccountsEngagementCommand).count()==2



def test_transient_command_copy_cannot_certify_an_actual_native_source(client,db,fresh_accounts):
    from app.business_packs.accounting_firm.engagements import _proof
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from fastapi import HTTPException
    case=fresh_accounts
    created=client.post(BASE+'/engagements',headers=case['headers'],json=engagement_input())
    assert created.status_code==201,created.text
    actual=db.query(AccountsEngagementCommand).one()
    fake=AccountsEngagementCommand(**{column.name:getattr(actual,column.name) for column in AccountsEngagementCommand.__table__.c})
    with native_writer(db,case['manager'],case['branch']):
        scope=resolve_context(db,case['manager'],db.info['branch_context'],case['context'])
        cleanup=install(db,scope,policy=native_srm_policy('accounting_firm').policy)
        try:
            with pytest.raises(HTTPException) as error:_proof(db,case['manager'],scope,fake)
            assert error.value.status_code==403
        finally:cleanup()
    assert db.query(AccountsEngagementCommand).count()==1
