from datetime import date,datetime,timedelta,timezone
import pytest
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import account,middleware_database,BASE
from app.models.user import User
from app.models.employee import Employee
from app.models.company import Company,Branch
from app.models.notification import Notification
from app.common.models import CommonPerson
from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSTask,PMSTaskAssignee,PMSWorkspaceTeamMember
from app.services.metrics import queries as metrics

ROOT="/api/v1/metrics"

def test_approval_totals_cover_all_pages_and_exclude_other_organizations(client,db,population):
    from app.models.approval_os import ApprovalRequest
    data,_,_=population;owner,member,outsider,h,*_=data
    for i in range(325):
        db.add(ApprovalRequest(organization_id=1,source_module="crm",approval_type="Review",entity_type="lead",entity_id=i,title=f"Review {i}",assigned_to_user_id=owner.id,status="Pending",priority="High",sla_due_at=datetime.now(timezone.utc)-timedelta(days=1)))
    db.add(ApprovalRequest(organization_id=2,source_module="crm",approval_type="Review",entity_type="lead",entity_id=999,title="Other organization",assigned_to_user_id=owner.id,status="Pending"));db.commit()
    response=client.get("/api/v1/approval-os/inbox",headers=h,params={"scope":"all","page":7,"per_page":50})
    assert response.status_code==200,response.text
    body=response.json();assert body["total"]==325 and len(body["items"])==25
    assert body["summary"]["pending"]==325 and body["summary"]["overdue"]==325
    assert client.get("/api/v1/approval-os/summary",headers=h,params={"scope":"all"}).json()["total"]==325


def test_report_totals_and_cross_module_pages_are_not_preview_lengths(client,db,population):
    from app.apps.crm.models import CRMDeal,CRMPipeline,CRMPipelineStage
    from app.apps.analytics.models import AnalyticsReport
    from app.apps.analytics.services.engine import run_report
    data,_,_=population;owner,*_=data
    pipeline=CRMPipeline(organization_id=1,name="Report pipeline");db.add(pipeline);db.flush()
    stage=CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name="Open");db.add(stage);db.flush()
    db.add_all([CRMDeal(organization_id=1,name=f"Report deal {i}",pipeline_id=pipeline.id,stage_id=stage.id,currency="INR",amount=1) for i in range(625)])
    db.add(CRMDeal(organization_id=2,pipeline_id=pipeline.id,stage_id=stage.id,name="Foreign report deal",currency="USD",amount=999));db.commit()
    report=AnalyticsReport(name="Metrics cross module",module_name="lead_to_cash")
    result=run_report(db,report,True,page=7,page_size=100,user=owner)
    assert result["total"]==625 and len(result["items"])==25
    assert all(row["deal_name"]!="Foreign report deal" and row["margin"] is None for row in result["items"])
    report.module_name="crm_deals"
    export=run_report(db,report,True,page_size=5001,max_page_size=5001,user=owner)
    assert export["total"]==len(export["items"])==625
    report.owner_id=owner.id;db.add(report);db.commit()
    response=client.post(f"/api/v1/analytics/reports/{report.id}/export",headers=data[3],json={"export_type":"csv"})
    assert response.status_code==201,response.text
    assert response.json()["status"]=="completed" and response.json()["row_count"]==625

@pytest.fixture
def population(db,studio):
    owner,member,outsider,h,mh,oh,project,team,batch=studio
    outsider.is_active=False
    invite=User(email="invited-metrics@example.com",hashed_password="fixture",is_active=False,person=CommonPerson(organization_id=1,primary_email="invited-metrics@example.com",display_name="Invitation"))
    db.add(invite);db.flush();db.add(AccessPolicy(user_id=invite.id,company_id=1,status="invited",grants={}))
    branch=Branch(name="Metric HQ",company_id=1);db.add(branch);db.flush()
    records=[]
    for i,status in enumerate(["Probation","On Leave","Terminated","Active"]):
        row=Employee(employee_id=f"METRIC-{i}",first_name="Metric",last_name=str(i),status=status,branch_id=branch.id,date_of_joining=date(2026,1,1),deleted_at=datetime.now(timezone.utc) if i==3 else None)
        db.add(row);records.append(row)
    db.add(Company(id=2,name="Other Metrics",default_timezone="UTC"));db.flush()
    foreign_branch=Branch(name="Other HQ",company_id=2);db.add(foreign_branch);db.flush()
    db.add(Employee(employee_id="METRIC-FOREIGN",first_name="Foreign",last_name="Employee",status="Active",branch_id=foreign_branch.id,date_of_joining=date(2026,1,1)))
    team.members=[PMSWorkspaceTeamMember(user_id=owner.id),PMSWorkspaceTeamMember(user_id=member.id)]
    db.commit();return studio,invite,records


def test_hrms_and_pms_metrics_reconcile_without_conflating_employee_records(client,db,population):
    data,invite,records=population;owner,member,outsider,h,mh,oh,project,team,batch=data
    pms=client.get(BASE+"/people-workspace/reference",headers=h);assert pms.status_code==200,pms.text
    assert pms.json()["stats"]["total"]==3 and pms.json()["stats"]["active"]==2
    master=client.get("/api/v1/access/users",headers=h,params={"companyId":1,"perPage":1})
    assert master.status_code==200,master.text
    assert master.json()["summary"]["registered"]==3 and master.json()["summary"]["loginEnabled"]==2
    assert master.json()["summary"]["invited"]==1 and master.json()["summary"]["total"]==4
    for path in ["/api/v1/employees/count","/api/v1/employees/stats"]:
        response=client.get(path,headers=h);assert response.status_code==200,response.text
        assert response.json()["total"]==4 and response.json()["active"]==2 and response.json()["on_leave"]==1
    dashboard=client.get("/api/v1/reports/dashboard",headers=h)
    assert dashboard.status_code==200,dashboard.text
    assert dashboard.json()["headcount"]["total"]==4 and dashboard.json()["headcount"]["on_leave"]==1
    values=client.get(ROOT+"/values",headers=h,params={"ids":"users.total_registered,users.total_active,employees.total,employees.total_active"})
    assert values.status_code==200,values.text
    assert {m["id"]:m["value"] for m in values.json()["items"]}=={"users.total_registered":3,"users.total_active":2,"employees.total":4,"employees.total_active":2}
    assert "no-store" in values.headers["cache-control"]
    listing=client.get(BASE+"/people-workspace/people",headers=h)
    assert listing.json()["total"]==3 and invite.id not in [p["id"] for p in listing.json()["items"]]


def test_task_records_and_recipient_assignments_do_not_multiply(client,db,population):
    data,_,_=population;owner,member,outsider,h,mh,oh,project,team,batch=data
    today=date.fromisoformat(metrics.business_context(db,owner)["business_date"])
    for i,status in enumerate(["Done","Completed","Resolved","Closed","Cancelled","Blocked","In Progress"]):
        task=PMSTask(project_id=project["id"],title=status,task_key=f"MET-{i}",status=status,due_date=today-timedelta(days=1));db.add(task);db.flush()
        db.add_all([PMSTaskAssignee(task_id=task.id,user_id=owner.id),PMSTaskAssignee(task_id=task.id,user_id=member.id)])
    db.add(PMSTask(project_id=project["id"],title="Deleted",task_key="MET-DELETED",deleted_at=datetime.now(timezone.utc)));db.commit()
    response=client.get(BASE+f"/dashboard/{project['id']}",headers=h)
    assert response.status_code==200,response.text
    assert response.json()["metrics"]["total_tasks"]==7 and response.json()["metrics"]["completed_tasks"]==4 and response.json()["metrics"]["overdue_tasks"]==2
    assert response.json()["assignment_count"]==14 and response.json()["metrics"]["team_utilization"] is None
    values=client.get(ROOT+"/values",headers=h,params={"ids":"pms.tasks.total,pms.tasks.completed,pms.tasks.overdue,pms.assignments.total","project":project["id"]})
    assert values.status_code==200,values.text
    assert [m["value"] for m in values.json()["items"]]==[7,4,2,14]


def test_notification_badges_match_scoped_list_before_pagination(client,db,population):
    data,_,_=population;owner,member,outsider,h,*_=data
    for company,read in [(1,False),(1,False),(None,False),(2,False),(1,True)]:
        db.add(Notification(user_id=owner.id,company_id=company,title="Metric notification",message="Fixture",is_read=read,module="hrms",channels=["in_app"]))
    db.add(Notification(user_id=member.id,company_id=1,title="Someone else",message="Private",is_read=False,channels=["in_app"]));db.commit()
    unread=client.get("/api/v1/notifications/unread-count",headers=h).json()["unread"]
    listing=client.get("/api/v1/notifications/",headers=h,params={"unread_only":True,"per_page":1}).json()
    grouped=client.get("/api/v1/notifications/summary",headers=h).json()
    assert unread==3 and listing["total"]==3 and len(listing["items"])==1
    assert sum(g["count"] for g in grouped["groups"])==3


def test_permissions_and_immutable_audit_snapshots(client,db,population):
    data,_,_=population;owner,member,outsider,h,mh,oh,project,team,batch=data
    assert client.get(ROOT+"/inventory",headers=mh).status_code==403
    assert client.get(ROOT+"/values",headers=mh,params={"ids":"users.total_registered"}).status_code==403
    assert client.get(ROOT+"/values",headers=h,params={"ids":"employees.total","workspace":1}).status_code==422
    assert client.get(ROOT+"/values",headers=h,params={"ids":"pms.tasks.total","project":999999}).status_code==404
    request={"metrics":["users.total_registered","users.total_active","employees.total","employees.total_active","employees.on_leave","notifications.unread"]}
    audit=client.post(ROOT+"/audits",headers=h,json=request)
    assert audit.status_code==201,audit.text
    assert len(audit.json()["results"])>=10 and all(r["result"]=="match" for r in audit.json()["results"]),audit.text
    history=client.get(ROOT+"/audits",headers=h)
    assert history.status_code==200 and history.json()["items"][0]["id"]==audit.json()["id"]
    assert client.get(ROOT+f"/audits/{audit.json()['id']}",headers=mh).status_code==403
    export=client.get(ROOT+f"/audits/{audit.json()['id']}",headers=h)
    assert export.status_code==200 and export.json()["context"]["organization_id"]==1
    assert "SELECT " not in export.text and "hashed_password" not in export.text
    db.add(Employee(employee_id="METRIC-NEW",first_name="New",last_name="Record",status="Active",date_of_joining=date.today(),branch_id=member.employee.department.branch_id));db.commit()
    assert client.get(ROOT+"/values",headers=h,params={"ids":"employees.total"}).json()["items"][0]["value"]==5
    assert client.get(ROOT+f"/audits/{audit.json()['id']}",headers=h).json()==export.json()


def test_organization_business_date_boundary(db,population):
    owner=population[0][0]
    context=metrics.business_context(db,owner,datetime(2026,10,31,22,30,tzinfo=timezone.utc))
    assert context["business_date"]=="2026-11-01" and context["timezone"]=="Asia/Kolkata"


def test_crm_counts_full_query_and_keeps_currencies_separate(client,db,population):
    from app.apps.crm.models import CRMLead,CRMDeal,CRMPipeline,CRMPipelineStage
    from app.apps.crm.lead_models import CRMLeadOperatingState
    data,_,_=population;owner,member,outsider,h,*_=data
    leads=[CRMLead(organization_id=1,first_name="Metric",full_name=f"Metric lead {i}",status="New") for i in range(150)]
    db.add_all(leads);db.flush()
    db.add(CRMLeadOperatingState(organization_id=1,lead_id=leads[0].id,data_json={"archived":True}))
    leads[1].deleted_at=datetime.now(timezone.utc);leads[2].created_at=datetime(2020,1,1,tzinfo=timezone.utc)
    db.add(CRMLead(organization_id=2,first_name="Private",full_name="Other company lead"))
    pipeline=CRMPipeline(organization_id=1,name="Metrics pipeline");db.add(pipeline);db.flush()
    stages=[CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name=name,is_won=name=="Won",is_lost=name=="Lost") for name in ["Open","Won","Lost"]]
    db.add_all(stages);db.flush()
    for i,(code,amount) in enumerate([("INR",100),("USD",200),("INR",300)]):db.add(CRMDeal(organization_id=1,name=f"Metric deal {i}",pipeline_id=pipeline.id,stage_id=stages[0].id,amount=amount,currency=code,probability=50,expected_close_date=date.today()))
    for stage in stages[1:]:db.add(CRMDeal(organization_id=1,name=stage.name,pipeline_id=pipeline.id,stage_id=stage.id,status=stage.name,amount=1000,currency="INR",expected_close_date=date.today()))
    db.commit()
    dashboard=client.get("/api/v1/crm/dashboard",headers=h,params={"period":"all"})
    assert dashboard.status_code==200,dashboard.text
    body=dashboard.json();assert body["summary"]["leads"]==148 and body["summary"]["openDeals"]==3
    assert body["summary"]["pipelineValue"] is None
    amounts={r["currency"]:float(r["amount"]) for r in body["summary"]["pipelineByCurrency"]};assert amounts=={"INR":400,"USD":200}
    assert body["period_statistics"]["leads_created"]==148 and body["period_statistics"]["win_rate"]==50
    worklist=client.get("/api/v1/crm/statistics/records",headers=h,params={"kind":"leads","period":"all","page":2,"page_size":100})
    assert worklist.status_code==200,worklist.text
    assert worklist.json()["total"]==148 and len(worklist.json()["items"])==48
    current=client.get("/api/v1/crm/dashboard",headers=h,params={"period":"month"}).json()["period_statistics"]["leads_created"]
    assert current==147
    assert client.get("/api/v1/crm/statistics/records",headers=h,params={"kind":"leads","period":"month"}).json()["total"]==current
    forecast=client.get("/api/v1/crm/forecast",headers=h,params={"startDate":"2026-01-01","endDate":"2026-12-31"})
    assert forecast.status_code==200,forecast.text
    assert forecast.json()["filters"]["currency"]=="INR"
    from app.apps.crm.api.router import _filtered_report_deals
    from fastapi import HTTPException
    with pytest.raises(HTTPException,match="") as failure:
        _filtered_report_deals(db,1,datetime(2020,1,1,tzinfo=timezone.utc),datetime(2030,1,1,tzinfo=timezone.utc),current_user=owner)
    assert failure.value.status_code==422 and "currenc" in str(failure.value.detail)


def test_sales_snapshot_history_is_not_summed_and_invoice_units_are_explicit(client,db,population):
    from app.apps.srm.models import SRMInvoice,SRMEngagement,SRMProfitabilitySnapshot,SRMRevenueEvent
    data,_,_=population;owner,member,outsider,h,*_=data
    engagement=SRMEngagement(organization_id=1,engagement_number="MET-ENG",name="Metrics engagement",currency="INR",status="delivery_in_progress")
    db.add(engagement);db.flush()
    db.add_all([SRMProfitabilitySnapshot(organization_id=1,engagement_id=engagement.id,gross_margin_amount=10),SRMProfitabilitySnapshot(organization_id=1,engagement_id=engagement.id,gross_margin_amount=20)])
    for code,amount,org in [("INR",100,1),("USD",200,1),("GBP",90000,2)]:
        db.add(SRMInvoice(organization_id=org,invoice_number=f"MET-{code}",currency=code,total_amount=amount,balance_amount=amount,paid_amount=0,status="sent",issue_date=date.today(),due_date=date.today()-timedelta(days=1)))
    for kind,code,amount in [("invoice_sent","INR",100),("payment_received","INR",20),("invoice_sent","USD",200)]:db.add(SRMRevenueEvent(organization_id=1,event_type=kind,currency=code,amount=amount,recognized_on=date.today()))
    db.commit()
    response=client.get("/api/v1/srm/dashboard",headers=h)
    assert response.status_code==200,response.text
    body=response.json();assert body["total_invoiced_value"] is None
    assert {r["currency"]:float(r["amount"]) for r in body["currency_totals"]["total_invoiced_value"]}=={"INR":100,"USD":200}
    assert body["profitability_summary"]["gross_margin"]==20
    assert len(body["revenue_time_series"])==3


def test_shared_memberships_count_unique_identities_and_global_scope_is_explicit(client,db,population):
    from app.access.models import AccessMembership
    data,_,_=population;owner,member,outsider,h,*_=data
    db.add(AccessMembership(user_id=owner.id,company_id=2,active=True,is_admin=True));db.commit()
    dashboard=client.get("/api/v1/access/control/dashboard",headers=h)
    assert dashboard.status_code==200,dashboard.text
    assert dashboard.json()["summary"]["Total users"]==4 and dashboard.json()["summary"]["Registered users"]==3
    assert len(dashboard.json()["context"]["organizations"])==2
    switched={**h,"X-Suite-Organization":"2"}
    assert client.get(ROOT+"/values",headers=switched,params={"ids":"users.total_registered"}).json()["items"][0]["value"]==1
    # Membership in another company must not leak its projects into current-company totals.
    from app.apps.project_management.models import PMSProject,PMSWorkspace,PMSWorkspaceMember
    foreign=PMSWorkspace(organization_id=2,name="Other workspace");db.add(foreign);db.flush()
    db.add(PMSWorkspaceMember(workspace_id=foreign.id,user_id=owner.id,role="Owner"))
    db.add(PMSProject(organization_id=2,workspace_id=foreign.id,name="Private project",project_key="OTHER-MET"));db.commit()
    value=client.get(ROOT+"/values",headers=h,params={"ids":"pms.projects.total"})
    assert value.status_code==200,value.text
    assert value.json()["items"][0]["value"]==1


def test_full_default_audit_reads_each_registered_source(client,population):
    h=population[0][3]
    response=client.post(ROOT+"/audits",headers=h,json={})
    assert response.status_code==201,response.text
    assert response.json()["results"]
    assert not [r for r in response.json()["results"] if r["result"]=="mismatch"]


def test_unique_team_members_follow_membership_removals(client,db,population):
    from app.apps.project_management.models import PMSWorkspaceTeam
    data,_,_=population;owner,member,outsider,h,mh,oh,project,team,batch=data
    other=PMSWorkspaceTeam(workspace_id=team.workspace_id,name="Intern coordination",alias="intern-coordination",member_ids_json="[]")
    db.add(other);db.flush()
    db.add_all([PMSWorkspaceTeamMember(team_id=other.id,user_id=owner.id),PMSWorkspaceTeamMember(team_id=other.id,user_id=member.id)]);db.commit()
    def value():return client.get(ROOT+"/values",headers=h,params={"ids":"teams.total,teams.unique_members"}).json()["items"]
    assert [r["value"] for r in value()]==[2,2]
    db.query(PMSWorkspaceTeamMember).filter(PMSWorkspaceTeamMember.user_id==member.id).delete(synchronize_session=False);db.commit()
    assert [r["value"] for r in value()]==[2,1]


def test_concurrent_changes_are_not_reported_as_calculation_mismatches(client,db,population,monkeypatch):
    import app.services.metrics.api as source
    original=source.source_values
    data,_,_=population;owner,member,outsider,h,*_=data
    def changing(db,user,code,filters):
        values=original(db,user,code,filters)
        member.is_active=False;db.flush()
        return values
    monkeypatch.setattr(source,"source_values",changing)
    body=client.post(ROOT+"/audits",headers=h,json={"metrics":["users.total_active"]}).json()
    assert all(row["result"]=="not_comparable" for row in body["results"])
    assert all("Concurrent" in row["classification"] for row in body["results"])


def test_bounded_automation_log_totals_preserve_full_query_and_tenant(db,population):
    from app.apps.automation.models import AutomationExecutionLog
    from app.apps.automation.api.router import list_logs
    data,_,_=population;owner,*_=data
    db.add_all([AutomationExecutionLog(organization_id=1,module_name="crm",status="success") for _ in range(225)])
    db.add(AutomationExecutionLog(organization_id=2,module_name="crm",status="success"));db.commit()
    result=list_logs(db,owner)
    assert result["total"]==225 and len(result["items"])==200
