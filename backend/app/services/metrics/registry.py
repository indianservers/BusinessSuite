"""Versioned business definitions, separate from display labels and paged lists."""
from dataclasses import dataclass, asdict
from fastapi import HTTPException
from sqlalchemy import func
from app.services.metrics import queries as q


@dataclass(frozen=True)
class Metric:
    id: str
    name: str
    module: str
    definition: str
    source: str
    methodology: str = "COUNT DISTINCT authoritative primary key before pagination"
    supported_filters: tuple[str,...] = ("organization",)
    permission_scope: str = "Current organization intersected with authenticated module/record grants"
    time_period: str = "Current snapshot; no historical headcount inferred"
    cache_policy: str = "no-store"
    refresh: str = "On request, explicit refresh and affected successful mutations"
    version: int = 1


def metric(code,name,module,definition,source,**kwargs):
    return Metric(code,name,module,definition,source,**kwargs)


DEFINITIONS=[
    metric("users.total_registered","Registered users","identity","Unique provisioned user identities with accepted organization access; excludes pending access invitations. Profiles and memberships never add extra users.","User.id + CommonPerson.organization_id / AccessMembership; excludes invited AccessPolicy"),
    metric("users.total_active","Login-enabled registered users","identity","Registered identities whose global login switch is enabled. This differs from employment status or per-module policy enablement.","User.id; User.is_active"),
    metric("users.total_accounts","Provisioned accounts","identity","Unique account rows, including accounts awaiting an access invitation; standalone email invitations without an account are excluded.","User.id"),
    metric("employees.total","Employee records","hrms","All nondeleted employee records, including interns and employees without login accounts. Each Employee.id counts once.","Employee.id",supported_filters=("organization","department")),
    metric("employees.total_active","Active / probation employees","hrms","Nondeleted employee records with status Active or Probation. Login access is a separate metric.","Employee.id",supported_filters=("organization","department")),
    metric("employees.on_leave","Employees on leave","hrms","Nondeleted employee records explicitly marked On Leave; never total minus active.","Employee.id",supported_filters=("organization","department")),
    metric("interns.total","Intern records","internhub","Nondeleted employee records explicitly classified Intern, within InternHub management scope. No inference from team names.","Employee.id / InternHub employee_query"),
    metric("interns.total_active","Active / probation interns","internhub","Scoped intern employee records with status Active or Probation.","Employee.id / InternHub employee_query"),
    *[metric("teams."+key,name,"pms",definition,source,supported_filters=("organization","workspace","team")) for key,name,definition,source in [
        ("total","Visible teams","Team rows in accessible nonarchived workspaces, respecting private-team visibility.","PMSWorkspaceTeam.id"),
        ("unique_members","Unique team members","Distinct visible registered user IDs across selected visible teams, not sum of membership edges.","PMSWorkspaceTeamMember.user_id")]],
    *[metric("pms.tasks."+key,name,"pms",definition,"PMSTask.id",supported_filters=("organization","workspace","project")) for key,name,definition in [
        ("total","Task records","Unique live task records, including subtasks; 50 recipients still represent one task record."),
        ("completed","Completed task records","Live tasks in Done, Completed, Closed or Resolved."),
        ("overdue","Overdue task records","Live tasks due before the organization's current business date, excluding completed/cancelled/rejected states."),
        ("due_today","Tasks due today","Open task records due on the organization's business date."),
        ("blocked","Blocked task records","Live tasks explicitly in Blocked state.")]],
    metric("pms.assignments.total","Individual assignments","pms","Uncancelled recipient execution rows for visible live task records; intentionally differs from unique task count.","PMSTaskAssignee composite task/user key",supported_filters=("organization","workspace","project")),
    *[metric("pms.projects."+key,name,"pms",definition,"PMSProject.id",supported_filters=("organization","workspace","project")) for key,name,definition in [
        ("total","Visible projects","Accessible live projects outside archived workspaces, before pagination."),
        ("active","Open projects","Visible projects outside Completed, Archived and Cancelled states."),
        ("completed","Completed projects","Visible projects explicitly in Completed state; progress percentage alone does not close a project.")]],
    *[metric("internhub.batches."+state.lower(),state+" intern batches","internhub","Authorized InternHub batch rows explicitly in "+state+" state.","InternBatch.id") for state in ["Active","Upcoming","Completed"]],
    metric("crm.contacts.total","Contacts","crm","Visible nonarchived, nondeleted CRM contact records; no lead/contact identity merging.","CRMContact.id"),
    metric("crm.leads.total","Leads","crm","Visible nonarchived, nondeleted CRM lead records, including converted leads unless the worklist explicitly filters conversion.","CRMLead.id"),
    metric("crm.leads.active","Active leads","crm","Visible leads outside Converted, Lost, Disqualified and Archived states.","CRMLead.id"),
    metric("crm.deals.open","Open deals","crm","Visible nondeleted, nonarchived deals outside Won/Lost/Cancelled states, also respecting terminal pipeline stages.","CRMDeal.id / CRMPipelineStage"),
    metric("crm.pipeline.value","Open pipeline by currency","crm","Sum open-deal amount separately by explicit currency. No cross-currency scalar or implicit exchange rate.","CRMDeal.amount / currency",methodology="SUM GROUP BY currency; Unknown currency stays Unknown"),
    metric("notifications.unread","Unread notifications","notifications","Personal unread notification rows in the active organization or explicitly tenantless notifications addressed to this user.","Notification.id",permission_scope="Authenticated user only"),
    metric("hrms.attendance.present_today","Present employees today","hrms","Distinct eligible employee IDs with latest attendance status Present, WFH or Half-day on the organization's business date.","Attendance.employee_id",time_period="Today in the active organization's timezone"),
    metric("srm.orders.total","Sales orders","srm","Authorized live sales order records, independent of invoice count or line items.","SRMSalesOrder.id"),
    metric("srm.invoices.total","Sales invoices","srm","Authorized live sales invoice records, independent of invoice items and collections.","SRMInvoice.id"),
    metric("fam.ledgers.active","Active ledgers","fam","Active ledgers in the active organization. Monetary balances use the accounting company's base currency.","FAMLedger.id"),
]
REGISTRY={definition.id:definition for definition in DEFINITIONS}


def access_admin(db,user):
    from app.access.models import AccessMembership
    return user.is_superuser or bool(db.query(AccessMembership.id).filter_by(user_id=user.id,company_id=q.company_id(user),active=True,is_admin=True).first())


def allowed(db,user,definition):
    if definition.module=="notifications":return True
    if definition.module=="identity":return access_admin(db,user)
    grants=getattr(user,"_suite_grants",None)
    key={"pms":"project_management","internhub":"hrms"}.get(definition.module,definition.module)
    if grants is not None and not user.is_superuser:
        grant=grants.get(key,{})
        if not grant.get("enabled") or not set(grant.get("actions",[])).intersection({"view","read","configure"}):return False
    if user.is_superuser:return True
    from app.access.catalog import permission_objects
    permissions={p.name for p in permission_objects(user)}
    needed={"hrms":{"employee_view","reports_view","attendance_view"},"internhub":{"intern_management_view","intern_management_manage","employee_view"},"pms":{"pms_view","pms_manage_projects","pms_manage_tasks","pms_admin"},"crm":{"crm_view","crm_manage","crm_admin"},"srm":{"srm_view","srm_invoice_view","srm_admin"},"fam":{"fam_view","fam_admin"}}.get(definition.module,set())
    return bool(permissions & needed)


def catalog(db,user):
    return [asdict(m) for m in DEFINITIONS if allowed(db,user,m)]


def crm_query(db,user,resource):
    from app.apps.crm.api.router import _base_query,_get_resource,_organization_id,_apply_record_visibility
    spec=_get_resource(resource)
    query=_apply_record_visibility(_base_query(db,spec,_organization_id(db,user)),spec,user,db)
    if resource=="leads":
        from app.apps.crm.lead_models import CRMLeadOperatingState
        from app.apps.crm.models import CRMLead
        archived=db.query(CRMLeadOperatingState.lead_id).filter(CRMLeadOperatingState.organization_id==_organization_id(db,user),CRMLeadOperatingState.data_json["archived"].as_boolean().is_(True))
        query=query.filter(CRMLead.id.notin_(archived))
    return query


def open_deals(db,user):
    from app.apps.crm.models import CRMDeal,CRMPipelineStage
    closed=db.query(CRMPipelineStage.id).filter((CRMPipelineStage.is_won.is_(True)) | (CRMPipelineStage.is_lost.is_(True)))
    return crm_query(db,user,"deals").filter(CRMDeal.status.notin_(["Won","Lost","Cancelled","Canceled"]),CRMDeal.stage_id.notin_(closed))


def evaluate(db,user,code,filters=None):
    from app.models.user import User
    from app.models.employee import Employee
    filters=filters or {}
    m=REGISTRY.get(code)
    if not m:raise HTTPException(404,"Unknown metric identifier")
    if not allowed(db,user,m):raise HTTPException(403,"Metric unavailable in your permission scope")
    if set(filters)-set(m.supported_filters):raise HTTPException(422,"Unsupported metric filters: "+", ".join(sorted(set(filters)-set(m.supported_filters))))
    if filters.get("workspace"):
        from app.apps.project_management.people_workspace import workspace_query
        from app.apps.project_management.models import PMSWorkspace
        if not workspace_query(db,user).filter(PMSWorkspace.id==filters["workspace"]).first():raise HTTPException(404,"Workspace outside permitted scope")
    if filters.get("team"):
        from app.apps.project_management.people_workspace import teams_query
        from app.apps.project_management.models import PMSWorkspaceTeam
        if not teams_query(db,user).filter(PMSWorkspaceTeam.id==filters["team"]).first():raise HTTPException(404,"Team outside permitted scope")
    if filters.get("project"):
        from app.apps.project_management.access import get_project_for_action
        get_project_for_action(db,filters["project"],user,"browse")
    if code.startswith("users."):
        query=q.registered_users(db,user,include_invited=code=="users.total_accounts")
        if code=="users.total_active":query=query.filter(User.is_active.is_(True))
        return q.unique_count(query,User.id)
    if code.startswith("employees."):
        query=q.employee_records(db,user)
        if filters.get("department"):query=query.filter(Employee.department_id==filters["department"])
        if code.endswith("total_active"):query=query.filter(Employee.status.in_(q.EMPLOYED))
        if code.endswith("on_leave"):query=query.filter(Employee.status=="On Leave")
        return q.unique_count(query,Employee.id)
    if code.startswith("interns."):
        from app.apps.interns_hub.management_access import employee_query,require_admin
        require_admin(user);query=employee_query(db,user)
        if code.endswith("total_active"):query=query.filter(Employee.status.in_(q.EMPLOYED))
        return q.unique_count(query,Employee.id)
    if code.startswith("internhub.batches."):
        from app.apps.interns_hub.management_access import batch_query,require_admin
        from app.apps.interns_hub.management_models import InternBatch
        require_admin(user)
        return q.unique_count(batch_query(db,user).filter(InternBatch.status==code.rsplit(".",1)[-1].title()),InternBatch.id)
    if code.startswith("teams."):
        from app.apps.project_management.people_workspace import teams_query,scope
        from app.apps.project_management.models import PMSWorkspaceTeam,PMSWorkspaceTeamMember
        query=teams_query(db,user)
        if filters.get("workspace"):query=query.filter(PMSWorkspaceTeam.workspace_id==filters["workspace"])
        if filters.get("team"):query=query.filter(PMSWorkspaceTeam.id==filters["team"])
        if code=="teams.total":return q.unique_count(query,PMSWorkspaceTeam.id)
        members=db.query(PMSWorkspaceTeamMember).filter(PMSWorkspaceTeamMember.team_id.in_(query.with_entities(PMSWorkspaceTeam.id)),PMSWorkspaceTeamMember.user_id.in_(scope(db,user).with_entities(User.id)))
        return q.unique_count(members,PMSWorkspaceTeamMember.user_id)
    if code.startswith("pms.tasks.") or code=="pms.assignments.total":
        key=code.rsplit(".",1)[-1] if code.startswith("pms.tasks.") else "assignments"
        return q.task_counts(db,user,filters.get("project"),filters.get("workspace"))[key]
    if code.startswith("pms.projects."):
        from app.apps.project_management.access import accessible_project_query
        from app.apps.project_management.models import PMSProject
        query=accessible_project_query(db,user)
        if filters.get("workspace"):query=query.filter(PMSProject.workspace_id==filters["workspace"])
        if filters.get("project"):query=query.filter(PMSProject.id==filters["project"])
        if code.endswith(".active"):query=query.filter(PMSProject.status.notin_(["Completed","Archived","Cancelled"]))
        if code.endswith(".completed"):query=query.filter(PMSProject.status=="Completed")
        return q.unique_count(query,PMSProject.id)
    if code=="notifications.unread":
        from app.models.notification import Notification
        return q.personal_notifications(db,user).filter(Notification.is_read.is_(False)).count()
    if code=="hrms.attendance.present_today":return q.attendance_counts(db,user)["present"]
    if code=="crm.contacts.total":
        from app.apps.crm.models import CRMContact
        return q.unique_count(crm_query(db,user,"contacts"),CRMContact.id)
    if code.startswith("crm.leads."):
        from app.apps.crm.models import CRMLead
        query=crm_query(db,user,"leads")
        if code.endswith("active"):query=query.filter(CRMLead.status.notin_(["Converted","Lost","Disqualified","Archived"]),CRMLead.is_converted.is_(False))
        return q.unique_count(query,CRMLead.id)
    if code in {"crm.deals.open","crm.pipeline.value"}:
        from app.apps.crm.models import CRMDeal
        query=open_deals(db,user)
        return q.unique_count(query,CRMDeal.id) if code.endswith("open") else q.amounts_by_currency(query,CRMDeal.currency,CRMDeal.amount)
    if code=="srm.orders.total":
        from app.apps.srm.access import sales_order_query
        from app.apps.srm.models import SRMSalesOrder
        return q.unique_count(sales_order_query(db,user),SRMSalesOrder.id)
    if code=="srm.invoices.total":
        from app.apps.srm.api.router import authorized_invoice_query
        from app.apps.srm.models import SRMInvoice
        return q.unique_count(authorized_invoice_query(db,user).filter(SRMInvoice.deleted_at.is_(None)),SRMInvoice.id)
    if code=="fam.ledgers.active":
        from app.apps.fam.models import FAMLedger
        return db.query(FAMLedger).filter(FAMLedger.company_id==q.company_id(user),FAMLedger.active.is_(True)).count()
    raise HTTPException(501,"Metric resolver unavailable")
