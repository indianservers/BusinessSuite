"""Native HTTP persisted client-service review; no client-book impersonation."""
from uuid import uuid4
from datetime import date
import pytest
from sqlalchemy import select,func
from app.models.employee import Employee
from app.apps.srm.models import SRMEngagement
from app.business_packs.accounting_firm.models import MODELS,AccountsPeriod,AccountsCommand
from app.business_packs.models import PackMasterAvailability,PackContext,PackUserGrant
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_srm_native_transaction_operations import native_writer

BASE='/api/v1/srm/accounts/periods'


@pytest.fixture
def accounts(db,client,scenario):
    _,branch,_,_=scenario
    for model in MODELS:
        model.__table__.create(db.bind,checkfirst=True)
    manager_headers,manager=native_actor(db,branch,actions=('view','create','edit','approve','assign'))
    context,_=grant(db,manager,branch,'accounting_firm','engagement_manager')
    users={}
    for role in ('preparer','reviewer'):
        headers,user=native_actor(db,branch)
        grant(db,user,branch,'accounting_firm',role,context)
        with native_writer(db,manager,branch):
            employee=Employee(employee_id='AC-'+uuid4().hex,first_name=role,last_name='QA',user_id=user.id,branch_id=branch,status='Active',date_of_joining=date(2025,1,1))
            db.add(employee);db.commit()
        users[role]={'headers':{**headers,'X-Suite-Pack-Context':str(context.id)},'user':user,'employee':employee.id}
    with native_writer(db,manager,branch):
        manager_employee=Employee(employee_id='AC-'+uuid4().hex,first_name='Manager',last_name='QA',user_id=manager.id,branch_id=branch,status='Active',date_of_joining=date(2025,1,1))
        db.add(manager_employee);db.commit()
    for table,ident in [('crm_companies',101),*[('employees',row['employee']) for row in users.values()]]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table='employees',resource_key=str(manager_employee.id),active=True));db.commit()
    with native_writer(db,manager,branch):
        scope=resolve_context(db,manager,db.info['branch_context'],context.id)
        cleanup=install(db,scope,policy=native_srm_policy('accounting_firm').policy)
        try:
            engagement=SRMEngagement(organization_id=1,engagement_number='AC-'+uuid4().hex,customer_id=101,name='Client accounts service',status='active',assigned_user_id=manager.id,created_by=manager.id)
            db.add(engagement);db.commit()
            engagement_id=engagement.id
        finally:
            cleanup()
    return dict(headers={**manager_headers,'X-Suite-Pack-Context':str(context.id)},manager=manager,
        context=context.id,branch=branch,engagement=engagement_id,manager_employee=manager_employee.id,**users)


def body(case):
    return dict(request_key=str(uuid4()),engagement_id=case['engagement'],client_id=101,
        starts_on='2026-01-01',ends_on='2026-01-31',due_on='2026-02-10',title='January client bookkeeping',
        preparer_employee_id=case['preparer']['employee'],reviewer_employee_id=case['reviewer']['employee'])


def send(client,headers,path,data,method='post',status=200):
    response=getattr(client,method)(BASE+path,headers=headers,json=data)
    assert response.status_code==status,response.text
    return response.json()


def create(client,case):
    payload=body(case)
    row=send(client,case['headers'],'',payload,status=201)
    assert send(client,case['headers'],'',payload,status=201)==row
    return row


def revision(row):
    return {'request_key':str(uuid4()),'expected_revision':row['revision']}


def prepared(client,case,row):
    row=send(client,case['preparer']['headers'],f"/{row['id']}/work",revision(row)|{'summary':'Reconciled provided records'},method='put')
    return send(client,case['preparer']['headers'],f"/{row['id']}/submit",revision(row))


def test_native_persisted_independent_review_and_changed_work_invalidates_approval(client,db,accounts):
    row=create(client,accounts)
    row=prepared(client,accounts,row)
    payload=revision(row)|{'expected_work_revision':row['work_revision'],'reason':'Reviewed supplied records'}
    approved=send(client,accounts['reviewer']['headers'],f"/{row['id']}/approve",payload)
    assert approved['state']=='approved' and approved['approved_work_revision']==1
    assert approved['review_reason']=='Reviewed supplied records'
    assert send(client,accounts['reviewer']['headers'],f"/{row['id']}/approve",payload)==approved
    changed=send(client,accounts['preparer']['headers'],f"/{row['id']}/work",revision(approved)|{'summary':'Corrected reconciliation'},method='put')
    assert changed['state']=='draft' and changed['work_revision']==2 and changed['approved_work_revision'] is None
    assert changed['submitted_work_revision'] is None
    assert changed['review_reason']==''
    persisted=db.connection().execute(select(AccountsPeriod.__table__).where(AccountsPeriod.id==row['id'])).mappings().one()
    assert persisted['state']=='draft' and persisted['work_revision']==2
    assert db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))==5


def test_assigned_review_identity_and_stale_revision_reject_without_partial_history(client,db,accounts):
    row=prepared(client,accounts,create(client,accounts))
    before=db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))
    data=revision(row)|{'expected_work_revision':row['work_revision']}
    send(client,accounts['preparer']['headers'],f"/{row['id']}/approve",data,status=403)
    send(client,accounts['headers'],f"/{row['id']}/approve",data,status=403)
    send(client,accounts['reviewer']['headers'],f"/{row['id']}/approve",data|{'expected_revision':999},status=409)
    send(client,accounts['reviewer']['headers'],f"/{row['id']}/approve",data|{'expected_work_revision':999},status=409)
    send(client,accounts['reviewer']['headers'],f"/{row['id']}/return",data,status=422)
    assert db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))==before
    returned=send(client,accounts['reviewer']['headers'],f"/{row['id']}/return",data|{'reason':'Missing reconciliation explanation'})
    assert returned['state']=='returned'
    response=client.get(BASE+f"/{row['id']}",headers=accounts['preparer']['headers'])
    assert response.status_code==200,response.text
    assert response.json()['review_reason']=='Missing reconciliation explanation'


@pytest.mark.parametrize('fault',['same_employee','foreign_client','foreign_engagement','unexpected_books','same_key_changed'])
def test_invalid_period_sources_and_request_keys_do_not_create_partial_records(client,db,accounts,fault):
    payload=body(accounts)
    status=422
    if fault=='same_employee':payload['reviewer_employee_id']=payload['preparer_employee_id']
    elif fault=='foreign_client':payload['client_id']=999999;status=404
    elif fault=='foreign_engagement':payload['engagement_id']=999999;status=404
    elif fault=='unexpected_books':payload['client_company_id']=1
    else:
        send(client,accounts['headers'],'',payload,status=201)
        payload['title']='Changed request'
        status=409
    before=tuple(db.connection().scalar(select(func.count()).select_from(model.__table__)) for model in MODELS)
    send(client,accounts['headers'],'',payload,status=status)
    assert tuple(db.connection().scalar(select(func.count()).select_from(model.__table__)) for model in MODELS)==before


def test_other_pack_and_revoked_source_are_denied(client,db,accounts):
    row=create(client,accounts)
    before=db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))
    for pack in ('hospital','salon','retail','construction','pharma','restaurant'):
        other,_=grant(db,accounts['manager'],accounts['branch'],pack,'business_owner')
        foreign={**accounts['headers'],'X-Suite-Pack-Context':str(other.id)}
        assert client.get(BASE+f"/{row['id']}",headers=foreign).status_code==403
        send(client,foreign,f"/{row['id']}/work",revision(row)|{'summary':'Foreign pack work'},method='put',status=403)
    assert db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))==before
    available=db.query(PackMasterAvailability).filter_by(context_id=accounts['context'],resource_table='crm_companies',resource_key='101').one()
    available.active=False;db.commit()
    response=client.get(BASE+f"/{row['id']}",headers=accounts['headers'])
    assert response.status_code in (403,404),response.text


def test_reassignment_invalidates_review_and_old_preparer_cannot_write(client,db,accounts):
    row=prepared(client,accounts,create(client,accounts))
    assigned=send(client,accounts['headers'],f"/{row['id']}/assignment",revision(row)|{
        'preparer_employee_id':accounts['manager_employee'],'reviewer_employee_id':accounts['reviewer']['employee']},method='put')
    assert assigned['state']=='draft' and assigned['submitted_work_revision'] is None
    send(client,accounts['preparer']['headers'],f"/{row['id']}/work",revision(assigned)|{'summary':'Old preparer'},method='put',status=403)


def test_revoked_assigned_staff_blocks_work_without_partial_history(client,db,accounts):
    row=create(client,accounts)
    granted=db.query(PackUserGrant).filter_by(context_id=accounts['context'],user_id=accounts['reviewer']['user'].id).one()
    granted.active=False;db.commit()
    before=db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))
    send(client,accounts['preparer']['headers'],f"/{row['id']}/work",revision(row)|{'summary':'Must not continue with revoked reviewer'},method='put',status=409)
    assert db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))==before


def test_native_assign_ceiling_controls_capability_and_endpoint(client,db,accounts):
    from copy import deepcopy
    from app.access.models import AccessPolicy
    row=create(client,accounts)
    policy=db.query(AccessPolicy).filter_by(user_id=accounts['manager'].id,company_id=1).one()
    values=deepcopy(policy.grants)
    values['srm']['actions'].remove('assign')
    policy.grants=values;db.commit()
    response=client.get('/api/v1/srm/accounts/capabilities',headers=accounts['headers'])
    assert response.status_code==200,response.text
    assert response.json()['engagements_manage'] is True and response.json()['assignments_manage'] is False
    before=db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))
    send(client,accounts['headers'],f"/{row['id']}/assignment",revision(row)|{
        'preparer_employee_id':accounts['manager_employee'],'reviewer_employee_id':accounts['reviewer']['employee']},method='put',status=403)
    assert db.connection().scalar(select(func.count()).select_from(AccountsCommand.__table__))==before


def test_manager_cannot_assign_staff_without_matching_accounts_role(client,db,accounts):
    row=create(client,accounts)
    payload=revision(row)|{'preparer_employee_id':accounts['reviewer']['employee'],'reviewer_employee_id':accounts['preparer']['employee']}
    send(client,accounts['headers'],f"/{row['id']}/assignment",payload,method='put',status=409)


def test_native_scoped_selection_and_capabilities_do_not_offer_other_pack_staff(client,db,accounts):
    response=client.get('/api/v1/srm/accounts/options',headers=accounts['headers'])
    assert response.status_code==200,response.text
    data=response.json()
    assert data['engagements']==[{'id':accounts['engagement'],'name':'Client accounts service','client_id':101,'client_name':data['engagements'][0]['client_name']}]
    assert {row['id'] for row in data['preparers']}=={accounts['preparer']['employee'],accounts['manager_employee']}
    assert {row['id'] for row in data['reviewers']}=={accounts['reviewer']['employee'],accounts['manager_employee']}
    response=client.get('/api/v1/srm/accounts/options',headers=accounts['preparer']['headers'])
    assert response.status_code==403,response.text
    response=client.get('/api/v1/srm/accounts/capabilities',headers=accounts['preparer']['headers'])
    assert response.status_code==200,response.text
    assert response.json()['employee_id']==accounts['preparer']['employee']
    assert response.json()['work_prepare'] is True and response.json()['work_review'] is False
    accounts['reviewer']['user'].is_active=False;db.commit()
    response=client.get('/api/v1/srm/accounts/options',headers=accounts['headers'])
    assert response.status_code==200,response.text
    assert accounts['reviewer']['employee'] not in {row['id'] for row in response.json()['reviewers']}


def test_accounts_option_pages_have_independent_complete_native_cursors(client,db,accounts):
    with native_writer(db,accounts['manager'],accounts['branch']):
        scope=resolve_context(db,accounts['manager'],db.info['branch_context'],accounts['context'])
        cleanup=install(db,scope,policy=native_srm_policy('accounting_firm').policy)
        try:
            extra=SRMEngagement(organization_id=1,engagement_number='AC-PAGE-'+uuid4().hex,
                customer_id=101,name='Second client service',status='active',
                assigned_user_id=accounts['manager'].id,created_by=accounts['manager'].id)
            db.add(extra);db.commit()
            extra_id=extra.id
        finally:
            cleanup()
    first=client.get('/api/v1/srm/accounts/options',headers=accounts['headers'],params={'limit':1})
    assert first.status_code==200,first.text
    page=first.json()
    assert page['limit']==1
    assert page['has_more']=={'engagements':True,'preparers':True,'reviewers':True}
    assert [row['id'] for row in page['preparers']]==[accounts['preparer']['employee']]
    assert [row['id'] for row in page['reviewers']]==[accounts['reviewer']['employee']]
    second=client.get('/api/v1/srm/accounts/options',headers=accounts['headers'],params={
        'limit':1,'engagement_after':page['next']['engagements'],
        'preparer_after':page['next']['preparers'],'reviewer_after':page['next']['reviewers']})
    assert second.status_code==200,second.text
    final=second.json()
    assert [row['id'] for row in final['engagements']]==[extra_id]
    assert [row['id'] for row in final['preparers']]==[accounts['manager_employee']]
    assert [row['id'] for row in final['reviewers']]==[accounts['manager_employee']]
    assert final['next']=={'engagements':None,'preparers':None,'reviewers':None}
    assert not any(final['has_more'].values())


@pytest.mark.parametrize('status',['closed','cancelled'])
def test_closed_native_engagement_keeps_history_but_denies_new_period_work(client,db,accounts,status):
    original=body(accounts)
    row=send(client,accounts['headers'],'',original,status=201)
    with native_writer(db,accounts['manager'],accounts['branch']):
        scope=resolve_context(db,accounts['manager'],db.info['branch_context'],accounts['context'])
        cleanup=install(db,scope,policy=native_srm_policy('accounting_firm').policy)
        try:
            db.get(SRMEngagement,accounts['engagement']).status=status
            db.commit()
        finally:
            cleanup()
    history=client.get(BASE+f'/{row["id"]}',headers=accounts['headers'])
    assert history.status_code==200,history.text
    replayed=client.post(BASE,headers=accounts['headers'],json=original)
    assert replayed.status_code==201,replayed.text
    assert replayed.json()==row
    new_period=body(accounts)|{'starts_on':'2026-02-01','ends_on':'2026-02-28','due_on':'2026-03-10'}
    refused=client.post(BASE,headers=accounts['headers'],json=new_period)
    assert refused.status_code==409,refused.text
    send(client,accounts['preparer']['headers'],f'/{row["id"]}/work',
         revision(row)|{'summary':'A closed engagement cannot accept new work'},method='put',status=409)
    db.expire_all()
    assert db.query(AccountsPeriod).count()==1
    assert db.get(AccountsPeriod,row['id']).work_revision==0
