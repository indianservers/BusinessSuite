"""Record scope, explicit identity and source-preserving PMS work regression tests."""
import pytest
from fastapi import HTTPException
from app.shared.record_360 import summary, record_work, events, queue
from app.apps.crm.models import CRMCompany, CRMLead, CRMTask, CRMNote
from app.apps.project_management.models import PMSClient, PMSProject, PMSTask, PMSTaskUpdateEntry
from app.apps.srm.commercial_models import CustomerLink
from tests.test_pms_workspaces import account, middleware_database
from datetime import date


def seeded(db):
    user, headers = account(db, 'record360-owner@test.com', True)
    from tests.tenant_test_utils import assign_company
    assign_company(db, user, 1)
    company = CRMCompany(organization_id=1, name='Same name', created_by_user_id=user.id)
    other = CRMCompany(organization_id=1, name='Same name', created_by_user_id=user.id)
    db.add_all([company, other]); db.flush()
    client = PMSClient(organization_id=1, name='Delivery client')
    db.add(client); db.flush()
    db.add(CustomerLink(organization_id=1, source_type='pms_client', source_id=client.id, customer_id=company.id))
    project = PMSProject(organization_id=1, project_key='R360', name='Linked delivery', client_id=client.id)
    db.add(project); db.flush()
    task = PMSTask(project_id=project.id, task_key='R360-1', title='Deliver', assignee_user_id=user.id, reporter_user_id=user.id, due_date=date.today())
    db.add(task); db.flush()
    entry = PMSTaskUpdateEntry(task_id=task.id, author_id=user.id, kind='followup', body='Confirm delivery', follow_up_date=date.today())
    db.add(entry); db.flush()
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, company, other, client, project, task, entry)
    db.commit()
    return user, headers, company, other, project, task, entry


def test_audit_customer_360_combines_only_linked_business_records(db):
    from app.apps.crm.models import CRMPipeline, CRMPipelineStage, CRMDeal, CRMActivity
    from app.apps.srm.models import SRMSalesOrder, SRMInvoice
    from test_identity_utils import own_workflow_records
    user, _, company, other, *_ = seeded(db)
    pipeline = CRMPipeline(organization_id=1, name="360 audit pipeline")
    db.add(pipeline); db.flush()
    stage = CRMPipelineStage(organization_id=1, pipeline_id=pipeline.id, name="New")
    db.add(stage); db.flush()
    deal = CRMDeal(organization_id=1, company_id=company.id, pipeline_id=pipeline.id, stage_id=stage.id, name="Linked 360 deal", owner_user_id=user.id)
    other_deal = CRMDeal(organization_id=1, company_id=other.id, pipeline_id=pipeline.id, stage_id=stage.id, name="Other company deal", owner_user_id=user.id)
    activity = CRMActivity(organization_id=1, company_id=company.id, activity_type="Call", subject="Linked 360 call", owner_user_id=user.id, created_by_user_id=user.id)
    order = SRMSalesOrder(organization_id=1, customer_id=company.id, order_number="SO-360-AUDIT", title="Linked 360 order", created_by=user.id)
    invoice = SRMInvoice(organization_id=1, customer_id=company.id, invoice_number="INV-360-AUDIT", issue_date=date.today())
    other_invoice = SRMInvoice(organization_id=1, customer_id=other.id, invoice_number="INV-OTHER-CUSTOMER", issue_date=date.today())
    db.add_all([deal, other_deal, activity, order, invoice, other_invoice]); db.flush()
    own_workflow_records(db, deal, other_deal, activity, order, invoice, other_invoice)
    db.commit()
    for source in ("crm", "srm"):
        record = summary("company", company.id, source, db, user)
        assert any(row["id"] == deal.id and row["kind"] == "deal" for row in record["relations"])
        assert not any(row["id"] == other_deal.id and row["kind"] == "deal" for row in record["relations"])
        history = events("company", company.id, source, 1, 100, "all", db, user)
        titles = {row["title"] for row in history["items"]}
        assert {"SO-360-AUDIT", "INV-360-AUDIT", "Linked 360 call"} <= titles
        assert "INV-OTHER-CUSTOMER" not in titles
        links = {row["title"]: row.get("url") for row in history["items"]}
        assert links["SO-360-AUDIT"] == f"/srm/sales-orders/{order.id}"
        assert links["INV-360-AUDIT"] == f"/srm/invoices/{invoice.id}"


def test_customer_identity_projects_and_work_are_not_name_matched(db):
    user, _, company, other, project, task, entry = seeded(db)
    first = summary('company', company.id, 'crm', db, user)
    assert first['projects'][0]['id'] == project.id
    assert summary('company', other.id, 'crm', db, user)['projects'] == []
    work = record_work('company', company.id, 'crm', 1, 25, db, user)
    assert {item['source'] for item in work['items']} == {'pms_task', 'pms_followup'}
    assert record_work('company', other.id, 'crm', 1, 25, db, user)['items'] == []


def test_lead_without_customer_and_exact_context(db):
    user, _, company, other, *_ = seeded(db)
    lead = CRMLead(organization_id=1, first_name='Solo', full_name='Solo lead', owner_user_id=user.id)
    db.add(lead); db.flush()
    db.add_all([CRMTask(organization_id=1, lead_id=lead.id, title='Lead call'), CRMTask(organization_id=1, company_id=company.id, title='Unrelated')])
    db.commit()
    assert summary('lead', lead.id, 'crm', db, user)['customer'] is None
    result = record_work('lead', lead.id, 'crm', 1, 25, db, user)
    assert [i['title'] for i in result['items']] == ['Lead call']


def test_events_stable_paging_and_soft_delete(db):
    user, _, company, *_ = seeded(db)
    db.add_all([CRMNote(organization_id=1, company_id=company.id, body='First'), CRMNote(organization_id=1, company_id=company.id, body='Second')]); db.commit()
    one = events('company', company.id, 'crm', 1, 1, 'note', db, user)
    two = events('company', company.id, 'crm', 2, 1, 'note', db, user)
    assert one['total'] == 2 and one['items'][0]['id'] != two['items'][0]['id']
    assert {one['items'][0]['body'], two['items'][0]['body']} == {'First', 'Second'}


def test_inaccessible_project_and_tenant_are_hidden(db):
    user, _, company, _, project, task, _ = seeded(db)
    outsider, _ = account(db, 'record360-outsider@test.com')
    assert summary('company', company.id, 'crm', db, user)['projects']
    with pytest.raises(HTTPException):
        summary('task', task.id, 'project_management', db, outsider)
    company.organization_id = 2; db.commit()
    with pytest.raises(HTTPException):
        summary('company', company.id, 'crm', db, user)


def test_http_queue_and_record_scope(client, db):
    user, headers, company, other, project, task, entry = seeded(db)
    response = client.get(f'/api/v1/record-360/company/{company.id}', headers=headers)
    assert response.status_code == 200, response.text
    result = client.get('/api/v1/record-360/work/queue/items', params={'view':'today'}, headers=headers)
    assert result.status_code == 200, result.text
    assert {i['source'] for i in result.json()['items']} == {'pms_task', 'pms_followup'}
    assert client.get('/api/v1/record-360/work/queue/items', params={'per_page': 1000}, headers=headers).status_code == 422


def test_pms_only_user_reuses_service_engine_without_crm_grant(db):
    from datetime import datetime, timezone, timedelta
    from app.models.user import Role, Permission
    from app.shared.follow_ups import CreateFollowUp, Change, create, change
    from tests.tenant_test_utils import assign_company
    user, _, company, other, project, task, entry = seeded(db)
    actor, _ = account(db, 'record360-pms-only@test.com')
    assign_company(db, actor, 1)
    permission = db.query(Permission).filter_by(name='pms_manage_tasks').first()
    if not permission:
        permission = Permission(name='pms_manage_tasks', module='project_management')
        db.add(permission)
    role = Role(name='record360_pms_only', permissions=[permission])
    db.add(role); actor.role = role
    project.manager_user_id = actor.id
    db.commit()
    followup = create(db, actor, CreateFollowUp(customer_id=company.id, title='Customer check-in', type='date', due_at=datetime.now(timezone.utc)+timedelta(days=1)))
    db.commit()
    result = record_work('company', company.id, 'project_management', 1, 25, db, actor)
    assert any(i['source']=='service_followup' and i['source_id']==followup.id for i in result['items'])
    change(followup.id, Change(action='complete', notes='Customer confirmed'), db, actor)
    result = record_work('company', company.id, 'project_management', 1, 25, db, actor)
    assert all(i['id']!=f'service_followup:{followup.id}' for i in result['items'])
    assert summary('company', company.id, 'project_management', db, actor)['customer']['id']==company.id


def test_resolved_pms_followup_retains_history_and_queue_source(db):
    from app.apps.project_management.task_workspace import EditEntry, edit_entry
    user, _, company, _, project, task, entry = seeded(db)
    edit_entry(entry.id, EditEntry(revision=entry.revision, resolved=True), db, user)
    focus = record_work('task', task.id, 'project_management', 1, 25, db, user)
    assert all(item['source']!='pms_followup' for item in focus['items'])
    completed = queue(1,25,'completed','','',project.id,None,db,user)
    assert completed['items'][0]['id']==f'pms_followup:{entry.id}'
    assert events('task',task.id,'project_management',1,25,'followup',db,user)['items'][0]['body']=='Confirm delivery'


def test_srm_view_does_not_grant_financial_or_pms_sections(db):
    from app.models.user import Role, Permission
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.api.router import _customer_360_payload
    user, _, company, _, project, task, entry = seeded(db)
    db.add(SRMInvoice(organization_id=1, invoice_number='PRIVATE-360', customer_id=company.id, issue_date=date.today(), total_amount=100, balance_amount=100))
    permission = db.query(Permission).filter_by(name='srm_view').first()
    if not permission:
        permission = Permission(name='srm_view', module='srm'); db.add(permission)
    user.role = Role(name='srm_viewer', permissions=[permission]); user.is_superuser=False
    db.commit()
    result = _customer_360_payload(db,user,company.id,{})
    assert result['matched'] is True
    assert result['invoices']==[] and result['receipts']==[] and result['profitability']==[]
    assert result['pms_projects']==[]
    assert result['sections']['invoices']=='restricted'
    event_result=events('company',company.id,'srm',1,25,'commercial',db,user)
    assert event_result['items']==[]
    assert event_result['sections']['invoices']=='restricted'


def test_srm_outstanding_is_grouped_by_currency(db):
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.api.router import _customer_360_payload
    user, _, company, *_ = seeded(db)
    for currency,amount in [('INR',100),('USD',20)]:
        db.add(SRMInvoice(organization_id=1, invoice_number=f'360-{currency}', customer_id=company.id, issue_date=date.today(), currency=currency, total_amount=amount, balance_amount=amount))
    db.commit()
    result=_customer_360_payload(db,user,company.id,{})
    assert result['outstanding_amount'] is None
    assert result['outstanding_by_currency']==[{'currency':'INR','amount':100.0},{'currency':'USD','amount':20.0}]


def test_history_equal_timestamps_do_not_repeat_between_pages(db):
    from datetime import datetime
    user, _, company, *_ = seeded(db)
    stamp=datetime(2026,11,4,9)
    db.add_all([CRMNote(organization_id=1,company_id=company.id,body=f'Note {i}',created_at=stamp) for i in range(12)])
    db.commit()
    ids=[events('company',company.id,'crm',page,1,'note',db,user)['items'][0]['source_id'] for page in range(1,13)]
    assert len(set(ids))==12
    assert ids==sorted(ids,reverse=True)


def test_queue_rejects_mismatched_customer_project(db):
    user, _, company, other, project, *_ = seeded(db)
    with pytest.raises(HTTPException) as error:
        queue(1,25,'all','','',project.id,other.id,db,user)
    assert error.value.status_code==422


def test_shared_customer_contract_is_identical_across_modules(client,db):
    user,headers,company,*_=seeded(db)
    names=[]
    for source in ('crm','srm','project_management'):
        result=client.get(f'/api/v1/record-360/company/{company.id}',params={'source':source},headers=headers)
        assert result.status_code==200,result.text
        names.append(result.json()['name'])
    assert names==[company.name]*3


def test_communication_events_require_permission_and_tenant_scope(db):
    from app.models.user import Role,Permission
    from app.apps.communication.models import CommunicationTimelineEvent
    from app.models.company import Company
    user,_,company,*_=seeded(db)
    db.add(Company(id=2,name='Other tenant'))
    db.add_all([CommunicationTimelineEvent(organization_id=1,record_type='account',record_id=company.id,channel='email',event_type='sent',subject='Visible mail'),CommunicationTimelineEvent(organization_id=2,record_type='account',record_id=company.id,channel='email',event_type='sent',subject='Private mail')])
    permission=db.query(Permission).filter_by(name='crm_view').first() or Permission(name='crm_view',module='crm')
    role=Role(name='record360_communications',permissions=[permission]);db.add(role);user.role=role;user.is_superuser=False;db.commit()
    assert events('company',company.id,'crm',1,25,'email',db,user)['items']==[]
    role.permissions.append(db.query(Permission).filter_by(name='communication_view').first() or Permission(name='communication_view',module='communication'));db.commit()
    result=events('company',company.id,'crm',1,25,'email',db,user)
    assert [e['title'] for e in result['items']]==['Visible mail']


def test_existing_crm_followups_meetings_and_calls_are_reused(db):
    from datetime import datetime,timedelta,timezone
    from app.apps.crm.models import CRMActivity,CRMMeeting,CRMCallLog
    user,_,company,*_=seeded(db)
    now=datetime.now(timezone.utc)
    db.add_all([CRMActivity(organization_id=1,company_id=company.id,subject='Existing lead workflow follow-up',activity_type='call',due_date=now,status='Pending'),CRMMeeting(organization_id=1,company_id=company.id,title='Existing meeting',start_time=now,end_time=now+timedelta(hours=1)),CRMCallLog(organization_id=1,company_id=company.id,direction='Outbound',phone_number='2025550101',call_time=now,outcome='Reached customer')]);db.commit()
    work=record_work('company',company.id,'crm',1,25,db,user)
    assert {'crm_activity','crm_meeting'}.issubset({item['source'] for item in work['items']})
    assert events('company',company.id,'crm',1,25,'call',db,user)['items'][0]['title']=='Reached customer'
    assert events('company',company.id,'crm',1,25,'meeting',db,user)['items'][0]['title']=='Existing meeting'


def test_related_task_timeline_copy_is_history_not_duplicate_work(db):
    from datetime import datetime, timedelta, timezone
    from app.apps.crm.models import CRMActivity
    user, _, company, *_ = seeded(db)
    due = datetime.now(timezone.utc) + timedelta(days=2)
    task = CRMTask(organization_id=1, company_id=company.id, title='Native task',
                   status='To Do', due_date=due, owner_user_id=user.id)
    db.add(task)
    db.flush()
    mirror = CRMActivity(organization_id=1, company_id=company.id, subject='Native task',
                         title='Native task', activity_type='task', status='To Do',
                         activity_date=datetime.now(timezone.utc),
                         metadata_json={'sourceEntity': 'tasks', 'sourceId': task.id})
    native = CRMActivity(organization_id=1, company_id=company.id, subject='Native follow-up',
                         activity_type='call', status='Pending', due_date=due)
    db.add_all([mirror, native])
    db.commit()
    work = record_work('company', company.id, 'crm', 1, 25, db, user)['items']
    assert len([item for item in work if item['title'] == 'Native task']) == 1
    assert any(item['source'] == 'crm_task' and item['source_id'] == task.id for item in work)
    assert any(item['source'] == 'crm_activity' and item['source_id'] == native.id for item in work)
    assert not any(item['source'] == 'crm_activity' and item['source_id'] == mirror.id for item in work)
    history = events('company', company.id, 'crm', 1, 25, 'activity', db, user)['items']
    assert any(item['source_id'] == mirror.id and item['title'] == 'Native task' for item in history)
