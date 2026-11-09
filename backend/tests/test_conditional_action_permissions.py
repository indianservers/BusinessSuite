"""Regressions for action-specific permission branches found by native UI tests."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.access.catalog import action_for
from app.api.v1.payroll_guided import _allows_action,advance,GuidedAction
from app.api.v1.leave import cancel_leave


def ensure_foreign_company(db):
    from app.models.company import Company
    if not db.get(Company, 2):
        db.add(Company(id=2, name='Foreign scope fixture'))
        db.flush()

def request(path,method):
    return SimpleNamespace(url=SimpleNamespace(path=path),method=method)

def test_asset_owner_acknowledgement_is_edit_not_assign():
    assert action_for(request("/api/v1/assets/assignments/17/acknowledge","PUT"))=="edit"
    assert action_for(request("/api/v1/assets/assignments/17/return","PUT"))=="assign"
    assert action_for(request("/api/v1/assets/assignments","POST"))=="assign"

@pytest.mark.parametrize("allowed",["view","create","edit","delete","configure","approve","assign"])
def test_guided_payroll_rechecks_each_body_action_before_mutating(allowed):
    actor=SimpleNamespace(is_superuser=False,_suite_grants={"hrms":{"enabled":True,"actions":["view",allowed]}})
    assert _allows_action(actor,"edit")== (allowed=="edit")
    assert _allows_action(actor,"approve")== (allowed=="approve")
    assert action_for(request("/api/v1/payroll/runs/17/guided","POST"))=="view"
    for action in ("review","approve","lock","pay","reconcile"):
        required="edit" if action=="review" else "approve"
        if allowed==required:continue
        with pytest.raises(HTTPException) as error:
            advance(17,GuidedAction(action=action,remarks="Permission regression"),None,actor)
        assert error.value.status_code==403

@pytest.mark.parametrize("employee",[None,SimpleNamespace(id=18)])
def test_leave_cancellation_rejects_missing_or_wrong_employee(employee):
    class Query:
        def filter(self,*args):return self
        def first(self):return SimpleNamespace(employee_id=17,status="Pending")
    db=SimpleNamespace(query=lambda *args:Query())
    with pytest.raises(HTTPException) as error:
        cancel_leave(1,db,SimpleNamespace(is_superuser=False,employee=employee))
    assert error.value.status_code==403

@pytest.mark.parametrize("action",["create","edit","assign"])
def test_follow_up_body_action_requires_exact_grant(monkeypatch,action):
    from app.shared import follow_ups
    monkeypatch.setattr('app.module_registry.is_app_enabled',lambda module:True)
    monkeypatch.setattr(follow_ups,'require',lambda *args:None)
    for allowed in ("create","edit","assign","approve","view"):
        actor=SimpleNamespace(is_superuser=False,_suite_current_module="crm",_suite_grants={"crm":{"enabled":True,"actions":["view",allowed]}})
        if action==allowed:follow_ups.access(actor,True,action=action)
        else:
            with pytest.raises(HTTPException) as error:follow_ups.access(actor,True,action=action)
            assert error.value.status_code==403
    assert action_for(request('/api/v1/follow-ups/17/actions','POST'))=='view'

def test_managed_finance_role_creates_reads_and_posts_its_voucher(client,db):
    from tests.fam_test_utils import fam_admin_headers,balanced_voucher_payload,auth_headers_for,FAM_ADMIN_PERMISSIONS
    from app.access.models import AccessPolicy
    from app.models.user import User
    admin=fam_admin_headers(client,db)
    payload=balanced_voucher_payload(client,admin)
    own=auth_headers_for(client,db,'conditional-finance@example.com','conditional_finance',permissions=FAM_ADMIN_PERMISSIONS)
    user=db.query(User).filter_by(email='conditional-finance@example.com').one()
    db.add(AccessPolicy(user_id=user.id,company_id=1,status='active',grants={'fam':{'enabled':True,'role':'editor','scope':'organization','permissions':FAM_ADMIN_PERMISSIONS,'actions':['view','create','edit','approve']}}));db.commit()
    result=client.post('/api/v1/fam/vouchers',headers=own,json=payload)
    assert result.status_code==201,result.text
    voucher=result.json()
    detail=client.get('/api/v1/fam/vouchers/'+str(voucher['id']),headers=own)
    assert detail.status_code==200,detail.text
    assert len(detail.json()['lines'])==2
    posted=client.post('/api/v1/fam/vouchers/'+str(voucher['id'])+'/post',headers=own)
    assert posted.status_code==200,posted.text


def test_finance_child_rejects_another_company_parent(db,superuser_headers):
    from datetime import date
    from app.apps.fam.models import FAMVoucher,FAMVoucherLine,FAMFinancialYear,FAMVoucherType
    from app.models.company import Company
    from app.models.user import User
    from app.access.scope import install_scope
    from tests.fam_test_utils import FAM_ADMIN_PERMISSIONS
    user=db.query(User).first()
    for company in (1,2):
        if not db.get(Company,company):db.add(Company(id=company,name='Finance company '+str(company)))
    db.flush()
    fy=FAMFinancialYear(company_id=2,name='QA cross-company',start_date=date(2026,4,1),end_date=date(2027,3,31))
    kind=FAMVoucherType(company_id=2,voucher_type_code='QA',voucher_type_name='QA',category='journal',numbering_prefix='QA')
    db.add_all([fy,kind]);db.flush()
    voucher=FAMVoucher(company_id=2,financial_year_id=fy.id,voucher_type_id=kind.id,voucher_number='QA-FOREIGN',voucher_date=date(2026,11,7),total_debit=0,total_credit=0,status='draft')
    db.add(voucher);db.flush();ident=voucher.id
    grants={'fam':{'enabled':True,'role':'editor','scope':'organization','permissions':FAM_ADMIN_PERMISSIONS,'actions':['view','create','edit','approve']}}
    cleanup=install_scope(db,user,1,grants)
    try:
        db.add(FAMVoucherLine(voucher_id=ident,line_number=1,ledger_id=1,debit_amount=0,credit_amount=0))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()

def test_hrms_children_inherit_only_their_own_company_parents(db,superuser_headers):
    from datetime import date
    from app.models.company import Company,Branch
    from app.models.user import User
    from app.models.payroll import PayrollPayGroup,PayrollPeriod,PayrollRun,PayrollRunAuditLog
    from app.models.recruitment import Job,Candidate
    from app.access.scope import install_scope
    actor=db.query(User).first()
    for ident in (1,2):
        if not db.get(Company,ident):db.add(Company(id=ident,name='Scoped company '+str(ident)))
    db.flush();branches=[];periods=[];jobs=[];runs=[]
    for company in (1,2):
        branch=Branch(company_id=company,name='Scoped branch '+str(company),code='HRCOND'+str(company));db.add(branch);db.flush();branches.append(branch)
        group=PayrollPayGroup(name='Scoped group '+str(company),code='HRCOND'+str(company),branch_id=branch.id);db.add(group);db.flush()
        period=PayrollPeriod(pay_group_id=group.id,month=2,year=2027,financial_year='2026-27',period_start=date(2027,2,1),period_end=date(2027,2,28),payroll_date=date(2027,2,28),status='Locked');db.add(period);periods.append(period)
        job=Job(title='Scoped job '+str(company),branch_id=branch.id);db.add(job);db.flush();jobs.append(job)
        db.add(Candidate(job_id=job.id,first_name='Scope',last_name=str(company),email='scope'+str(company)+'@example.com'))
        run=PayrollRun(company_id=company,branch_id=branch.id,month=2,year=2027,status='calculated');db.add(run);runs.append(run)
    db.flush();ids=[run.id for run in runs]
    cleanup=install_scope(db,actor,1,{'hrms':{'enabled':True,'scope':'organization','role':'editor','permissions':[],'actions':['view','edit']}})
    try:
        assert [row.id for row in db.query(Job).all()]==[jobs[0].id]
        assert [row.id for row in db.query(PayrollPeriod).all()]==[periods[0].id]
        assert [row.job_id for row in db.query(Candidate).all()]==[jobs[0].id]
        db.add(PayrollRunAuditLog(payroll_run_id=ids[0],actor_user_id=actor.id,action='conditional_review'));db.flush()
        db.add(PayrollRunAuditLog(payroll_run_id=ids[1],actor_user_id=actor.id,action='conditional_review'))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()

@pytest.mark.parametrize('path',['my-work/tasks/17/arrange','backlog/reorder','projects/17/board/reorder','sprints/17/reorder-tasks','tasks/17/move-to-sprint','tasks/17/remove-from-sprint'])
def test_arranging_existing_project_work_is_edit(path):
    assert action_for(request('/api/v1/project-management/'+path,'POST'))=='edit'
    assert action_for(request('/api/v1/project-management/projects/17/tasks','POST'))=='create'

@pytest.mark.parametrize('module',['crm','srm','hrms','project_management'])
def test_pipeline_routes_use_the_consuming_module(module):
    from app.access.catalog import request_module
    assert request_module(request('/api/v1/pipeline-workspaces/'+module+'/jobs/17/candidates','POST'))==module


@pytest.mark.parametrize("action", ["create", "edit", "delete", "export"])
def test_note_body_commands_require_their_action(action):
    from app.apps.project_management.notes import require_note_action
    actor=SimpleNamespace(is_superuser=False,_suite_grants={"project_management":{"enabled":True,"actions":["view",action]}})
    require_note_action(actor,action)
    for other in {"create","edit","delete","export"}-{action}:
        with pytest.raises(HTTPException) as error: require_note_action(actor,other)
        assert error.value.status_code==403
    assert action_for(request("/api/v1/project-management/note-actions/bulk","POST"))=="view"
    assert action_for(request("/api/v1/project-management/notes/1/restore","POST"))=="delete"


def test_personal_note_scope_uses_owner_company_and_children(db,superuser_headers):
    from app.models.user import User
    from app.models.company import Company
    from app.apps.project_management.models import PMSNote,PMSNoteRevision
    from app.access.scope import install_scope
    from test_identity_utils import attach_test_identity
    actor=db.query(User).first()
    if not db.get(Company,1):db.add(Company(id=1,name="Owner company"))
    if not db.get(Company,2):db.add(Company(id=2,name="Foreign company"))
    db.flush();attach_test_identity(db,actor,1)
    foreign=User(email="foreign-note@example.test",hashed_password="!not-login",is_active=True);db.add(foreign);db.flush();attach_test_identity(db,foreign,2)
    own=PMSNote(owner_id=actor.id,title="Own personal",content="private")
    other=PMSNote(owner_id=foreign.id,title="Foreign personal",content="private")
    db.add_all([own,other]);db.flush()
    db.add_all([PMSNoteRevision(note_id=n.id,version=1,title=n.title,content=n.content) for n in (own,other)]);db.flush()
    cleanup=install_scope(db,actor,1,{"project_management":{"enabled":True,"scope":"organization","actions":["view","edit"],"permissions":[]}})
    try:
        assert [n.id for n in db.query(PMSNote).all()]==[own.id]
        assert [n.note_id for n in db.query(PMSNoteRevision).all()]==[own.id]
    finally:cleanup();db.rollback()


@pytest.mark.parametrize("action", ["create", "edit", "assign", "delete", "view"])
def test_lead_patch_commands_recheck_the_body_action(action):
    from app.apps.crm.lead_management import require_patch_actions,LeadPayload
    actor=SimpleNamespace(is_superuser=False,_suite_grants={"crm":{"enabled":True,"actions":["view",action]}})
    for required,payload in [("edit",{"values":{"status":"Contacted"}}),("assign",{"values":{"owner_user_id":2},"details":{"assignmentReason":"Synthetic reassignment"}}),("delete",{"details":{"archived":True,"archiveReason":"Synthetic retirement"}})]:
        if action==required:require_patch_actions(actor,LeadPayload(**payload))
        else:
            with pytest.raises(HTTPException):require_patch_actions(actor,LeadPayload(**payload))
    assert action_for(request("/api/v1/crm/lead-management/bulk/apply","POST"))=="view"


@pytest.mark.parametrize("action,onboarding", [("view",False),("create",False),("edit",True)])
def test_deal_close_requires_edit_and_create_for_optional_work(action,onboarding):
    from app.apps.crm.deal_workspace import close
    actor=SimpleNamespace(is_superuser=False,_suite_grants={"crm":{"enabled":True,"actions":["view",action]}})
    with pytest.raises(HTTPException) as error:
        close(1,SimpleNamespace(onboarding=onboarding,reengagement_date=None),None,actor)
    assert error.value.status_code==403
    assert action_for(request("/api/v1/crm/deal-workspace/1/close","POST"))=="edit"


@pytest.mark.parametrize("path,method,action",[("notes/1/shares","POST","assign"),("notes/1/shares/2","DELETE","assign"),("notes/1/visibility","PUT","assign"),("work/submissions/1/review","POST","approve")])
def test_document_sharing_and_work_review_commands_use_exact_actions(path,method,action):
    assert action_for(request("/api/v1/project-management/"+path,method))==action


def test_srm_handoff_children_inherit_their_company_parent(db,superuser_headers):
    from app.models.user import User
    from app.apps.srm.models import SRMSalesOrder,SRMEngagement,SRMEngagementLink
    from app.access.scope import install_scope
    actor=db.query(User).first();parents=[]
    for company in (1,2):
        order=SRMSalesOrder(organization_id=company,order_number="COND-ORDER-"+str(company),title="Conditional order",created_by=actor.id);db.add(order);db.flush()
        engagement=SRMEngagement(organization_id=company,sales_order_id=order.id,engagement_number="COND-ENG-"+str(company),name="Conditional engagement",created_by=actor.id);db.add(engagement);db.flush();parents.append(engagement.id)
        db.add(SRMEngagementLink(engagement_id=engagement.id,linked_module="srm",linked_entity_type="sales_order",linked_entity_id=order.id))
    db.flush()
    cleanup=install_scope(db,actor,1,{"srm":{"enabled":True,"scope":"organization","actions":["view","create"],"permissions":[]}})
    try:
        assert [r.engagement_id for r in db.query(SRMEngagementLink).all()]==[parents[0]]
        db.add(SRMEngagementLink(engagement_id=parents[1],linked_module="srm",linked_entity_type="sales_order",linked_entity_id=1))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


def test_pms_work_review_inherits_submission_scope_and_rejects_foreign_parent(db,superuser_headers):
    from app.models.user import User
    from app.apps.project_management.models import PMSProject,PMSTask,PMSWorkSubmission,PMSWorkReview
    from app.access.scope import install_scope
    actor=db.query(User).first();submissions=[]
    for company in (1,2):
        project=PMSProject(organization_id=company,name="Scoped review",project_key="REVIEW-SCOPE-"+str(company));db.add(project);db.flush()
        task=PMSTask(project_id=project.id,title="Submission parent",task_key="REVIEW-1");db.add(task);db.flush()
        item=PMSWorkSubmission(task_id=task.id,user_id=actor.id,version=1,notes="Synthetic evidence");db.add(item);db.flush();submissions.append(item.id)
    cleanup=install_scope(db,actor,1,{"project_management":{"enabled":True,"scope":"organization","actions":["view","approve"],"permissions":[]}})
    def review(parent):return PMSWorkReview(submission_id=parent,reviewer_user_id=actor.id,decision="Approved",score=90,maximum_score=100,feedback="Synthetic review")
    try:
        db.add(review(submissions[0]));db.flush()
        assert [row.submission_id for row in db.query(PMSWorkReview).all()]==[submissions[0]]
        db.add(review(submissions[1]))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


@pytest.mark.parametrize("status,locked",[("draft",False),("rejected",False),("submitted",True),("approved",True)])
def test_time_log_list_exposes_timesheet_immutability(db,superuser_headers,status,locked):
    from datetime import date
    from app.models.user import User
    from app.apps.project_management.models import PMSTimesheet
    from app.apps.project_management.api.router import _mark_timesheet_locks
    actor=db.query(User).first();sheet=PMSTimesheet(organization_id=1,user_id=actor.id,week_start_date=date(2026,11,2),status=status);db.add(sheet);db.flush()
    linked=SimpleNamespace(timesheet_id=sheet.id);unlinked=SimpleNamespace(timesheet_id=None)
    assert _mark_timesheet_locks(db,[linked,unlinked])==[linked,unlinked]
    assert linked.timesheet_locked is locked
    assert unlinked.timesheet_locked is False


def test_picklist_values_follow_their_authorized_tenant_parent(db,superuser_headers):
    ensure_foreign_company(db)
    from app.models.user import User
    from app.common.models import CommonPerson
    from app.apps.customization.models import CustomizationGlobalPicklist,CustomizationGlobalPicklistValue
    from app.access.scope import install_scope
    actor=db.query(User).first();other=User(email="foreign-picklist-scope@example.com",hashed_password="unused",is_active=True,person=CommonPerson(organization_id=2,display_name="Foreign fixture"));db.add(other);db.flush()
    parents=[]
    for suffix,owner in [("own",actor),("foreign",other)]:
        parent=CustomizationGlobalPicklist(api_name="scope_"+suffix,label="Scoped picklist",created_by=owner.id);db.add(parent);db.flush();parents.append(parent.id)
        db.add(CustomizationGlobalPicklistValue(picklist_id=parent.id,value="Open",label="Open"))
    db.flush()
    # Legacy configuration ownership is stamped by tenant context, not creator identity.
    from app.models.security_boundary import SecurityResourceOwnership
    db.query(SecurityResourceOwnership).filter_by(resource_table="customization_global_picklists",resource_id=parents[1]).update({"company_id":2})
    db.flush()
    cleanup=install_scope(db,actor,1,{"customization":{"enabled":True,"scope":"organization","actions":["view","create","edit","delete"],"permissions":[]}})
    try:
        assert [row.picklist_id for row in db.query(CustomizationGlobalPicklistValue).all()]==[parents[0]]
        db.add(CustomizationGlobalPicklistValue(picklist_id=parents[0],value="Closed",label="Closed"));db.flush()
        db.add(CustomizationGlobalPicklistValue(picklist_id=parents[1],value="Blocked",label="Blocked"))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


@pytest.mark.parametrize("scope",["organization","own"])
def test_dashboard_widgets_inherit_real_owner_tenant_and_scope(db,superuser_headers,scope):
    from app.models.user import User
    from app.common.models import CommonPerson
    from app.apps.analytics.models import AnalyticsDashboard,AnalyticsDashboardWidget
    from app.access.scope import install_scope
    actor=db.query(User).first()
    other=User(email="foreign-dashboard-scope@example.com",hashed_password="unused",is_active=True,person=CommonPerson(organization_id=2,display_name="Foreign dashboard owner"));db.add(other);db.flush()
    parents=[]
    for owner in (actor,other):
        dashboard=AnalyticsDashboard(name="Scoped dashboard",owner_id=owner.id);db.add(dashboard);db.flush();parents.append(dashboard.id)
        db.add(AnalyticsDashboardWidget(dashboard_id=dashboard.id,widget_type="kpi",title="Scoped widget"))
    db.flush()
    cleanup=install_scope(db,actor,1,{"analytics":{"enabled":True,"scope":scope,"actions":["view","create","edit","delete"],"permissions":[]}})
    try:
        created=AnalyticsDashboard(name="Managed dashboard",owner_id=actor.id);db.add(created);db.flush()
        from app.apps.analytics.models import AnalyticsReport
        report=AnalyticsReport(name="Managed report",owner_id=actor.id,module_name="crm",data_source_json={"table":"crm_deals"});db.add(report);db.flush()
        assert [row.id for row in db.query(AnalyticsDashboard).order_by(AnalyticsDashboard.id).all()]==[parents[0],created.id]
        assert [row.dashboard_id for row in db.query(AnalyticsDashboardWidget).all()]==[parents[0]]
        db.add(AnalyticsDashboardWidget(dashboard_id=parents[0],widget_type="kpi",title="Authorized widget"));db.flush()
        db.add(AnalyticsDashboardWidget(dashboard_id=parents[1],widget_type="kpi",title="Foreign widget"))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


def test_calculated_payroll_components_inherit_record_run_and_employee_scope(db,superuser_headers):
    ensure_foreign_company(db)
    from datetime import date
    from app.models.user import User
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.models.payroll import PayrollRun,PayrollRecord,PayrollComponent
    from app.access.scope import install_scope
    actor=db.query(User).first();branch=db.query(Branch).filter_by(company_id=1).first()
    employee=Employee(employee_id="COMPONENT-SCOPE",first_name="Scoped",last_name="Payroll",date_of_joining=date.today(),branch_id=branch.id,user_id=actor.id);db.add(employee);db.flush()
    records=[]
    for company in (1,2):
        run=PayrollRun(month=11,year=2026,company_id=company);db.add(run);db.flush()
        record=PayrollRecord(payroll_run_id=run.id,employee_id=employee.id);db.add(record);db.flush();records.append(record.id)
        db.add(PayrollComponent(record_id=record.id,component_name="Basic",amount=100))
    db.flush()
    cleanup=install_scope(db,actor,1,{"hrms":{"enabled":True,"scope":"organization","actions":["view","create","edit"],"permissions":[]}})
    try:
        assert [row.record_id for row in db.query(PayrollComponent).all()]==[records[0]]
        checks=[];original_query=db.query
        def track_parent(*entities,**kwargs):
            if len(entities)==1 and entities[0] is PayrollRecord.id:checks.append(True)
            return original_query(*entities,**kwargs)
        db.query=track_parent
        try:
            db.add_all([PayrollComponent(record_id=records[0],component_name="Allowance "+str(index),amount=10) for index in range(12)]);db.flush()
            assert len(checks)==1
        finally:db.query=original_query
        db.add(PayrollComponent(record_id=records[1],component_name="Foreign",amount=10))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


def test_attendance_month_lock_actor_stamps_do_not_replace_tenant_ownership(db,superuser_headers):
    ensure_foreign_company(db)
    from app.models.user import User
    from app.models.attendance import AttendanceMonthLock
    from app.models.security_boundary import SecurityResourceOwnership
    from app.core.tenant_boundary import legacy_root
    from app.access.scope import install_scope
    actor=db.query(User).first();locks=[]
    assert legacy_root(AttendanceMonthLock)
    for company in (1,2):
        lock=AttendanceMonthLock(month=11,year=2026,locked_by=actor.id);db.add(lock);db.flush();locks.append(lock.id)
        db.query(SecurityResourceOwnership).filter_by(resource_table="attendance_month_locks",resource_id=lock.id).update({"company_id":company})
    db.flush()
    cleanup=install_scope(db,actor,1,{"hrms":{"enabled":True,"scope":"organization","actions":["view","edit"],"permissions":[]}})
    try:
        assert [row.id for row in db.query(AttendanceMonthLock).all()]==[locks[0]]
        own=db.query(AttendanceMonthLock).first();own.status="Unlocked";own.unlocked_by=actor.id;db.flush()
        assert db.query(AttendanceMonthLock).filter_by(id=locks[1]).first() is None
    finally:cleanup();db.rollback()


def test_chat_messages_inherit_conversation_workspace_tenant(db,superuser_headers):
    from app.models.user import User
    from app.apps.project_management.models import PMSWorkspace
    from app.apps.project_management.chat_models import ChatConversation,ChatMessage
    from app.access.scope import install_scope
    actor=db.query(User).first();parents=[]
    for company in (1,2):
        workspace=PMSWorkspace(name="Scoped chat workspace",organization_id=company);db.add(workspace);db.flush()
        conversation=ChatConversation(workspace_id=workspace.id,key="scoped-chat-"+str(company),kind="channel",owner_id=actor.id);db.add(conversation);db.flush();parents.append(conversation.id)
        db.add(ChatMessage(conversation_id=conversation.id,author_id=actor.id,client_id="fixture",body="Private synthetic message"))
    db.flush()
    cleanup=install_scope(db,actor,1,{"project_management":{"enabled":True,"scope":"organization","actions":["view","create","edit","delete"],"permissions":[]}})
    try:
        assert [row.conversation_id for row in db.query(ChatMessage).all()]==[parents[0]]
        db.add(ChatMessage(conversation_id=parents[0],author_id=actor.id,client_id="own",body="Authorized message"));db.flush()
        db.add(ChatMessage(conversation_id=parents[1],author_id=actor.id,client_id="foreign",body="Denied message"))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


def test_hr_timesheet_entries_inherit_timesheet_project_and_employee_tenant(db,superuser_headers):
    from datetime import date
    from app.models.user import User
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.models.timesheet import Project,Timesheet,TimesheetEntry
    from app.access.scope import install_scope
    actor=db.query(User).first();branch=db.query(Branch).filter_by(company_id=1).first()
    employee=Employee(employee_id="ENTRY-SCOPE",first_name="Scoped",last_name="Timesheet",date_of_joining=date.today(),branch_id=branch.id,user_id=actor.id);db.add(employee);db.flush();parents=[]
    for company in (1,2):
        project=Project(code="ENTRY-SCOPE-"+str(company),name="Scoped project",organization_id=company);db.add(project);db.flush()
        sheet=Timesheet(employee_id=employee.id,project_id=project.id,period_start=date(2026,11,2),period_end=date(2026,11,8));db.add(sheet);db.flush();parents.append(sheet.id)
        db.add(TimesheetEntry(timesheet_id=sheet.id,work_date=date(2026,11,8),hours=1))
    db.flush()
    cleanup=install_scope(db,actor,1,{"hrms":{"enabled":True,"scope":"organization","actions":["view","create","edit","approve"],"permissions":[]}})
    try:
        assert [row.timesheet_id for row in db.query(TimesheetEntry).all()]==[parents[0]]
        db.add(TimesheetEntry(timesheet_id=parents[0],work_date=date(2026,11,8),hours=2));db.flush()
        db.add(TimesheetEntry(timesheet_id=parents[1],work_date=date(2026,11,8),hours=2))
        with pytest.raises(HTTPException) as error:db.flush()
        assert error.value.status_code==403
    finally:cleanup();db.rollback()


@pytest.mark.parametrize("suffix,expected",[("presence","view"),("preferences","view"),("mute","view"),("read","view"),("draft","create"),("messages/7/saved","view"),("messages/7/reactions/thumbs-up","create"),("messages/7/pin","edit")])
@pytest.mark.parametrize("namespace",["collaboration","project-management"])
def test_chat_personal_state_and_authored_content_actions_are_distinct(namespace,suffix,expected):
    assert action_for(request(f"/api/v1/{namespace}/workspaces/1/chat/conversations/2/{suffix}","PUT"))==expected


@pytest.mark.parametrize("module",["project_management","crm","hrms","srm","fam"])
@pytest.mark.parametrize("allowed",["create","edit","delete"])
def test_shared_chat_requires_specific_managed_action_in_business_module(module,allowed):
    from app.shared.communication.gateway import require_communication_action
    actor=SimpleNamespace(is_superuser=False,_suite_grants={module:{"enabled":True,"actions":["view",allowed]}})
    require_communication_action(actor,"view")
    require_communication_action(actor,allowed)
    for denied in {"create","edit","delete"}-{allowed}:
        with pytest.raises(HTTPException) as error:require_communication_action(actor,denied)
        assert error.value.status_code==403


@pytest.mark.parametrize("grants",[{}, {"crm":{"enabled":False,"actions":["view","create"]}}, {"ai":{"enabled":True,"actions":["view","create"]}}])
def test_shared_chat_does_not_accept_disabled_or_unrelated_grants(grants):
    from app.shared.communication.gateway import require_communication_action
    with pytest.raises(HTTPException):require_communication_action(SimpleNamespace(is_superuser=False,_suite_grants=grants),"create")
