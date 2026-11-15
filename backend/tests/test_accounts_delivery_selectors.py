from copy import deepcopy
from uuid import uuid4
import pytest
from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSProject, PMSWorkspace, PMSTask
from app.apps.srm.models import SRMEngagement
from app.branches.models import BranchOwnership
from app.business_packs.models import PackRecordOwnership, PackContext
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, create
from tests.test_accounts_actual_time import delivery
from tests.test_business_pack_http_integration import native_actor, grant
from tests.test_srm_native_transaction_operations import native_writer

BASE='/api/v1/srm/accounts/periods'


def get(client,headers,path,status=200):
    response=client.get(BASE+path,headers=headers)
    assert response.status_code==status,response.text
    return response.json()


def enroll(db,case,table,ident):
    db.add(PackRecordOwnership(company_id=1,branch_id=case['branch'],context_id=case['context'],
        resource_table=table,resource_key=str(ident),source='explicit-selector-test'))
    if db.get(BranchOwnership,(table,str(ident))) is None:
        db.add(BranchOwnership(company_id=1,branch_id=case['branch'],resource_table=table,
            resource_key=str(ident),source='explicit-selector-test'))


def test_project_picker_requires_native_visibility_and_exact_ownership(client,db,accounts,delivery):
    db.get(SRMEngagement,accounts['engagement']).pms_project_id=None
    with native_writer(db,accounts['manager'],accounts['branch']):
        unowned=PMSProject(organization_id=1,branch_id=accounts['branch'],name='Unenrolled project',
            project_key=uuid4().hex[:16],manager_user_id=accounts['manager'].id)
        workspace=PMSWorkspace(organization_id=1,name='Private inaccessible workspace')
        db.add_all([unowned,workspace]);db.flush()
        hidden=PMSProject(organization_id=1,branch_id=accounts['branch'],workspace_id=workspace.id,
            name='Owned but native-hidden project',project_key=uuid4().hex[:16])
        db.add(hidden);db.flush()
    enroll(db,accounts,'pms_workspaces',workspace.id)
    enroll(db,accounts,'pms_projects',hidden.id)
    db.commit()
    row=create(client,accounts)
    choices=get(client,accounts['headers'],f"/{row['id']}/project-options?limit=1")
    assert choices=={'items':[{'id':delivery,'name':'Canonical client delivery','currency':'INR'}],'next':None}
    get(client,accounts['preparer']['headers'],f"/{row['id']}/project-options",403)


def test_task_picker_uses_owned_linked_native_upload_tasks_and_cursor(client,db,accounts,delivery):
    with native_writer(db,accounts['manager'],accounts['branch']):
        tasks=[PMSTask(project_id=delivery,task_key=uuid4().hex[:20],title=title)
            for title in ('First delivery task','Unenrolled task','Second delivery task')]
        db.add_all(tasks);db.flush()
    for task in (tasks[0],tasks[2]):
        enroll(db,accounts,'pms_tasks',task.id)
    db.commit()
    row=create(client,accounts)
    first=get(client,accounts['preparer']['headers'],f"/{row['id']}/task-options?limit=1")
    assert first=={'items':[{'id':tasks[0].id,'title':tasks[0].title}],'next':tasks[0].id}
    second=get(client,accounts['preparer']['headers'],f"/{row['id']}/task-options?limit=1&after={first['next']}")
    assert second=={'items':[{'id':tasks[2].id,'title':tasks[2].title}],'next':None}
    from app.apps.project_management.models import PMSProjectMember
    db.query(PMSProjectMember).filter_by(project_id=delivery,user_id=accounts['preparer']['user'].id).one().role='Viewer'
    db.commit()
    get(client,accounts['preparer']['headers'],f"/{row['id']}/task-options",403)


def test_billing_officer_period_reads_use_real_native_financial_scope(client,db,accounts):
    row=create(client,accounts)
    from tests.test_settings_hub import actor
    from app.branches.models import BranchGrant
    headers,user=actor(db,role='acct-fin-'+uuid4().hex,permissions=['srm_invoice_view'])
    user.organization_id=1
    db.add(BranchGrant(company_id=1,branch_id=accounts['branch'],user_id=user.id,can_write=True))
    policy=AccessPolicy(company_id=1,user_id=user.id,status='active',grants={
        'srm':{'enabled':True,'permissions':['srm_invoice_view'],'actions':['view'],'scope':'organization'}})
    db.add(policy);db.commit()
    grant(db,user,accounts['branch'],'accounting_firm','billing_officer',db.get(PackContext,accounts['context']))
    headers=headers|{'X-Suite-Branch':str(accounts['branch']),'X-Suite-Pack-Context':str(accounts['context'])}
    assert [item['id'] for item in get(client,headers,'')['items']]==[row['id']]
    assert get(client,headers,f"/{row['id']}")['project_id'] is None
    assert get(client,headers,f"/{row['id']}/billing")['invoice'] is None
    capabilities=client.get('/api/v1/srm/accounts/capabilities',headers=headers)
    assert capabilities.status_code==200,capabilities.text
    assert capabilities.json()['billing_view'] is True and capabilities.json()['billing_prepare'] is False
    assert capabilities.json()['documents_view'] is False and capabilities.json()['employee_id'] is None
    values=deepcopy(policy.grants);values['srm']['scope']='own';policy.grants=values;db.commit()
    assert get(client,headers,'')['items']==[]
    get(client,headers,f"/{row['id']}",404)
    values=deepcopy(policy.grants);values['srm']['permissions']=[];policy.grants=values;db.commit()
    get(client,headers,'',403)


def test_legacy_linked_period_never_uses_preparer_assignment_as_pms_visibility(client,db,accounts,delivery):
    row=create(client,accounts)
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one()
    policy.grants={key:value for key,value in policy.grants.items() if key!='project_management'}
    db.commit()
    get(client,accounts['preparer']['headers'],f"/{row['id']}",403)
    assert get(client,accounts['preparer']['headers'],'')['items']==[]
    manager_policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['manager'].id).one()
    manager_policy.grants={key:value for key,value in manager_policy.grants.items() if key!='project_management'}
    db.commit()
    options=client.get('/api/v1/srm/accounts/options',headers=accounts['headers'])
    assert options.status_code==200,options.text
    assert options.json()['engagements']==[] and options.json()['next']['engagements'] is None


def test_financial_period_reader_needs_real_native_project_visibility_without_hr_grant(client,db,accounts,delivery):
    from tests.test_settings_hub import actor
    from app.branches.models import BranchGrant
    from app.apps.project_management.models import PMSProjectMember
    row=create(client,accounts)
    headers,user=actor(db,role='acct-link-'+uuid4().hex,permissions=['srm_invoice_view'],grants={
        'srm':{'enabled':True,'permissions':['srm_invoice_view'],'actions':['view'],'scope':'organization'},
        'project_management':{'enabled':True,'permissions':['pms_view'],'actions':['view'],'scope':'own'}})
    user.organization_id=1
    db.add(BranchGrant(company_id=1,branch_id=accounts['branch'],user_id=user.id,can_write=True))
    member=PMSProjectMember(project_id=delivery,user_id=user.id,role='Viewer')
    db.add(member);db.commit()
    grant(db,user,accounts['branch'],'accounting_firm','billing_officer',db.get(PackContext,accounts['context']))
    headers=headers|{'X-Suite-Branch':str(accounts['branch']),'X-Suite-Pack-Context':str(accounts['context'])}
    assert get(client,headers,f"/{row['id']}")['project_id']==delivery
    status=get(client,headers,f"/{row['id']}/delivery")
    assert status['project']['id']==delivery and status['capabilities']['billing_view'] is True
    assert status['capabilities']['documents_request'] is False and status['capabilities']['time_record'] is False
    db.delete(member);db.commit()
    get(client,headers,f"/{row['id']}",403)
    assert get(client,headers,'')['items']==[]


def test_delivery_flags_follow_native_actions_review_invoice_and_lifecycle(client,db,accounts):
    from tests.test_accounts_billing import approved,billing
    row=approved(client,accounts)
    state=get(client,accounts['headers'],f"/{row['id']}/delivery")
    assert state['capabilities']['billing_prepare'] is True
    assert state['capabilities']['billing_view'] is True
    assert state['capabilities']['documents_request'] is False
    assert state['capabilities']['payments_record'] is False
    certificate=billing(client,accounts,row)
    state=get(client,accounts['headers'],f"/{row['id']}/delivery")
    assert state['invoice']=={'id':certificate['invoice_id'],'status':'draft'}
    assert state['capabilities']['billing_prepare'] is False and state['capabilities']['invoice_issue'] is True
    assert state['capabilities']['payments_record'] is False
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['manager'].id).one()
    values=deepcopy(policy.grants);values['srm']['actions'].remove('approve');policy.grants=values;db.commit()
    assert get(client,accounts['headers'],f"/{row['id']}/delivery")['capabilities']['invoice_issue'] is False
    db.get(SRMEngagement,accounts['engagement']).status='closed';db.commit()
    state=get(client,accounts['headers'],f"/{row['id']}/delivery")
    assert state['engagement_status']=='closed'
    assert state['capabilities']['project_link'] is False and state['capabilities']['documents_upload'] is False


@pytest.mark.parametrize('fault', ['client', 'currency', 'pms_client', 'default_currency'])
def test_project_commercial_mismatch_blocks_selector_link_and_linked_reads(client,db,accounts,delivery,fault):
    from app.apps.srm.commercial_models import ProjectCommercial
    from tests.test_accounts_periods import revision, send
    engagement=db.get(SRMEngagement,accounts['engagement'])
    client_id=engagement.customer_id
    # Use a genuine persisted second canonical client when testing a client mismatch.
    if fault in {'client','pms_client'}:
        from app.apps.crm.models import CRMCompany
        with native_writer(db,accounts['manager'],accounts['branch']):
            foreign=CRMCompany(name='Other commercial client',organization_id=1)
            db.add(foreign);db.flush()
            client_id=foreign.id
    with native_writer(db,accounts['manager'],accounts['branch']):
        if fault=='pms_client':
            from app.apps.project_management.models import PMSClient
            from app.apps.srm.commercial_models import CustomerLink
            native_client=PMSClient(name='Canonical linked client',organization_id=1)
            db.add(native_client);db.flush()
            db.get(PMSProject,delivery).client_id=native_client.id
            db.add(CustomerLink(source_type='pms_client',source_id=native_client.id,customer_id=client_id,organization_id=1))
        elif fault!='default_currency':
            db.add(ProjectCommercial(project_id=delivery,customer_id=client_id,seller_id=1,
                currency='USD' if fault=='currency' else engagement.currency))
    engagement.pms_project_id=None
    if fault=='default_currency':
        engagement.currency='USD'
    db.commit()
    row=create(client,accounts)
    assert get(client,accounts['headers'],f"/{row['id']}/project-options")['items']==[]
    send(client,accounts['headers'],f"/{row['id']}/project",revision(row)|{'project_id':delivery},status=409)
    assert db.get(SRMEngagement,accounts['engagement']).pms_project_id is None
    from app.business_packs.accounting_firm.models import AccountsCommand
    assert db.query(AccountsCommand).filter_by(period_id=row['id'],action='project.link').count()==0
    engagement.pms_project_id=delivery;db.commit()
    get(client,accounts['preparer']['headers'],f"/{row['id']}",409)
    send(client,accounts['preparer']['headers'],f"/{row['id']}/time",revision(row)|{
        'log_date':'2026-01-15','duration_minutes':30,'description':'Must not record foreign commercial work'},status=409)
