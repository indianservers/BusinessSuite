from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, exists, select, func, case

from app.models.user import User
from app.models.employee import Employee
from app.models.company import Branch, Department, Company
from app.common.models import CommonPerson
from app.access.models import AccessMembership, AccessPolicy

EMPLOYED = ("Active", "Probation")
COMPLETED = ("Done", "Completed", "Closed", "Resolved")
TERMINAL = (*COMPLETED, "Cancelled", "Canceled", "Rejected")


def company_id(user):
    from app.apps.project_management.access import organization_id_for
    return organization_id_for(user)


def business_context(db, user, now=None):
    company = db.get(Company, company_id(user))
    zone = (company.default_timezone if company else None) or "Asia/Kolkata"
    # Invalid configuration is an error, never silently replaced with UTC.
    instant = now or datetime.now(timezone.utc)
    return {"organization_id": company_id(user), "timezone": zone,
            "as_of": instant.isoformat(), "business_date": instant.astimezone(ZoneInfo(zone)).date().isoformat(),
            "cache_policy": "no-store", "period": "current snapshot"}


def business_day(db=None,user=None):
    if db is not None and user is not None:return datetime.fromisoformat(business_context(db,user)["business_date"]).date()
    from app.core.config import settings
    return datetime.now(ZoneInfo(settings.CELERY_TIMEZONE)).date()


def unique_count(query, identity):
    return query.order_by(None).with_entities(identity).distinct().count()


def count_rows_before_page(query):
    """Keep the caller's authorization, joins, DISTINCT and filters; clear only paging."""
    return query.limit(None).offset(None).order_by(None).count()


def registered_users(db, user, include_invited=False, organization_id=None):
    """One User.id, not one profile, invitation, role, or membership edge."""
    company = organization_id or company_id(user)
    canonical = exists(select(CommonPerson.id).where(CommonPerson.user_id == User.id, CommonPerson.organization_id == company))
    membership = exists(select(AccessMembership.id).where(AccessMembership.user_id == User.id, AccessMembership.company_id == company, AccessMembership.active.is_(True)))
    legacy = exists(select(Employee.id).join(Branch, Branch.id == Employee.branch_id).where(Employee.user_id == User.id, Branch.company_id == company))
    no_person = ~exists(select(CommonPerson.id).where(CommonPerson.user_id == User.id))
    known_branch=exists(select(Employee.id).join(Branch,Branch.id==Employee.branch_id).where(Employee.user_id==User.id))
    legacy_default=and_(no_person,~known_branch,company==1)
    query=db.query(User).filter(or_(canonical, membership, and_(no_person, legacy),legacy_default))
    if not include_invited:
        invitation=exists(select(AccessPolicy.id).where(AccessPolicy.user_id==User.id,AccessPolicy.company_id==company,AccessPolicy.status=="invited"))
        query=query.filter(~invitation)
    return query


def employee_records(db, user=None):
    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if user is None:
        # Compatibility for internal, already-scoped CRUD callers.
        return query
    company = company_id(user)
    branch = exists(select(Branch.id).where(Branch.id == Employee.branch_id, Branch.company_id == company))
    department = exists(select(Department.id).join(Branch, Branch.id == Department.branch_id).where(Department.id == Employee.department_id, Branch.company_id == company))
    account = exists(select(CommonPerson.id).where(CommonPerson.user_id == Employee.user_id, CommonPerson.organization_id == company))
    no_person = ~exists(select(CommonPerson.id).where(CommonPerson.user_id == Employee.user_id))
    unassigned = and_(Employee.branch_id.is_(None), Employee.department_id.is_(None), or_(account, and_(no_person, company == 1)))
    query = query.filter(or_(branch, and_(Employee.branch_id.is_(None), department), unassigned))
    grant = (getattr(user, "_suite_grants", None) or {}).get("hrms", {})
    scope = grant.get("scope", "organization")
    actor = getattr(user, "employee", None)
    if scope in {"own", "self", "assigned"}:
        query = query.filter(Employee.user_id == user.id)
    elif scope == "team":
        query = query.filter(or_(Employee.user_id == user.id, Employee.reporting_manager_id == (actor.id if actor else -1)))
    elif scope in {"department", "branch"}:
        query = query.filter(getattr(Employee, scope + "_id") == (getattr(actor, scope + "_id", None) or -1))
    return query


def employee_counts(db, user=None):
    query = employee_records(db, user)
    rows = dict(query.with_entities(Employee.status, func.count(func.distinct(Employee.id))).group_by(Employee.status).all())
    total = sum(rows.values())
    active = sum(rows.get(status, 0) for status in EMPLOYED)
    return {"total": total, "active": active, "inactive": total-active,
            "on_leave": rows.get("On Leave", 0), "resigned": rows.get("Resigned", 0),
            "probation": rows.get("Probation", 0), "by_status": rows}


def attendance_counts(db,user):
    from app.models.attendance import Attendance
    day=datetime.fromisoformat(business_context(db,user)["business_date"]).date()
    cohort=employee_records(db,user).filter(Employee.status.in_([*EMPLOYED,"On Leave"]))
    latest=db.query(func.max(Attendance.id)).filter(Attendance.employee_id.in_(cohort.with_entities(Employee.id)),Attendance.attendance_date==day).group_by(Attendance.employee_id)
    rows=dict(db.query(Attendance.status,func.count(func.distinct(Attendance.employee_id))).filter(Attendance.id.in_(latest)).group_by(Attendance.status).all())
    present=sum(rows.get(status,0) for status in ["Present","WFH","Half-day"])
    leave=sum(rows.get(status,0) for status in ["On Leave","Leave"])
    total=unique_count(cohort,Employee.id)
    return {"date":day.isoformat(),"present":present,"on_leave":leave,"absent":max(total-present-leave,0),"total_employees":total}


def task_query(db, user, project_id=None, workspace_id=None):
    from app.apps.project_management.access import accessible_project_query, get_project_for_action
    from app.apps.project_management.models import PMSProject, PMSTask
    projects = accessible_project_query(db, user)
    if project_id:
        get_project_for_action(db, project_id, user, "browse")
        projects = projects.filter(PMSProject.id == project_id)
    if workspace_id:
        from app.apps.project_management.people_workspace import workspace_query
        from app.apps.project_management.models import PMSWorkspace
        from fastapi import HTTPException
        if not workspace_query(db,user).filter(PMSWorkspace.id==workspace_id).first():
            raise HTTPException(404,"Workspace outside your permitted scope")
        projects=projects.filter(PMSProject.workspace_id==workspace_id)
    return db.query(PMSTask).filter(PMSTask.deleted_at.is_(None), PMSTask.project_id.in_(projects.with_entities(PMSProject.id)))


def task_counts(db, user, project_id=None, workspace_id=None):
    from app.apps.project_management.models import PMSTask, PMSTaskAssignee
    query = task_query(db,user,project_id,workspace_id)
    today = datetime.fromisoformat(business_context(db,user)["business_date"]).date()
    conditions={"total":None,"completed":PMSTask.status.in_(COMPLETED),"overdue":(PMSTask.due_date<today)&PMSTask.status.notin_(TERMINAL),"due_today":(PMSTask.due_date==today)&PMSTask.status.notin_(TERMINAL),"blocked":PMSTask.status=="Blocked"}
    columns=[func.count(func.distinct(PMSTask.id if condition is None else case((condition,PMSTask.id)))) for condition in conditions.values()]
    result=dict(zip(conditions,query.order_by(None).with_entities(*columns).one()))
    result["assignments"]=db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id.in_(query.with_entities(PMSTask.id)),PMSTaskAssignee.cancelled_at.is_(None)).count()
    return result


def personal_notifications(db,user):
    from app.models.notification import Notification
    return db.query(Notification).filter(Notification.user_id==user.id,or_(Notification.company_id==company_id(user),Notification.company_id.is_(None)))


def amounts_by_currency(query,currency,amount):
    """No exchange rate is assumed. Null/blank currency stays explicitly Unknown."""
    code=func.coalesce(func.nullif(func.upper(func.trim(currency)),""),"Unknown")
    return [{"currency":row[0],"amount":str(row[1] or 0)} for row in query.order_by(None).with_entities(code,func.sum(amount)).group_by(code).order_by(code).all()]
