"""Independently refreshed, authorized HR dashboard sections. No write side effects."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.access.catalog import permission_names
from app.services.metrics.queries import employee_records, business_context, company_id, EMPLOYED
from app.models.employee import Employee, ProbationReview, EmployeeCertification
from app.models.company import Company, Department, WorkLocation
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest, LeaveBalance
from app.models.payroll import PayrollRun, PayrollRecord, FullFinalSettlement, StatutoryComplianceCalendar
from app.models.onboarding import EmployeeOnboarding, EmployeeOnboardingTask
from app.models.exit import ExitRecord, ExitChecklistItem
from app.models.asset import AssetAssignment
from app.models.document import EmployeeCertificate
from app.models.statutory_compliance import StatutoryComplianceEvent, PayrollLegalEntity

router = APIRouter(prefix="/hrms-dashboard", tags=["HR dashboard"])
SECTIONS = {"workforce": {"employee_view", "reports_view"}, "attendance": {"attendance_view"},
    "leave": {"leave_view", "leave_approve"}, "payroll": {"payroll_view"},
    "onboarding": {"employee_view"}, "probation": {"employee_view"},
    "exits": {"exit_view"}, "compliance": {"employee_view"}}


def personal(user):
    role = user.role.name if user.role else "employee"
    scope = (getattr(user, "_suite_grants", None) or {}).get("hrms", {}).get("scope")
    return not user.is_superuser and (role in {"employee", "intern"} or scope in {"own", "self", "assigned"})


def team_only(user):
    return not user.is_superuser and user.role and user.role.name in {"manager", "team_lead", "department_head"}


def sections_for(user):
    permissions = permission_names(user)
    sections = [key for key, required in SECTIONS.items() if user.is_superuser or required & permissions]
    if personal(user):
        sections = [key for key in sections if key in {"attendance", "leave"}] + ["onboarding", "compliance"]
    if team_only(user):
        sections = [key for key in sections if key != "payroll"]
    return sections


def cohort(db, user, department_id=None, location_id=None, employment_type=None):
    query = employee_records(db, user)
    if personal(user):
        query = query.filter(Employee.user_id == user.id)
    elif team_only(user):
        manager = db.query(Employee.id).filter(Employee.user_id == user.id).scalar()
        query = query.filter(Employee.reporting_manager_id == (manager or -1))
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if location_id:
        query = query.filter(Employee.location_id == location_id)
    if employment_type:
        query = query.filter(Employee.employment_type == employment_type)
    return query


@router.get("/context")
def dashboard_context(response: Response, db: Session = Depends(get_db), user=Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    ctx = business_context(db, user)
    company = db.get(Company, company_id(user))
    employees = cohort(db, user)
    ids = employees.with_entities(Employee.department_id)
    departments = db.query(Department).filter(Department.id.in_(ids)).order_by(Department.name).all()
    locations = db.query(WorkLocation).filter(WorkLocation.company_id == company_id(user), WorkLocation.id.in_(employees.with_entities(Employee.location_id))).order_by(WorkLocation.name).all()
    permissions = permission_names(user)
    return {**ctx, "currency": company.default_currency or "INR", "sections": sections_for(user),
        "scope": "My records" if personal(user) else "My direct reports" if team_only(user) else "Permitted workforce",
        "personal": personal(user), "permissions": sorted(permissions), "superuser": user.is_superuser,
        "departments": [{"id": row.id, "name": row.name} for row in departments],
        "locations": [{"id": row.id, "name": row.name} for row in locations],
        "employment_types": [row[0] for row in employees.with_entities(Employee.employment_type).distinct().all() if row[0]]}


def item(identity, employee, detail, when=None, status=None, href=None):
    return {"id": str(identity), "employee_id": employee.id if employee else None,
        "name": f"{employee.first_name} {employee.last_name}" if employee else "Company",
        "detail": detail, "date": when.isoformat() if when else None, "status": status,
        "href": href or (f"/hrms/employees/{employee.id}" if employee else "/hrms/statutory-compliance")}


@router.get("/{section}")
def dashboard_section(section: Literal["workforce", "attendance", "leave", "payroll", "onboarding", "probation", "exits", "compliance"],
    response: Response, from_date: date | None = None, to_date: date | None = None,
    department_id: int | None = Query(None, ge=1), location_id: int | None = Query(None, ge=1),
    employment_type: str | None = Query(None, max_length=80),
    record_status: str | None = Query(None, max_length=80), record_date: date | None = None,
    db: Session = Depends(get_db), user=Depends(get_current_user)):
    if section not in sections_for(user):
        raise HTTPException(403, "This dashboard section is outside your permissions")
    response.headers["Cache-Control"] = "no-store"
    ctx = business_context(db, user)
    today = date.fromisoformat(ctx["business_date"])
    end = to_date or today
    start = from_date or end - timedelta(days=29)
    if start > end or (end-start).days > 365:
        raise HTTPException(422, "Choose an ordered reporting period of at most 366 days")
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - (end-start)
    employees = cohort(db, user, department_id, location_id, employment_type).all()
    people = {row.id: row for row in employees}
    ids = list(people)
    active = [e for e in employees if e.status in EMPLOYED and e.date_of_joining <= today]
    rows, metrics, series, notes = [], {}, [], []
    if section == "workforce":
        def employed_on(day):
            return sum(e.date_of_joining <= day and (e.date_of_exit is None or e.date_of_exit > day) for e in employees)
        metrics = {"total": len(employees), "active": len(active), "headcount": employed_on(end),
            "previous_headcount": employed_on(prior_end), "joined": sum(start <= e.date_of_joining <= end for e in employees)}
        groups = Counter(e.department.name if e.department else "Unassigned" for e in active)
        series = [{"department": key, "count": count} for key, count in sorted(groups.items())]
        rows = [item(e.id, e, e.employment_type or "Employment type unspecified", e.date_of_joining, e.status) for e in employees]
        notes = ["Active means Active or Probation. Includes people without login accounts.", "Historical headcount uses recorded joining and exit dates; it does not reconstruct historical status changes."]
    elif section == "attendance":
        week_start = today - timedelta(days=today.weekday())
        latest = db.query(func.max(Attendance.id)).filter(Attendance.employee_id.in_(ids), Attendance.attendance_date.between(min(start, week_start), max(end, today))).group_by(Attendance.employee_id, Attendance.attendance_date)
        records = db.query(Attendance).filter(Attendance.id.in_(latest)).all()
        daily = [r for r in records if r.attendance_date == today]
        period = [r for r in records if start <= r.attendance_date <= end]
        counts = Counter(r.status for r in daily)
        eligible = [r for r in period if r.status in {"Present", "WFH", "Half-day", "Absent"}]
        present_equivalent = sum(.5 if r.status == "Half-day" else 1 if r.status in {"Present", "WFH"} else 0 for r in eligible)
        metrics = {"present": counts["Present"], "wfh": counts["WFH"], "absent": counts["Absent"],
            "on_leave": counts["On Leave"] + counts["Leave"], "not_marked": max(len(active)-len(daily),0),
            "rate": round(100*present_equivalent/len(eligible),1) if eligible else None,
            "denominator": len(eligible), "present_equivalent": present_equivalent,
            "week_days": len({r.attendance_date for r in records if week_start <= r.attendance_date <= today and r.status in {"Present", "WFH", "Half-day"}}),
            "week_hours": float(sum((r.total_hours or 0) for r in records if week_start <= r.attendance_date <= today)),
            "missing_punches": sum(bool(r.check_in) != bool(r.check_out) for r in daily)}
        series = [{"status": status, "count": count} for status, count in sorted(counts.items())]
        rows = [item(r.id, people[r.employee_id], r.status, r.attendance_date, r.status) for r in records if start <= r.attendance_date <= end or r.attendance_date == today]
        notes = ["Rate = (Present + WFH + 0.5 × Half-day) / recorded working-day entries. Leave, holidays, weekends and unmarked days are excluded. Shift schedules are not inferred.", f"Today uses {ctx['timezone']}. Latest record per employee/day; missing punch count includes incomplete pairs only."]
    elif section == "leave":
        pending = db.query(LeaveRequest).filter(LeaveRequest.employee_id.in_(ids), LeaveRequest.deleted_at.is_(None), LeaveRequest.status == "Pending").order_by(LeaveRequest.applied_at).all()
        balances = db.query(LeaveBalance).filter(LeaveBalance.employee_id.in_(ids), LeaveBalance.year == today.year).all()
        available = sum(max(Decimal(0), (b.allocated or 0)+(b.carried_forward or 0)-(b.used or 0)-(b.pending or 0)) for b in balances)
        def applied_day(instant):
            instant = instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant
            return instant.astimezone(ZoneInfo(ctx["timezone"])).date()
        metrics = {"pending": len(pending), "available_days": float(available), "oldest_days": max([max(0,(today-applied_day(r.applied_at)).days) for r in pending if r.applied_at] or [0]),
            "starting_soon": sum(today <= r.from_date <= today+timedelta(days=3) for r in pending)}
        rows = [{**item(r.id, people[r.employee_id], f"Requested {applied_day(r.applied_at) if r.applied_at else 'date unavailable'}; leave {r.from_date} to {r.to_date}", r.from_date, r.status, "/hrms/leave"), "requested_date": applied_day(r.applied_at).isoformat() if r.applied_at else "9999"} for r in pending]
        horizon = today+timedelta(days=7)
        approved = db.query(LeaveRequest).filter(LeaveRequest.employee_id.in_(ids), LeaveRequest.deleted_at.is_(None), LeaveRequest.status == "Approved", LeaveRequest.from_date <= horizon, LeaveRequest.to_date >= today).all()
        series = [{"date": (today+timedelta(days=i)).isoformat(), "on_leave": len({r.employee_id for r in approved if r.from_date <= today+timedelta(days=i) <= r.to_date}), "without_handover": sum(not r.handover_employee_id for r in approved if r.from_date <= today+timedelta(days=i) <= r.to_date)} for i in range(8)]
        notes = [f"{'Personal' if personal(user) else 'Permitted workforce'} available leave days for {today.year}; not a monetary liability. Allocated + carried forward − used − pending, floored at zero per balance.", "Approval queue is current regardless of reporting period. Coverage gaps identify approved requests without a recorded handover; staffing requirements are not inferred."]
    elif section == "payroll":
        # Company and employee scope are both explicit, including for Super Admin.
        runs = db.query(PayrollRun).filter(PayrollRun.company_id == company_id(user), PayrollRun.deleted_at.is_(None)).order_by(PayrollRun.year.desc(), PayrollRun.month.desc(), PayrollRun.id.desc()).all()
        completed = {r.id:r for r in runs if (r.status or "").lower() in {"approved", "locked", "paid"}}
        all_records = db.query(PayrollRecord).filter(PayrollRecord.employee_id.in_(ids), PayrollRecord.payroll_run_id.in_([run.id for run in runs])).all()
        records = [record for record in all_records if record.payroll_run_id in completed]
        def total(a,b):
            selected = [r for r in records if a <= date(completed[r.payroll_run_id].year, completed[r.payroll_run_id].month, 1) <= b]
            return float(sum(r.net_salary or 0 for r in selected))
        grouped = {}
        for r in records:
            run = completed[r.payroll_run_id]; day = date(run.year,run.month,1)
            if start <= day <= end:
                values = grouped.setdefault(day.isoformat(), {"month": day.isoformat(), "gross": 0., "net": 0.})
                values["gross"] += float(r.gross_salary or 0); values["net"] += float(r.net_salary or 0)
        series = list(sorted(grouped.values(), key=lambda r:r["month"]))
        latest = next((run for run in runs if any(r.payroll_run_id == run.id for r in all_records)), None)
        metrics = {"net": total(start,end), "previous_net": total(prior_start,prior_end), "latest_run": latest.id if latest else None, "status": latest.status if latest else "No scoped run", "issue_count": 0}
        if latest:
            for r in all_records:
                if r.payroll_run_id != latest.id: continue
                e=people[r.employee_id]
                missing=[label for label,value in [("Bank name",e.bank_name),("Account number",e.account_number),("IFSC",e.ifsc_code)] if not value]
                issues = (["Missing bank details: " + ", ".join(missing)] if missing else []) + (["Negative net pay"] if (r.net_salary or 0)<0 else [])
                for i, message in enumerate(issues): rows.append(item(f"{r.id}-{i}",e,message,None,"Blocked"))
            metrics["issue_count"]=len(rows)
        notes=["Approved, locked and paid runs only. Payroll months are included by their first calendar day; totals use scoped employee records, not company run totals.", "Bank checks cover the latest run with scoped employee records, including draft calculations. No scoped run means readiness has not been validated. Approval and locking are separate controls."]
    elif section == "onboarding":
        tasks=db.query(EmployeeOnboardingTask,EmployeeOnboarding.employee_id).join(EmployeeOnboarding,EmployeeOnboarding.id==EmployeeOnboardingTask.employee_onboarding_id).filter(EmployeeOnboarding.employee_id.in_(ids), EmployeeOnboarding.status.notin_(["completed","cancelled"]),EmployeeOnboardingTask.status.notin_(["completed","cancelled"]), EmployeeOnboardingTask.due_date <= today+timedelta(days=30)).order_by(EmployeeOnboardingTask.due_date).all()
        rows=[item(t.id,people[eid],f"{t.category}: {t.task_name}",t.due_date,"Overdue" if t.due_date<today else "Upcoming", "/hrms/onboarding") for t,eid in tasks]
        metrics={"overdue":sum(r["status"]=="Overdue" for r in rows),"upcoming":sum(r["status"]=="Upcoming" for r in rows)}
        notes=["Open onboarding tasks due within 30 days, including overdue joining, document and equipment tasks."]
    elif section == "probation":
        rows=[item(f"confirmation-{e.id}",e,"Confirmation decision",e.probation_end_date,"Overdue" if e.probation_end_date<today else "Upcoming","/hrms/probation") for e in active if e.probation_end_date and e.probation_end_date<=today+timedelta(days=30) and not e.date_of_confirmation and e.probation_status not in {"confirmed","terminated"}]
        reviews=db.query(ProbationReview).filter(ProbationReview.employee_id.in_(ids),ProbationReview.status=="pending",ProbationReview.review_date<=today+timedelta(days=30)).all()
        rows += [item(f"review-{r.id}",people[r.employee_id],"Probation review",r.review_date,"Overdue" if r.review_date<today else "Upcoming","/hrms/probation") for r in reviews]
        metrics={"overdue":sum(r["status"]=="Overdue" for r in rows),"upcoming":sum(r["status"]=="Upcoming" for r in rows)}
    elif section == "exits":
        exits=db.query(ExitRecord).filter(ExitRecord.employee_id.in_(ids),ExitRecord.status.notin_(["Completed","Cancelled"])).all()
        for ex in exits:
            tasks=db.query(ExitChecklistItem).filter_by(exit_record_id=ex.id,is_completed=False).count()
            assets=db.query(AssetAssignment).filter_by(employee_id=ex.employee_id,returned_date=None).count()
            settlement=db.query(FullFinalSettlement).filter_by(employee_id=ex.employee_id).order_by(FullFinalSettlement.id.desc()).first()
            settled=bool(settlement and (settlement.status or "").lower() in {"paid","completed","settled"})
            rows.append(item(ex.id,people[ex.employee_id],f"{tasks} handover/checklist tasks; {assets} assets unreturned; settlement {'complete' if settled else 'pending'}",ex.last_working_date,"Blocked" if tasks or assets or not settled else "Ready","/hrms/exit"))
        metrics={"open":len(exits),"blocked":sum(r["status"]=="Blocked" for r in rows)}
    elif section == "compliance":
        certs=db.query(EmployeeCertificate).filter(EmployeeCertificate.employee_id.in_(ids),EmployeeCertificate.expiry_date<=today+timedelta(days=30)).all()
        rows=[item(f"certificate-{c.id}",people[c.employee_id],c.title,c.expiry_date,"Expired" if c.expiry_date<today else "Expiring","/hrms/documents") for c in certs]
        qualifications=db.query(EmployeeCertification).filter(EmployeeCertification.employee_id.in_(ids),EmployeeCertification.expiry_date<=today+timedelta(days=30)).all()
        rows += [item(f"qualification-{c.id}",people[c.employee_id],c.certification_name,c.expiry_date,"Expired" if c.expiry_date<today else "Expiring") for c in qualifications]
        if (user.is_superuser or "payroll_run" in permission_names(user)) and not personal(user) and not team_only(user) and not any([department_id,location_id,employment_type]):
            deadlines=db.query(StatutoryComplianceCalendar).filter(StatutoryComplianceCalendar.company_id==company_id(user),StatutoryComplianceCalendar.due_date<=today+timedelta(days=30),StatutoryComplianceCalendar.status.notin_(["Filed","Completed","Cancelled"])).all()
            rows += [item(f"filing-{d.id}",None,d.description or d.statutory_type,d.due_date,"Overdue" if d.due_date<today else "Upcoming","/hrms/statutory-compliance") for d in deadlines]
        # Assigned tasks are private to their owner; organizational tasks require
        # payroll administration and are omitted when employee filters are active.
        events=db.query(StatutoryComplianceEvent).filter(
            StatutoryComplianceEvent.legal_entity_id.in_(db.query(PayrollLegalEntity.id).filter(PayrollLegalEntity.company_id==company_id(user))),
            StatutoryComplianceEvent.due_date<=today+timedelta(days=30),
            StatutoryComplianceEvent.completed_at.is_(None),
            StatutoryComplianceEvent.status.notin_(["Completed","Cancelled","Filed"]))
        if not (user.is_superuser or "payroll_run" in permission_names(user)) or personal(user) or team_only(user):
            events=events.filter(StatutoryComplianceEvent.owner_user_id==user.id)
        if not any([department_id,location_id,employment_type]):
            rows += [item(f"task-{event.id}",None,f"{event.compliance_type} filing task · {'Assigned to you' if event.owner_user_id==user.id else 'Company compliance'}",event.due_date,"Overdue" if event.due_date<today else "Upcoming","/hrms/statutory-compliance") for event in events.all()]
        metrics={"overdue":sum(r["status"] in {"Expired","Overdue"} for r in rows),"upcoming":sum(r["status"] not in {"Expired","Overdue"} for r in rows)}
        notes=["Document expiries within 30 days, including expired documents. Assigned filing tasks are owner-scoped; company tasks require payroll administration. Filing tasks are omitted with workforce filters."]
    if record_status:
        rows = [r for r in rows if r["status"] == record_status]
    if record_date:
        rows = [r for r in rows if r["date"] == record_date.isoformat()]
    rows.sort(key=lambda r:(r.get("requested_date",r["date"]) or "9999",r["id"]))
    return {"section":section,"context":{**ctx,"from_date":start,"to_date":end,"previous_from":prior_start,"previous_to":prior_end},"metrics":metrics,"series":series,"rows":rows[:250],"total_rows":len(rows),"notes":notes}
