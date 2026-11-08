"""Regressions for action-specific permission branches found by native UI tests."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.access.catalog import action_for
from app.api.v1.payroll_guided import _allows_action,advance,GuidedAction
from app.api.v1.leave import cancel_leave

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
