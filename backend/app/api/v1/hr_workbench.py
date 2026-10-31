"""HR daily work, using existing employee scope, lifecycle and operational records."""
import calendar
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, RequirePermission
from app.core.employee_scope import validate_employee_links
from app.core.masking import user_has_permission, mask_email, mask_phone, can_view_sensitive_employee
from app.models.employee import Employee, EmployeeLifecycleEvent, EmployeeDocument
from app.models.user import User
from app.models.company import Branch
from app.models.audit import AuditLog
from app.models.attendance import Attendance, AttendanceRegularization, Shift
from app.models.leave import LeaveRequest
from app.models.expense import ExpenseClaim
from app.models.timesheet import Timesheet
from app.models.onboarding import EmployeeOnboarding, EmployeeOnboardingTask
from app.models.exit import ExitRecord, ExitChecklistItem
from app.models.asset import AssetAssignment
from app.models.payroll import FullFinalSettlement
from app.models.helpdesk import HelpdeskTicket

router = APIRouter(prefix="/workbench", tags=["HR daily work"])


def business_today():
    from app.api.v1.attendance import _business_date
    return _business_date()


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def permit(user, permission):
    return user_has_permission(user, permission)


def employees(db, user, scope="organization"):
    # The parent /employees router installs tenant scope; central access additionally
    # intersects branch, department and managed grants on this same ORM session.
    from app.services.metrics.queries import employee_records
    query = employee_records(db,user)
    own = user.employee.id if user.employee else None
    if scope == "mine":
        return query.filter(Employee.id == (own or 0))
    if scope == "team":
        return query.filter(Employee.reporting_manager_id == (own or 0))
    if not permit(user, "employee_view"):
        return query.filter(or_(Employee.id == (own or 0), Employee.reporting_manager_id == (own or 0)))
    return query


def employee(db, user, ident, lock=False):
    query = employees(db, user).filter(Employee.id == ident)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, "Employee not found in your permitted scope")
    return row


def summary(row, user):
    sensitive = can_view_sensitive_employee(user, row.id)
    return {"id": row.id, "employee_code": row.employee_id,
            "name": f"{row.first_name} {row.last_name}".strip(), "status": row.status,
            "department": row.department.name if row.department else None,
            "branch": row.branch.name if row.branch else None,
            "company":row.branch.company.name if row.branch and row.branch.company else "Not assigned",
            "department_id": row.department_id, "branch_id": row.branch_id,
            "email": row.work_email or (row.personal_email if sensitive else mask_email(row.personal_email)),
            "phone": row.phone_number if sensitive else mask_phone(row.phone_number)}


def version(row):
    return hashlib.sha256(json.dumps([row.id, str(row.updated_at), row.status, row.user_id,
        row.user.is_active if row.user else None, str(row.user.updated_at) if row.user else None,
        row.branch_id, row.department_id, row.reporting_manager_id], default=str).encode()).hexdigest()


def audit(db, user, ident, action, reason, before=None, after=None):
    db.add(AuditLog(user_id=user.id, actor_email=user.email, actor_authenticated=True,
        method="POST", entity_type="employee", entity_id=ident, module="employees", action=action,
        description=reason, old_values=json.dumps(before, default=str) if before else None,
        new_values=json.dumps(after, default=str) if after else None))


@router.get("/search")
def search(q: str = Query("", max_length=150), scope: Literal["mine", "team", "organization"]="organization",
           db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    query = employees(db, user, scope)
    if q.strip():
        term = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(*[column.ilike(term, escape="\\") for column in
            (Employee.first_name + " " + Employee.last_name, Employee.employee_id,
             Employee.personal_email, Employee.work_email, Employee.phone_number)]))
    return {"items": [summary(row, user) for row in query.order_by(Employee.first_name, Employee.id).limit(50)],
            "scope": scope, "limit": 50}


def approval_counts(db,user,scope):
    visible=employees(db,user,scope)
    own=user.employee.id if user.employee else None
    counts={}
    specs=[("leave",LeaveRequest,["Pending"],"leave_approve","leave_view"),("attendance",AttendanceRegularization,["Pending"],"attendance_manage","attendance_view"),("expense",ExpenseClaim,["submitted","manager_approved"],None,None),("timesheet",Timesheet,["Submitted"],"timesheet_approve","timesheet_view")]
    for kind,model,statuses,decide,view in specs:
        permitted=visible
        if kind=="expense":
            from app.api.v1.expenses import _can_hr_or_finance
            if not _can_hr_or_finance(user):permitted=permitted.filter(or_(Employee.id==(own or -1),Employee.reporting_manager_id==(own or -1)))
        elif not permit(user,view) and not permit(user,decide):permitted=permitted.filter(Employee.id==(own or -1))
        query=db.query(model).filter(model.employee_id.in_(permitted.with_entities(Employee.id)),model.status.in_(statuses))
        if kind=="leave":query=query.filter(LeaveRequest.deleted_at.is_(None))
        counts[kind]=query.count()
    return counts


def approval_items(db, user, scope):
    visible = employees(db, user, scope).order_by(Employee.id).limit(5000).all()
    by_id = {row.id: row for row in visible}
    own = user.employee.id if user.employee else None
    items = []
    specs = [("leave", LeaveRequest, ["Pending"], "leave_approve", "leave_view", "applied_at"),
             ("attendance", AttendanceRegularization, ["Pending"], "attendance_manage", "attendance_view", "created_at"),
             ("expense", ExpenseClaim, ["submitted", "manager_approved"], None, None, "created_at"),
             ("timesheet", Timesheet, ["Submitted"], "timesheet_approve", "timesheet_view", "submitted_at")]
    for kind, model, statuses, decide_permission, view_permission, submitted_field in specs:
        # Own submissions remain visible, while other employees' source records
        # require source-specific permission (or the existing expense manager rule).
        for row in db.query(model).filter(model.employee_id.in_(by_id), model.status.in_(statuses)).order_by(model.id).limit(1001):
            if kind == "leave" and row.deleted_at:
                continue
            person = by_id[row.employee_id]
            is_own = row.employee_id == own
            manager = person.reporting_manager_id == own and own is not None
            if kind == "expense":
                from app.api.v1.expenses import _can_hr_or_finance, _can_finance
                may_view = is_own or manager or _can_hr_or_finance(user)
                may_decide = (_can_finance(user) if row.status == "manager_approved" else manager or _can_hr_or_finance(user))
                stage = "Finance review" if row.status == "manager_approved" else "Manager review"
            else:
                may_view = is_own or permit(user, view_permission) or permit(user, decide_permission)
                may_decide = permit(user, decide_permission)
                stage = "Manager / authorized HR review"
            if not may_view:
                continue
            submitted = aware(getattr(row, submitted_field))
            manager_row = person.reporting_manager
            assignee = "Finance approver" if kind == "expense" and row.status == "manager_approved" else (
                f"{manager_row.first_name} {manager_row.last_name}" if manager_row else "Authorized HR approver; no reporting manager recorded")
            item = {"key": f"{kind}:{row.id}", "kind": kind, "id": row.id, "employee": summary(person, user),
                    "status": row.status, "submitted_at": submitted,
                    "waiting_hours": max(0, int((now()-submitted).total_seconds()/3600)) if submitted else None,
                    "current_approver": assignee, "approval_path": ["Employee submission", stage, "Recorded decision"],
                    "path_source": "Current source workflow; authorized HR approvers may act within scope",
                    "can_decide": bool(may_decide and (not is_own or user.is_superuser)),
                    "restricted_reason": "Self approval is unavailable" if is_own and not user.is_superuser else "Source approval permission is required" if not may_decide else "",
                    "url": f"/hrms/{ {'leave':'leave','attendance':'attendance','expense':'expenses','timesheet':'timesheets'}[kind]}?employee_id={person.id}",
                    "description": str(getattr(row, "reason", None) or getattr(row, "description", None) or "")[:500]}
            item["review_comment"]=getattr(row,"review_remarks",None) or getattr(row,"remarks",None)
            if kind=="expense":item.update(amount=str(row.amount),currency=row.currency,reference=row.claim_number)
            elif kind=="attendance":item.update(requested_check_in=row.requested_check_in,requested_check_out=row.requested_check_out,recorded_check_in=row.attendance.check_in if row.attendance else None,recorded_check_out=row.attendance.check_out if row.attendance else None)
            elif kind=="timesheet":item.update(period_start=row.period_start,period_end=row.period_end,total_hours=str(row.total_hours),entries=[{"date":e.work_date,"task":e.task_name,"hours":str(e.hours)} for e in row.entries[:20]])
            if kind == "leave":
                item.update(from_date=row.from_date, to_date=row.to_date, days=str(row.days_count))
                # Availability is limited to the same permitted employee population.
                colleagues = [e.id for e in visible if e.department_id == person.department_id and e.id != person.id]
                item["team_absences"] = [{"employee": summary(by_id[r.employee_id], user), "from_date": r.from_date, "to_date": r.to_date}
                    for r in db.query(LeaveRequest).filter(LeaveRequest.employee_id.in_(colleagues), LeaveRequest.status=="Approved",
                        LeaveRequest.deleted_at.is_(None), LeaveRequest.from_date<=row.to_date, LeaveRequest.to_date>=row.from_date).limit(30)]
            items.append(item)
    return sorted(items, key=lambda i: (i["submitted_at"] or now(), i["key"]))


@router.get("/approvals")
def approvals(scope: Literal["mine", "team", "organization"]="organization", db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    items=approval_items(db,user,scope)
    counts=approval_counts(db,user,scope);total=sum(counts.values())
    return {"items":items[:1000],"total":total,"truncated":total>len(items[:1000]),"counts":counts,"scope":scope,
        "boundary":"Statistics cover the complete authorized source queries. This inbox previews up to 1,000 requests; open source workspaces for complete worklists."}



class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def meaningful_reason(self):
        if hasattr(self,"reason"):
            self.reason=self.reason.strip()
            if len(self.reason)<3:raise ValueError("Explain this change with at least three characters")
        return self


class Decision(Strict):
    keys: list[str] = Field(min_length=1, max_length=100)
    decision: Literal["approve", "reject", "request_correction"]
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/approvals/decide")
def decide(data: Decision, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if len(data.reason.strip()) < 3:
        raise HTTPException(422, "Explain this decision")
    available = {i["key"]: i for i in approval_items(db, user, "organization")}
    results = []
    for key in dict.fromkeys(data.keys):
        item = available.get(key)
        if not item or not item["can_decide"]:
            results.append({"key": key, "ok": False, "error": "Request changed, is outside scope, or approval permission is unavailable"})
            continue
        try:
            kind, ident = item["kind"], item["id"]
            model = {"leave": LeaveRequest, "attendance": AttendanceRegularization, "expense": ExpenseClaim, "timesheet": Timesheet}[kind]
            row = db.query(model).filter(model.id==ident).with_for_update().first()
            if not row or row.status != item["status"]:
                raise HTTPException(409, "Request changed; refresh before deciding")
            if data.decision == "request_correction":
                # Keep the original request and its balances intact. The requester
                # is notified and the review comment remains in the audit history.
                from app.services.notifications import create_notification
                from app.schemas.notification import NotificationCreate
                person = employee(db, user, row.employee_id)
                if person.user_id:
                    create_notification(db, NotificationCreate(user_id=person.user_id, title="Correction requested",
                        message=data.reason, module="employees", event_type="hr_request_correction",
                        related_entity_type=kind, related_entity_id=ident, action_url=item["url"], channels=["in_app"]))
                field = "remarks" if kind=="expense" else "review_remarks"
                setattr(row, field, data.reason)
                audit(db, user, row.employee_id, "HR_REQUEST_CORRECTION", data.reason, after={"request": key})
                db.commit()
            elif kind == "leave":
                from app.api.v1.leave import approve_leave
                from app.schemas.leave import LeaveApprovalRequest
                approve_leave(ident, LeaveApprovalRequest(status="Approved" if data.decision=="approve" else "Rejected", review_remarks=data.reason), db, user)
            elif kind == "attendance":
                from app.api.v1.attendance import approve_regularization
                from app.schemas.attendance import RegularizationApproval
                approve_regularization(ident, RegularizationApproval(status="Approved" if data.decision=="approve" else "Rejected", review_remarks=data.reason), db, user)
            elif kind == "timesheet":
                from app.api.v1.timesheets import review_timesheet
                from app.schemas.timesheet import TimesheetReview
                review_timesheet(ident, TimesheetReview(status="Approved" if data.decision=="approve" else "Rejected", review_remarks=data.reason), db, user)
            else:
                from app.api.v1.expenses import manager_review_claim, finance_review_claim
                from app.schemas.expense import ExpenseClaimReview
                finance = row.status=="manager_approved"
                status = ("finance_approved" if finance else "manager_approved") if data.decision=="approve" else "rejected"
                (finance_review_claim if finance else manager_review_claim)(ident, ExpenseClaimReview(status=status, remarks=data.reason), db, user)
            results.append({"key": key, "ok": True})
        except HTTPException as exc:
            db.rollback()
            results.append({"key": key, "ok": False, "error": str(exc.detail)})
    return {"results": results, "scope": "Permitted requests; each result is recorded independently"}


@router.get("/home")
def home(scope: Literal["mine", "team", "organization"]="mine", db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    population=employees(db,user,scope);ids=population.with_entities(Employee.id)
    total=population.count();counts=approval_counts(db,user,scope)
    from app.services.metrics.queries import business_day,company_id
    today=business_day(db,user)
    joiner_query=population.filter(Employee.status.notin_(["Terminated","Exited","Resigned"]),Employee.date_of_joining>=today-timedelta(days=7),Employee.date_of_joining<=today+timedelta(days=30))
    joiners=[summary(p,user)|{"joining_date":p.date_of_joining} for p in joiner_query.order_by(Employee.date_of_joining,Employee.id).limit(50)]
    exit_query=db.query(ExitRecord).filter(ExitRecord.employee_id.in_(ids),ExitRecord.status.notin_(["Completed","Cancelled"]))
    exits=exit_query.order_by(ExitRecord.id).limit(50).all() if permit(user,"exit_view") else []
    exit_people={p.id:p for p in population.filter(Employee.id.in_([r.employee_id for r in exits])).all()} if exits else {}
    tickets=db.query(HelpdeskTicket).filter(HelpdeskTicket.employee_id.in_(ids),HelpdeskTicket.status.in_(["Open","In Progress","Pending"])).count() if permit(user,"helpdesk_view") else None
    missing=db.query(Attendance.employee_id).filter(Attendance.employee_id.in_(ids),Attendance.attendance_date==today,or_((Attendance.check_in.isnot(None)) & (Attendance.check_out.is_(None)),(Attendance.check_in.is_(None)) & (Attendance.check_out.isnot(None)))).distinct().count() if permit(user,"attendance_view") or scope=="mine" else None
    return {"scope":scope,"refreshed_at":now(),"employee_count":total,"truncated":False,"can_manage":permit(user,"employee_update"),"can_create":permit(user,"employee_create"),
        "pending_counts":{"approvals":sum(counts.values()),"leave":counts["leave"],"expenses":counts["expense"],"helpdesk":tickets},"joiner_count":joiner_query.count(),"exit_count":exit_query.count() if permit(user,"exit_view") else None,
        "joiners":joiners,"exits":[{"id":r.id,"employee_id":r.employee_id,"employee":summary(exit_people[r.employee_id],user),"status":r.status,"last_working_date":r.last_working_date} for r in exits],"missing_punches":missing,
        "scope_note":f"Organization #{company_id(user)} and current permission restrictions apply. My Team means direct reports. Counts cover complete source queries; joiner and exit previews show up to 50 records."}



@router.get("/attendance-exceptions")
def attendance_exceptions(month: int=Query(ge=1,le=12), year: int=Query(ge=2000,le=2100),
    scope: Literal["mine","team","organization"]="organization", employee_id: int|None=None,
    department_id: int|None=None, branch_id: int|None=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    people = employees(db,user,scope)
    if not permit(user,"attendance_view") and not permit(user,"attendance_manage"):
        people=people.filter(Employee.id==(user.employee.id if user.employee else 0))
    for column,value in ((Employee.id,employee_id),(Employee.department_id,department_id),(Employee.branch_id,branch_id)):
        if value: people=people.filter(column==value)
    by_id={p.id:p for p in people}
    first=date(year,month,1);last=date(year,month,calendar.monthrange(year,month)[1])
    query=db.query(Attendance).outerjoin(Shift,Shift.id==Attendance.shift_id).filter(Attendance.employee_id.in_(by_id),Attendance.attendance_date.between(first,last),
        or_(Attendance.check_in.is_(None),Attendance.check_out.is_(None),Attendance.late_minutes>0,Attendance.status=="Half-day",Attendance.is_short_hours.is_(True),Attendance.total_hours<func.coalesce(Shift.working_hours,8)))
    items=[]
    for row in query.order_by(Attendance.attendance_date.desc(),Attendance.id).limit(1001):
        if row.attendance_date>business_today() or row.status in {"Holiday","Weekend","Weekly Off","On Leave"}:continue
        issues=[]
        shift=db.get(Shift,row.shift_id) if row.shift_id else None
        expected=float(shift.working_hours or 8) if shift else 8
        if bool(row.check_in)!=bool(row.check_out) and (not row.check_in or now()>=aware(row.check_in)+timedelta(hours=expected)):
            issues.append("Missed punch")
        elif not row.check_in and row.status not in {"Absent"}:issues.append("Punches not recorded")
        if row.late_minutes:issues.append(f"Late arrival: {row.late_minutes} minutes")
        if row.check_out and float(row.total_hours or 0)<expected:issues.append("Incomplete shift")
        if row.status=="Absent":issues.append("Absent")
        if not issues:continue
        items.append({"id":row.id,"employee":summary(by_id[row.employee_id],user),"date":row.attendance_date,"status":row.status,
            "issues":issues,"hours":str(row.total_hours or 0),"overtime":str(row.overtime_hours or 0),
            "check_in":row.check_in,"check_out":row.check_out,"expected_hours":expected,
            "can_correct":permit(user,"attendance_manage"),"remarks":row.remarks})
    return {"items":items[:1000],"truncated":len(items)>1000,"month":month,"year":year,"scope":scope,
        "boundary":"Recorded attendance exceptions. Dates without an attendance record require the attendance register; they are not assumed absent."}


@router.get("/people/{ident}")
def person_panel(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=employee(db,user,ident)
    account=row.user
    last=db.query(AuditLog).filter(AuditLog.entity_type=="user",AuditLog.entity_id==row.user_id,
        AuditLog.action.in_(["ACCOUNT_ACTIVATE","ACCOUNT_SUSPEND","ACCOUNT_TERMINATE"])).order_by(AuditLog.id.desc()).first() if account else None
    access_status="Active" if account and account.is_active else "Suspended" if last and last.action=="ACCOUNT_SUSPEND" else "Disabled" if account else "No login account"
    managed=permit(user,"employee_update")
    protected=bool(account and (account.is_superuser or (account.role and account.role.name in {"admin","super_admin"})))
    can_access=managed and bool(account) and (user.is_superuser or not protected) and (not account or account.id!=user.id)
    from app.core.tenant_boundary import company_ids
    from app.apps.srm.services.commercial import tenant
    account_companies=company_ids(db,account) if account else set()
    scope_reason=""
    if account and not user.is_superuser and len(account_companies)>1:
        can_access=False;scope_reason="This login spans organizations; a Super Admin must change its account status"
    elif account and not account.is_active and not user.is_superuser and (not last or last.organization_id!=tenant(user)):
        can_access=False;scope_reason="A Super Admin must reactivate a login disabled outside this HR scope"
    required=[("Work contact",bool(row.work_email or row.personal_email or row.phone_number),"personal"),
        ("Branch and department",bool(row.branch_id and row.department_id),"job"),("Reporting manager",bool(row.reporting_manager_id),"job"),
        ("Bank account and IFSC",bool(row.account_number and row.ifsc_code),"bank"),("Emergency contact",bool(row.emergency_contact_name and row.emergency_contact_number),"personal")]
    history_allowed=managed or bool(user.employee and user.employee.id==ident)
    events=db.query(EmployeeLifecycleEvent).filter(EmployeeLifecycleEvent.employee_id==ident).order_by(EmployeeLifecycleEvent.id.desc()).limit(100).all() if history_allowed else []
    audits=db.query(AuditLog).filter(AuditLog.entity_type=="employee",AuditLog.entity_id==ident).order_by(AuditLog.id.desc()).limit(100).all() if history_allowed else []
    from app.models.audit import FieldAuditEvent
    field_events=db.query(FieldAuditEvent).filter(FieldAuditEvent.employee_id==ident).order_by(FieldAuditEvent.id.desc()).limit(100).all() if history_allowed else []
    return {**summary(row,user),"version":version(row),"employment_status":row.status,"login_status":access_status,
        "user_id":row.user_id,"account_email":account.email if account and (managed or account.id==user.id) else None,
        "scope":{"company":row.branch.company.name if row.branch and row.branch.company else "Not assigned","branch":row.branch.name if row.branch else "Not assigned","department":row.department.name if row.department else "Not assigned"},
        "permissions":{"edit":managed,"access":can_access,"terminate":managed and (user.is_superuser or not protected) and (not account or account.id!=user.id) and (user.is_superuser or len(account_companies)<=1),"exit":permit(user,"exit_manage")},
        "access_reason":scope_reason or ("No linked login account" if not account else "You cannot disable your own login" if account.id==user.id else "Only Super Admin can change protected administrator access" if protected and not user.is_superuser else "Employee update permission is required" if not managed else ""),
        "completion":[{"label":label,"complete":done,"url":f"/hrms/employees/{ident}?tab={tab}"} for label,done,tab in required],
        "timeline":[{"id":f"l{e.id}","action":e.event_type,"at":str(e.created_at),"actor":e.created_by,"reason":e.reason,"from":e.from_status,"to":e.to_status,"effective_from":e.effective_from,"event_id":e.id,"can_apply":managed and e.event_type=="Scheduled transfer" and bool(e.effective_from and e.effective_from<=business_today())} for e in events]+
            [{"id":f"a{a.id}","action":a.action,"at":str(a.created_at),"actor":a.user_id,"reason":a.description} for a in audits]+[{"id":f"f{e.id}","action":f"Changed {e.field_name}","at":str(e.created_at),"actor":e.actor_user_id,"reason":e.reason,"from":e.old_value_masked if e.is_sensitive else e.old_value_plaintext,"to":e.new_value_masked if e.is_sensitive else e.new_value_plaintext} for e in field_events],"timeline_restricted":not history_allowed}


class PersonAction(Strict):
    action: Literal["suspend_access","reactivate_access","terminate_employment","reactivate_employment"]
    version: str
    reason: str=Field(min_length=3,max_length=1000)


class CorrectAttendance(Strict):
    check_in:datetime|None=None
    check_out:datetime|None=None
    break_minutes:int=Field(default=0,ge=0,le=1440)
    reason:str=Field(min_length=3,max_length=1000)


@router.post("/attendance/{ident}/correct")
def correct_attendance(ident:int,data:CorrectAttendance,db:Session=Depends(get_db),user:User=Depends(RequirePermission("attendance_manage"))):
    row=db.query(Attendance).filter(Attendance.id==ident).with_for_update().first()
    if not row:raise HTTPException(404,"Attendance record not found")
    employee(db,user,row.employee_id)
    from app.api.v1.attendance import _locked_month
    if _locked_month(db,row.attendance_date):raise HTTPException(423,"Attendance month is locked; authorized payroll correction is required")
    if not data.check_in or not data.check_out or aware(data.check_out)<=aware(data.check_in):raise HTTPException(422,"Provide check-in and a later check-out")
    elapsed=(aware(data.check_out)-aware(data.check_in)).total_seconds()/3600
    hours=elapsed-data.break_minutes/60
    if elapsed>24 or hours<0:raise HTTPException(422,"A shift cannot exceed 24 hours and breaks cannot exceed elapsed time")
    shift=db.get(Shift,row.shift_id) if row.shift_id else None
    expected=float(shift.working_hours or 8) if shift else 8
    before={"check_in":row.check_in,"check_out":row.check_out,"hours":row.total_hours}
    row.check_in=aware(data.check_in);row.check_out=aware(data.check_out);row.total_hours=round(hours,2)
    row.overtime_hours=round(max(0,hours-expected),2);row.is_regularized=True;row.source="Manual"
    row.short_minutes=round(max(0,expected-hours)*60);row.is_short_hours=hours<expected
    if row.status in {"Absent","Present","Half-day"}:row.status="Present" if hours>=expected else "Half-day"
    if shift:
        from zoneinfo import ZoneInfo
        zone=ZoneInfo(employee(db,user,row.employee_id).timezone or "Asia/Kolkata")
        scheduled=datetime.combine(row.attendance_date,shift.start_time,tzinfo=zone)
        row.late_minutes=max(0,round((aware(data.check_in)-scheduled).total_seconds()/60)-int(shift.grace_minutes or 0))
        row.is_late=row.late_minutes>0
    row.remarks=data.reason;row.computed_at=now()
    audit(db,user,row.employee_id,"ATTENDANCE_CORRECTED",data.reason,before,{"attendance_id":row.id,"check_in":row.check_in,"check_out":row.check_out,"hours":row.total_hours,"break_minutes":data.break_minutes})
    db.commit();return {"message":"Attendance corrected; recorded elapsed hours and overtime recalculated"}


@router.post("/people/{ident}/actions")
def person_action(ident:int,data:PersonAction,db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_update"))):
    row=employee(db,user,ident,True)
    if row.user_id:
        row.user=db.query(User).filter(User.id==row.user_id).populate_existing().with_for_update().first()
    if version(row)!=data.version:raise HTTPException(409,"Employee or account changed; refresh before applying")
    panel=person_panel(ident,db,user)
    permission="terminate" if data.action in {"terminate_employment","reactivate_employment"} else "access"
    if not panel["permissions"][permission]:raise HTTPException(403,panel["access_reason"] or "This action is restricted")
    if len(data.reason.strip())<3:raise HTTPException(422,"Explain this action")
    before={"employment":row.status,"login_active":row.user.is_active if row.user else None}
    if data.action=="reactivate_access" and row.status in {"Terminated","Exited","Resigned"}:
        raise HTTPException(409,"Restore employment through the authorized rehire workflow before reactivating login")
    if data.action=="terminate_employment":
        row.status="Terminated";row.date_of_exit=business_today()
        db.add(EmployeeLifecycleEvent(employee_id=ident,event_type="Termination",event_date=business_today(),effective_from=business_today(),
            from_status=before["employment"],to_status=row.status,reason=data.reason,created_by=user.id))
    elif data.action=="reactivate_employment":
        if row.status not in {"Terminated","Exited","Resigned"}:raise HTTPException(409,"Employment is already active")
        row.status="Active";row.date_of_exit=None
        db.add(EmployeeLifecycleEvent(employee_id=ident,event_type="Employment reactivated",event_date=business_today(),effective_from=business_today(),from_status=before["employment"],to_status=row.status,reason=data.reason,created_by=user.id))
    if row.user and data.action!="reactivate_employment" and (data.action!="terminate_employment" or row.user.is_active or panel["permissions"]["access"] or user.is_superuser):
        from app.api.v1.employee_accounts import revoke
        from app.apps.srm.services.commercial import tenant
        db.info["hr_employee_access_target"]=row.user_id
        row.user.is_active=data.action=="reactivate_access"
        if not row.user.is_active:revoke(db,row.user)
        db.add(AuditLog(user_id=user.id,actor_email=user.email,actor_authenticated=True,method="POST",organization_id=tenant(user),
            entity_type="user",entity_id=row.user_id,action={"suspend_access":"ACCOUNT_SUSPEND","reactivate_access":"ACCOUNT_ACTIVATE","terminate_employment":"ACCOUNT_TERMINATE"}[data.action],description=data.reason))
    audit(db,user,ident,data.action.upper(),data.reason,before,{"employment":row.status,"login_active":row.user.is_active if row.user else None})
    row.updated_at=now()
    try:db.commit()
    finally:db.info.pop("hr_employee_access_target",None)
    return person_panel(ident,db,user)


class QuickEmployee(Strict):
    first_name:str=Field(min_length=1,max_length=160)
    last_name:str=Field(default="",max_length=160)
    date_of_joining:date
    branch_id:int|None=None
    department_id:int|None=None
    personal_email:str|None=None
    phone_number:str|None=None
    phone_number_country_code:str|None=None
    employment_type:str="Full-time"
    existing_user_id:int|None=None


def duplicate_people(db,user,email,phone):
    filters=[]
    if email:filters.extend([func.lower(Employee.personal_email)==email.strip().lower(),func.lower(Employee.work_email)==email.strip().lower(),Employee.user.has(func.lower(User.email)==email.strip().lower())])
    if phone:filters.append(Employee.phone_number==phone.strip())
    return employees(db,user).filter(or_(*filters)).limit(10).all() if filters else []


@router.get("/duplicate-check")
def duplicates(email:str=Query("",max_length=150),phone:str=Query("",max_length=40),db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_create","employee_update"))):
    return {"items":[summary(p,user) for p in duplicate_people(db,user,email,phone)]}


@router.get("/account-options")
def account_options(q:str=Query(min_length=2,max_length=150),db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_create"))):
    from app.common.models import CommonPerson
    from app.apps.srm.services.commercial import tenant
    query=db.query(User).filter(User.is_active.is_(True),User.is_superuser.is_(False),~User.employee.has(),User.email.ilike("%"+q.strip()+"%"))
    if not user.is_superuser:query=query.filter(User.id.in_(db.query(CommonPerson.user_id).filter(CommonPerson.organization_id==tenant(user))))
    return {"items":[{"id":u.id,"email":u.email} for u in query.order_by(User.email).limit(20) if not u.role or u.role.name not in {"admin","super_admin"}]}


@router.post("/quick-add",status_code=201)
def quick_add(data:QuickEmployee,db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_create"))):
    from app.schemas.employee import EmployeeCreate
    from app.core.input_validation import national_phone
    from pydantic import ValidationError
    try:
        values=EmployeeCreate(**data.model_dump(exclude={"existing_user_id"}),create_user_account=False).model_dump(exclude={"employee_id","create_user_account","user_email","user_password"})
    except ValidationError as exc:
        raise HTTPException(422,str(exc)) from None
    if not user.is_superuser and not values.get("branch_id"):
        raise HTTPException(422,"Choose a company branch so the employee remains within your organizational scope")
    validate_employee_links(db,user,values)
    if values.get("phone_number"):
        try:values["phone_number"]=national_phone(values["phone_number"])
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
    if duplicate_people(db,user,values.get("personal_email"),values.get("phone_number")):raise HTTPException(409,"A likely matching employee exists. Review the existing employee before saving")
    account=None
    if data.existing_user_id:
        account=db.query(User).filter(User.id==data.existing_user_id).with_for_update().first()
        options=account_options(account.email if account else "missing",db,user)["items"]
        if not account or not any(i["id"]==account.id for i in options):raise HTTPException(403,"Choose an eligible unlinked account within your organization")
        from app.core.tenant_boundary import company_ids
        from app.apps.srm.services.commercial import tenant
        branch=db.get(Branch,values["branch_id"]) if values.get("branch_id") else None
        account_companies=company_ids(db,account)
        if account_companies and (branch.company_id if branch else tenant(user)) not in account_companies:raise HTTPException(403,"Existing account does not belong to the employee's selected organization")
    row=Employee(**values,employee_id="EMP"+uuid.uuid4().hex[:12].upper(),user_id=account.id if account else None)
    db.add(row);db.flush()
    if account:
        from app.apps.hrms.services.identity import HrmsIdentityService
        HrmsIdentityService.sync_employee_identity(db,row)
    from app.crud.crud_onboarding import auto_start_onboarding_for_employee
    auto_start_onboarding_for_employee(db,row,created_by=user.id)
    audit(db,user,row.id,"QUICK_ADD_EMPLOYEE","Minimal employee profile created",after={"linked_user_id":row.user_id})
    db.commit();return {"id":row.id,"employee_code":row.employee_id,"message":"Employee created; complete the remaining profile checklist"}


@router.get("/people/{ident}/lifecycle-checklist")
def lifecycle_checklist(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=employee(db,user,ident)
    onboarding=db.query(EmployeeOnboarding).filter_by(employee_id=ident).order_by(EmployeeOnboarding.id.desc()).first()
    tasks=db.query(EmployeeOnboardingTask).filter_by(employee_onboarding_id=onboarding.id).order_by(EmployeeOnboardingTask.id).all() if onboarding else []
    record=db.query(ExitRecord).filter_by(employee_id=ident).first() if permit(user,"exit_view") or permit(user,"exit_manage") else None
    exit_tasks=db.query(ExitChecklistItem).filter_by(exit_record_id=record.id).order_by(ExitChecklistItem.id).all() if record else []
    assets=db.query(AssetAssignment).filter_by(employee_id=ident,is_active=True).count() if permit(user,"asset_view") else None
    documents=db.query(EmployeeDocument).filter_by(employee_id=ident).count()
    settlements=db.query(FullFinalSettlement).filter_by(employee_id=ident).order_by(FullFinalSettlement.id.desc()).all() if permit(user,"payroll_view") else []
    from app.api.v1.onboarding import _can_update_task, _can_view_employee_onboarding
    if not (permit(user,"employee_update") or _can_view_employee_onboarding(user,row)):tasks=[]
    return {"employee":summary(row,user),"can_complete_exit":permit(user,"exit_manage"),"onboarding_id":onboarding.id if onboarding else None,
        "joiner":[{"id":f"task:{t.id}","can_complete":permit(user,"employee_update") or _can_update_task(user,t),"label":t.task_name,"category":t.category,"complete":t.status in {"completed","skipped"},"status":t.status,"owner_user_id":t.assigned_to_user_id,"due":t.due_date,"url":f"/hrms/onboarding?employee_id={ident}"} for t in tasks]+
            [{"id":"documents","label":"Employee documents","complete":documents>0,"status":f"{documents} uploaded; verify required documents in the onboarding template","url":f"/hrms/employees/{ident}?tab=documents"},
             {"id":"account","label":"Login account setup","complete":bool(row.user_id and row.user and row.user.is_active),"status":"Active login" if row.user_id and row.user and row.user.is_active else "No active login","url":f"/hrms/employees/{ident}?tab=account"},
             {"id":"assets","label":"Equipment and assets","complete":None,"status":f"{assets} active assignments; confirm required equipment" if assets is not None else "Asset access is restricted","url":f"/hrms/assets?employee_id={ident}"}],
        "exit":{"id":record.id,"status":record.status,"last_working_date":record.last_working_date} if record else None,
        "offboarding":[{"id":t.id,"label":t.task_name,"complete":t.is_completed,"owner_role":t.assigned_to_role,"remarks":t.remarks,"url":f"/hrms/exit?employee_id={ident}"} for t in exit_tasks],
        "dependencies":{"active_assets":assets,"login_active":bool(row.user and row.user.is_active),
            "settlements":[{"id":s.id,"status":s.status,"exit_record_id":s.exit_record_id,"url":f"/hrms/fnf-settlements?employee_id={ident}"} for s in settlements],
            "settlement_restricted":not permit(user,"payroll_view")},"can_start_exit":permit(user,"exit_manage")}


class StartExit(Strict):
    last_working_date:date
    reason:str=Field(min_length=3,max_length=1000)
    exit_type:Literal["Resignation","Termination","Retirement"]="Resignation"


@router.post("/people/{ident}/start-exit",status_code=201)
def start_exit(ident:int,data:StartExit,db:Session=Depends(get_db),user:User=Depends(RequirePermission("exit_manage"))):
    employee(db,user,ident,True)
    if db.query(ExitRecord).filter_by(employee_id=ident).first():raise HTTPException(409,"An exit case already exists; open its existing checklist")
    record=ExitRecord(employee_id=ident,exit_type=data.exit_type,resignation_date=business_today(),last_working_date=data.last_working_date,reason=data.reason,status="Initiated")
    db.add(record);db.flush()
    for label,role in [("Transfer open tasks and project ownership","Manager"),("Revoke login access and active sessions","IT"),
        ("Return company assets and confirm condition","IT"),("Complete exit documents and certificates","HR"),
        ("Review final settlement and outstanding recoveries","Finance")]:
        db.add(ExitChecklistItem(exit_record_id=record.id,task_name=label,assigned_to_role=role))
    audit(db,user,ident,"START_EXIT",data.reason,after={"exit_id":record.id,"last_working_date":data.last_working_date})
    db.commit();return {"id":record.id,"message":"Exit checklist created; employment and login remain unchanged until their separate actions are applied"}


class ChecklistAction(Strict):
    reason:str=Field(min_length=3,max_length=1000)


@router.post("/people/{ident}/offboarding/{item_id}/complete")
def finish_exit_item(ident:int,item_id:int,data:ChecklistAction,db:Session=Depends(get_db),user:User=Depends(RequirePermission("exit_manage"))):
    person=employee(db,user,ident)
    item=db.query(ExitChecklistItem).join(ExitRecord).filter(ExitChecklistItem.id==item_id,ExitRecord.employee_id==ident,ExitRecord.status.notin_(["Completed","Cancelled"])).with_for_update().first()
    if not item:raise HTTPException(404,"Open exit checklist item not found")
    label=item.task_name.lower()
    if "access" in label and person.user and person.user.is_active:raise HTTPException(409,"The linked login is still active; disable access before signing off this item")
    if "asset" in label and db.query(AssetAssignment.id).filter_by(employee_id=ident,is_active=True).first():raise HTTPException(409,"Return assigned assets before signing off asset clearance")
    item.is_completed=True;item.completed_at=now();item.remarks=data.reason
    audit(db,user,ident,"EXIT_CHECKLIST_COMPLETE",data.reason,after={"item_id":item_id,"task":item.task_name})
    db.commit();return {"message":"Checklist evidence recorded"}


@router.post("/people/{ident}/joiner/{item_id}/complete")
def finish_joiner_item(ident:int,item_id:int,data:ChecklistAction,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    employee(db,user,ident)
    task=db.query(EmployeeOnboardingTask).join(EmployeeOnboarding).filter(EmployeeOnboardingTask.id==item_id,EmployeeOnboarding.employee_id==ident).first()
    from app.api.v1.onboarding import _can_update_task
    if not task or not (permit(user,"employee_update") or _can_update_task(user,task)):raise HTTPException(403,"You cannot complete this onboarding task")
    from app.crud.crud_onboarding import mark_task
    audit(db,user,ident,"JOINER_TASK_COMPLETE",data.reason,after={"item_id":item_id})
    mark_task(db,task=task,status="completed",user_id=user.id,notes=data.reason)
    return {"message":"Joiner task completed"}


class ApplyTemplate(Strict):
    template_id:int


@router.get("/onboarding-templates")
def template_options(db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_update","employee_create"))):
    from app.models.onboarding import OnboardingTemplate
    from app.apps.srm.services.commercial import tenant
    query=db.query(OnboardingTemplate).filter(OnboardingTemplate.is_active.is_(True))
    if not user.is_superuser:query=query.filter(or_(OnboardingTemplate.organization_id==tenant(user),(OnboardingTemplate.organization_id.is_(None)) & (tenant(user)==1)))
    return {"items":[{"id":t.id,"name":t.name,"applicable_for":t.applicable_for} for t in query.order_by(OnboardingTemplate.name)]}


@router.post("/people/{ident}/onboarding-template")
def apply_template(ident:int,data:ApplyTemplate,db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_update"))):
    person=employee(db,user,ident)
    options=template_options(db,user)["items"]
    if not any(t["id"]==data.template_id for t in options):raise HTTPException(404,"Eligible onboarding template not found in your organization")
    from app.models.onboarding import OnboardingTemplate
    from app.crud.crud_onboarding import create_employee_onboarding
    template=db.get(OnboardingTemplate,data.template_id)
    onboarding=create_employee_onboarding(db,employee=person,template=template,created_by=user.id,commit=False)
    audit(db,user,ident,"ONBOARDING_TEMPLATE_APPLIED",template.name,after={"template_id":template.id})
    db.commit();return {"id":onboarding.id}


class Transfer(Strict):
    employee_ids:list[int]=Field(min_length=1,max_length=100)
    changes:dict[str,int|None]
    effective_from:date
    reason:str=Field(min_length=3,max_length=1000)
    preview_version:str|None=None


def validate_transfer(db,user,row,changes):
    if not changes or set(changes)-{"branch_id","department_id","designation_id","reporting_manager_id","shift_id"}:
        raise HTTPException(422,"Choose branch, department, designation, reporting manager or shift changes")
    validate_employee_links(db,user,changes,row)
    grant=(getattr(user,"_suite_grants",None) or {}).get("hrms",{})
    for scope,field in (("branch","branch_id"),("department","department_id")):
        if not user.is_superuser and grant.get("scope")==scope and field in changes and changes[field]!=getattr(user.employee,field,None):
            raise HTTPException(403,"Destination is outside your assigned organizational scope")
    if changes.get("shift_id") and not db.query(Shift.id).filter_by(id=changes["shift_id"],is_active=True).first():
        raise HTTPException(422,"Choose an active shift")


def transfer_preview(db,user,data,lock=False):
    items=[];records=[];failures=[]
    for ident in sorted(set(data.employee_ids)):
        try:
            row=employee(db,user,ident,lock)
            validate_transfer(db,user,row,data.changes)
            before={field:getattr(row,field) for field in data.changes}
            records.append(row)
            items.append({"employee":summary(row,user),"before":before,"after":data.changes,"version":version(row)})
        except HTTPException as exc:failures.append({"employee_id":ident,"error":str(exc.detail)})
    stamp=hashlib.sha256(json.dumps({"actor":user.id,"items":items,"changes":data.changes,"date":str(data.effective_from),"reason":data.reason},sort_keys=True,default=str).encode()).hexdigest()
    return records,{"items":items,"failures":failures,"count":len(records),"affected_ids":[r.id for r in records],
        "effective_from":data.effective_from,"scheduled":data.effective_from>business_today(),"version":stamp,
        "scope":"Only the listed permitted employees will change; exceptions remain unchanged"}


@router.post("/transfers/preview")
def preview_transfer(data:Transfer,db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_update"))):
    if data.effective_from<business_today():raise HTTPException(422,"Choose today or a future effective date")
    return transfer_preview(db,user,data)[1]


@router.post("/transfers/apply")
def apply_transfer(data:Transfer,db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_update"))):
    if data.effective_from<business_today():raise HTTPException(422,"Choose today or a future effective date")
    records,preview=transfer_preview(db,user,data,True)
    if preview["version"]!=data.preview_version:raise HTTPException(409,"Employee data or transfer choices changed; review a fresh preview")
    for row in records:
        previous={field:getattr(row,field) for field in data.changes}
        event=EmployeeLifecycleEvent(employee_id=row.id,event_type="Scheduled transfer" if preview["scheduled"] else "Transfer applied",event_date=business_today(),effective_from=data.effective_from,
            from_status=row.status,from_branch_id=row.branch_id,from_department_id=row.department_id,from_designation_id=row.designation_id,from_manager_id=row.reporting_manager_id,
            to_branch_id=data.changes.get("branch_id",row.branch_id),to_department_id=data.changes.get("department_id",row.department_id),
            to_designation_id=data.changes.get("designation_id",row.designation_id),to_manager_id=data.changes.get("reporting_manager_id",row.reporting_manager_id),
            reason=data.reason,remarks=json.dumps({"changes":data.changes,"previous":previous,"state":"scheduled" if preview["scheduled"] else "applied"}),created_by=user.id)
        db.add(event)
        if not preview["scheduled"]:
            from app.core.hr_audit import record_employee_field_changes
            record_employee_field_changes(db,row,data.changes,user.id)
            for field,value in data.changes.items():setattr(row,field,value)
            row.updated_at=now()
        audit(db,user,row.id,"TRANSFER_SCHEDULED" if preview["scheduled"] else "TRANSFER_APPLIED",data.reason,previous,data.changes)
    db.commit()
    return {"message":"Transfer scheduled; apply from the employee timeline on or after its effective date" if preview["scheduled"] else "Transfer applied", "changed":len(records),"failures":preview["failures"]}


@router.post("/people/{ident}/transfers/{event_id}/apply")
def apply_scheduled_transfer(ident:int,event_id:int,db:Session=Depends(get_db),user:User=Depends(RequirePermission("employee_update"))):
    row=employee(db,user,ident,True)
    event=db.query(EmployeeLifecycleEvent).filter_by(id=event_id,employee_id=ident,event_type="Scheduled transfer").with_for_update().first()
    if not event or not event.effective_from or event.effective_from>business_today():raise HTTPException(409,"This transfer is not due or was already applied")
    plan=json.loads(event.remarks or "{}")
    if any(getattr(row,k)!=v for k,v in plan.get("previous",{}).items()):raise HTTPException(409,"Assignments changed since scheduling; review and create a new transfer")
    changes=plan.get("changes",{})
    validate_transfer(db,user,row,changes)
    from app.core.hr_audit import record_employee_field_changes
    record_employee_field_changes(db,row,changes,user.id)
    for key,value in changes.items():setattr(row,key,value)
    row.updated_at=now();event.event_type="Transfer applied";event.remarks=json.dumps({**plan,"state":"applied"})
    audit(db,user,ident,"SCHEDULED_TRANSFER_APPLIED",event.reason,plan.get("previous"),changes)
    db.commit();return {"message":"Due transfer applied; previous assignments retained in history"}


class RosterPlan(Strict):
    shift_id:int
    from_date:date
    to_date:date
    department_id:int|None=None
    employee_ids:list[int]|None=Field(default=None,max_length=200)
    preview_version:str|None=None


def roster_plan(db,user,data,lock=False):
    from app.api.v1 import shift_roster as source
    from app.models.attendance import ShiftRoster,Holiday
    shift=source._load_shift(db,data.shift_id)
    dates=source._date_range(data.from_date,data.to_date)
    people=source._candidate_employees(db,user,data.employee_ids,data.department_id)
    if len(dates)*len(people)>2000:raise HTTPException(422,"Preview at most 2,000 employee-days; narrow the department or date range")
    if lock:db.query(Employee).filter(Employee.id.in_([e.id for e in people])).order_by(Employee.id).with_for_update().all()
    items=[];snapshots=[]
    for person in people:
        current={r.roster_date:r for r in db.query(ShiftRoster).filter(ShiftRoster.employee_id==person.id,ShiftRoster.roster_date.in_(dates))}
        for day in dates:
            existing=current.get(day)
            warnings=source._conflicts(db,person,shift,day,existing)
            blocked=person.status not in {"Active","Probation","On Leave"} or "Employee is on approved leave" in warnings
            if person.status not in {"Active","Probation","On Leave"}:warnings.append(f"Employee employment status is {person.status}")
            if person.user and not person.user.is_active:warnings.append("Login is disabled; confirm work availability separately")
            holidays=db.query(Holiday).filter(Holiday.holiday_date==day,Holiday.is_active.is_(True)).all()
            if any(not h.applicable_branches or str(person.branch_id) in [v.strip() for v in h.applicable_branches.split(",")] for h in holidays):warnings.append("Company holiday on this date")
            snapshots.append([person.id,version(person),str(day),existing.id if existing else None,existing.shift_id if existing else None,existing.status if existing else None,warnings])
            items.append({"employee":summary(person,user),"date":day,"shift":shift.name,"warnings":warnings,"blocked":blocked})
    # Include all proposed days in each week's capacity warning, not just one
    # proposed day against the old roster.
    for person in people:
        for week in {d-timedelta(days=d.weekday()) for d in dates}:
            proposed=[i for i in items if i["employee"]["id"]==person.id and not i["blocked"] and week<=i["date"]<=week+timedelta(days=6)]
            replaced={i["date"] for i in proposed}
            remaining=db.query(ShiftRoster).filter(ShiftRoster.employee_id==person.id,ShiftRoster.roster_date.between(week,week+timedelta(days=6))).all()
            total=sum(float(r.shift.working_hours or 0) for r in remaining if r.roster_date not in replaced and r.shift)+len(proposed)*float(shift.working_hours or 0)
            if total>48:
                for item in proposed:item["warnings"].append(f"Proposed weekly capacity is {total:g} hours (above 48)")
    token=hashlib.sha256(json.dumps([user.id,data.model_dump(exclude={"preview_version"}),str(shift.start_time),str(shift.end_time),str(shift.working_hours),snapshots,items],sort_keys=True,default=str).encode()).hexdigest()
    return people,shift,{"items":items,"affected":sum(not i["blocked"] for i in items),"exceptions":sum(i["blocked"] for i in items),"version":token,"scope":"Listed employees and dates only. Blocked employee-days remain unchanged. Assignments are drafts until published."}


@router.post("/roster/preview")
def preview_roster(data:RosterPlan,db:Session=Depends(get_db),user:User=Depends(RequirePermission("attendance_manage"))):
    return roster_plan(db,user,data)[2]


@router.post("/roster/apply")
def apply_roster(data:RosterPlan,db:Session=Depends(get_db),user:User=Depends(RequirePermission("attendance_manage"))):
    from app.api.v1.shift_roster import _upsert_roster
    people,shift,preview=roster_plan(db,user,data,True)
    if preview["version"]!=data.preview_version:raise HTTPException(409,"Roster, leave or employee data changed; refresh the calendar preview")
    by_id={e.id:e for e in people}
    for item in preview["items"]:
        if item["blocked"]:continue
        _upsert_roster(db,by_id[item["employee"]["id"]],shift,item["date"],"draft",user)
    db.commit();return {"assigned":preview["affected"],"exceptions":[i for i in preview["items"] if i["blocked"]],"message":"Reviewed draft roster saved; blocked days unchanged"}
