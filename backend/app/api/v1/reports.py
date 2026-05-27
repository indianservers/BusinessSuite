from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
import csv
import io
from app.core.deps import get_current_user, get_db, RequirePermission
from app.models.user import User
from app.models.employee import Employee, EmployeeChangeRequest
from app.models.attendance import Attendance, AttendanceRegularization, Holiday
from app.models.leave import LeaveRequest, LeaveType
from app.models.helpdesk import HelpdeskTicket
from app.models.document import CompanyPolicy, GeneratedDocument
from app.models.payroll import PayrollRecord, PayrollRun
from app.models.recruitment import Candidate, Job
from app.models.timesheet import Project, Timesheet
from app.models.platform import ReportDefinition, ReportRun
from app.models.asset import AssetAssignment
from app.models.performance import PerformanceGoal, PerformanceReview
from app.schemas.platform import ReportDefinitionCreate, ReportDefinitionSchema, ReportRunSchema

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


REPORT_FIELD_CATALOG = {
    "employees": ["id", "employee_code", "first_name", "last_name", "department_id", "designation_id", "status", "date_of_joining"],
    "attendance": ["employee_id", "attendance_date", "status", "total_hours", "late_minutes", "overtime_hours", "source"],
    "payroll": ["employee_id", "payroll_run_id", "gross_salary", "total_deductions", "net_salary"],
    "recruitment": ["id", "job_id", "first_name", "last_name", "email", "status", "source"],
}


def _distribution(db: Session, field, label: str):
    total = db.query(func.count(Employee.id)).filter(Employee.status == "Active").scalar() or 0
    rows = db.query(field.label(label), func.count(Employee.id).label("count")).filter(
        Employee.status == "Active"
    ).group_by(field).order_by(func.count(Employee.id).desc()).all()
    return [
        {
            label: row[0] or "Not specified",
            "count": row[1],
            "percent": round((row[1] / total * 100) if total else 0, 2),
        }
        for row in rows
    ]


@router.get("/field-catalog")
def report_field_catalog(
    module: Optional[str] = Query(None),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    if module:
        return {"module": module, "fields": REPORT_FIELD_CATALOG.get(module, [])}
    return REPORT_FIELD_CATALOG


@router.post("/definitions", response_model=ReportDefinitionSchema, status_code=201)
def create_report_definition(
    data: ReportDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_manage")),
):
    if data.module not in REPORT_FIELD_CATALOG:
        return_fields = ", ".join(sorted(REPORT_FIELD_CATALOG))
        raise HTTPException(status_code=400, detail=f"Unsupported report module. Choose one of: {return_fields}")
    report = ReportDefinition(**data.model_dump(), created_by=current_user.id)
    if not report.field_catalog_json:
        report.field_catalog_json = REPORT_FIELD_CATALOG[data.module]
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/definitions", response_model=List[ReportDefinitionSchema])
def list_report_definitions(
    module: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(ReportDefinition).filter(ReportDefinition.is_active == True)
    if module:
        query = query.filter(ReportDefinition.module == module)
    return query.order_by(ReportDefinition.name).all()


@router.post("/definitions/{definition_id}/run", response_model=ReportRunSchema, status_code=201)
def run_report_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    definition = db.query(ReportDefinition).filter(ReportDefinition.id == definition_id, ReportDefinition.is_active == True).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Report definition not found")
    row_count = 0
    if definition.module == "employees":
        row_count = db.query(func.count(Employee.id)).scalar() or 0
    elif definition.module == "attendance":
        row_count = db.query(func.count(Attendance.id)).scalar() or 0
    elif definition.module == "payroll":
        row_count = db.query(func.count(PayrollRecord.id)).scalar() or 0
    elif definition.module == "recruitment":
        row_count = db.query(func.count(Candidate.id)).scalar() or 0
    run = ReportRun(
        report_definition_id=definition.id,
        status="Completed",
        row_count=row_count,
        file_url=f"/uploads/reports/{definition.code}.{definition.export_format}",
        requested_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/dashboard")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    total_employees = db.query(func.count(Employee.id)).scalar()
    active_employees = db.query(func.count(Employee.id)).filter(Employee.status == "Active").scalar()
    today = date.today()

    present_today = db.query(func.count(Attendance.id)).filter(
        Attendance.attendance_date == today,
        Attendance.status == "Present",
    ).scalar()

    pending_leaves = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.status == "Pending"
    ).scalar()

    open_positions = db.query(func.count(Job.id)).filter(Job.status == "Open").scalar()
    total_candidates = db.query(func.count(Candidate.id)).scalar()

    return {
        "headcount": {
            "total": total_employees,
            "active": active_employees,
            "on_leave": total_employees - active_employees,
        },
        "attendance": {
            "present_today": present_today,
            "absent_today": active_employees - present_today,
        },
        "leaves": {
            "pending_approvals": pending_leaves,
        },
        "recruitment": {
            "open_positions": open_positions,
            "total_candidates": total_candidates,
        },
    }


@router.get("/manager-dashboard")
def manager_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    employee = current_user.employee
    team_ids = []
    if employee:
        team_ids = [row.id for row in db.query(Employee.id).filter(Employee.reporting_manager_id == employee.id, Employee.deleted_at.is_(None)).all()]
    if not team_ids and (current_user.is_superuser or (current_user.role and current_user.role.name in {"hr_manager", "super_admin"})):
        team_ids = [row.id for row in db.query(Employee.id).filter(Employee.status == "Active", Employee.deleted_at.is_(None)).limit(50).all()]
    today = date.today()
    month_start = today.replace(day=1)
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    pending_leaves = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.status == "Pending",
        LeaveRequest.deleted_at.is_(None),
        LeaveRequest.employee_id.in_(team_ids or [0]),
    ).scalar() or 0
    attendance_rows = db.query(Attendance).filter(
        Attendance.attendance_date == today,
        Attendance.employee_id.in_(team_ids or [0]),
    ).all()
    present_today = sum(1 for row in attendance_rows if row.status == "Present")
    wfh_today = sum(1 for row in attendance_rows if row.status == "WFH")
    on_leave_today = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.status == "Approved",
        LeaveRequest.deleted_at.is_(None),
        LeaveRequest.employee_id.in_(team_ids or [0]),
        LeaveRequest.from_date <= today,
        LeaveRequest.to_date >= today,
    ).scalar() or 0
    pending_regularizations = db.query(func.count(AttendanceRegularization.id)).filter(
        AttendanceRegularization.employee_id.in_(team_ids or [0]),
        AttendanceRegularization.status == "Pending",
    ).scalar() or 0
    pending_change_requests = db.query(func.count(EmployeeChangeRequest.id)).filter(
        EmployeeChangeRequest.employee_id.in_(team_ids or [0]),
        EmployeeChangeRequest.status == "Pending",
    ).scalar() or 0
    open_tickets = db.query(func.count(HelpdeskTicket.id)).filter(
        HelpdeskTicket.employee_id.in_(team_ids or [0]),
        HelpdeskTicket.status.notin_(["Resolved", "Closed"]),
    ).scalar() or 0
    members = db.query(Employee).filter(Employee.id.in_(team_ids or [0]), Employee.deleted_at.is_(None)).limit(50).all()

    leave_rows = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id.in_(team_ids or [0]),
        LeaveRequest.deleted_at.is_(None),
        LeaveRequest.status.in_(["Pending", "Approved"]),
        LeaveRequest.from_date <= month_end,
        LeaveRequest.to_date >= month_start,
    ).all()
    holidays = db.query(Holiday).filter(
        Holiday.is_active == True,
        Holiday.holiday_date >= month_start,
        Holiday.holiday_date <= month_end,
    ).all()
    calendar_days = []
    cursor = month_start
    while cursor <= month_end:
        day_leaves = [
            {
                "employee_id": row.employee_id,
                "status": row.status,
                "from_date": row.from_date.isoformat(),
                "to_date": row.to_date.isoformat(),
                "employee_name": next((f"{m.first_name} {m.last_name}" for m in members if m.id == row.employee_id), None),
            }
            for row in leave_rows if row.from_date <= cursor <= row.to_date
        ]
        calendar_days.append({
            "date": cursor.isoformat(),
            "leave_count": len(day_leaves),
            "leaves": day_leaves,
            "holidays": [{"name": item.name, "type": item.holiday_type} for item in holidays if item.holiday_date == cursor],
        })
        cursor += timedelta(days=1)

    week_end = today + timedelta(days=7)
    moments = {
        "birthdays": [
            {"employee_id": item.id, "name": f"{item.first_name} {item.last_name}", "date": item.date_of_birth.replace(year=today.year).isoformat()}
            for item in members if item.date_of_birth and today <= item.date_of_birth.replace(year=today.year) <= week_end
        ],
        "anniversaries": [
            {"employee_id": item.id, "name": f"{item.first_name} {item.last_name}", "date": item.date_of_joining.replace(year=today.year).isoformat(), "years": today.year - item.date_of_joining.year}
            for item in members if item.date_of_joining and today <= item.date_of_joining.replace(year=today.year) <= week_end
        ],
    }
    return {
        "team_size": len(team_ids),
        "present_today": present_today,
        "wfh_today": wfh_today,
        "on_leave_today": on_leave_today,
        "pending_leave_approvals": pending_leaves,
        "pending_regularizations": pending_regularizations,
        "pending_change_requests": pending_change_requests,
        "open_helpdesk_tickets": open_tickets,
        "calendar_month": month_start.strftime("%B %Y"),
        "team_calendar": calendar_days,
        "moments_this_week": moments,
        "team": [
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "name": f"{item.first_name} {item.last_name}",
                "status": item.status,
                "profile_photo_url": item.profile_photo_url,
            }
            for item in members
        ],
    }


@router.get("/ess-summary")
def ess_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = current_user.employee
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not linked")
    latest_records = (
        db.query(PayrollRecord, PayrollRun)
        .join(PayrollRun, PayrollRun.id == PayrollRecord.payroll_run_id)
        .filter(PayrollRecord.employee_id == employee.id, PayrollRun.deleted_at.is_(None))
        .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
        .limit(12)
        .all()
    )
    documents = db.query(GeneratedDocument).filter(GeneratedDocument.employee_id == employee.id).order_by(GeneratedDocument.created_at.desc()).limit(12).all()
    assets = db.query(AssetAssignment).filter(AssetAssignment.employee_id == employee.id, AssetAssignment.is_active == True).limit(20).all()
    goals = db.query(PerformanceGoal).filter(PerformanceGoal.employee_id == employee.id).order_by(PerformanceGoal.created_at.desc()).limit(10).all()
    reviews = db.query(PerformanceReview).filter(PerformanceReview.employee_id == employee.id).order_by(PerformanceReview.created_at.desc()).limit(5).all()
    return {
        "employee": {"id": employee.id, "employee_id": employee.employee_id, "name": f"{employee.first_name} {employee.last_name}"},
        "payslips": [
            {
                "record_id": record.id,
                "month": run.month,
                "year": run.year,
                "net_salary": record.net_salary,
                "gross_salary": record.gross_salary,
                "pdf_url": record.payslip_pdf_url,
            }
            for record, run in latest_records
        ],
        "documents": [
            {"id": item.id, "document_type": item.document_type, "document_name": item.document_name, "file_url": item.file_url}
            for item in documents
        ],
        "assets": [
            {
                "id": item.id,
                "asset_id": item.asset_id,
                "asset_tag": item.asset.asset_tag if item.asset else None,
                "name": item.asset.name if item.asset else None,
                "assigned_date": item.assigned_date,
                "condition": item.condition_at_assignment,
            }
            for item in assets
        ],
        "goals": [{"id": item.id, "title": item.title, "status": item.status, "target_date": item.target_date} for item in goals],
        "reviews": [{"id": item.id, "cycle_id": item.cycle_id, "review_type": item.review_type, "status": item.status, "overall_rating": item.overall_rating} for item in reviews],
    }


@router.get("/people-moments")
def people_moments(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()

    def in_next_window(value: date | None) -> bool:
        if not value:
            return False
        candidate = value.replace(year=today.year)
        if candidate < today:
            candidate = candidate.replace(year=today.year + 1)
        return today <= candidate <= today + timedelta(days=days)

    employees = db.query(Employee).filter(Employee.status == "Active").all()
    birthdays = [
        {"employee_id": e.id, "name": f"{e.first_name} {e.last_name}", "date": e.date_of_birth.replace(year=today.year).isoformat()}
        for e in employees if in_next_window(e.date_of_birth)
    ]
    anniversaries = [
        {"employee_id": e.id, "name": f"{e.first_name} {e.last_name}", "date": e.date_of_joining.replace(year=today.year).isoformat(), "years": today.year - e.date_of_joining.year}
        for e in employees if in_next_window(e.date_of_joining)
    ]
    return {"days": days, "birthdays": birthdays, "anniversaries": anniversaries}


@router.get("/global-search")
def global_search(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    term = f"%{q.strip()}%"
    employees = db.query(Employee).filter(
        (Employee.first_name.ilike(term)) |
        (Employee.last_name.ilike(term)) |
        (Employee.employee_id.ilike(term)) |
        (Employee.personal_email.ilike(term))
    ).limit(8).all()
    jobs = db.query(Job).filter((Job.title.ilike(term)) | (Job.department.ilike(term))).limit(5).all()
    policies = db.query(CompanyPolicy).filter((CompanyPolicy.title.ilike(term)) | (CompanyPolicy.content.ilike(term))).limit(5).all()
    tickets = db.query(HelpdeskTicket).filter((HelpdeskTicket.ticket_number.ilike(term)) | (HelpdeskTicket.subject.ilike(term))).limit(5).all()
    return {
        "query": q,
        "results": [
            *[{"type": "Employee", "title": f"{e.first_name} {e.last_name}", "subtitle": e.employee_id, "url": f"/employees/{e.id}"} for e in employees],
            *[{"type": "Job", "title": j.title, "subtitle": j.status, "url": "/recruitment"} for j in jobs],
            *[{"type": "Policy", "title": p.title, "subtitle": "Company policy", "url": "/documents"} for p in policies],
            *[{"type": "Ticket", "title": t.subject, "subtitle": t.ticket_number, "url": f"/helpdesk"} for t in tickets],
        ],
    }


@router.get("/headcount-by-department")
def headcount_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    from app.models.company import Department
    result = (
        db.query(Department.name, func.count(Employee.id).label("count"))
        .outerjoin(Employee, Employee.department_id == Department.id)
        .group_by(Department.id, Department.name)
        .all()
    )
    return [{"department": r[0], "count": r[1]} for r in result]


@router.get("/dei-analytics")
def dei_analytics(
    department_id: Optional[int] = Query(None),
    include_pay_equity: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    from app.models.company import Department, GradeBand

    employee_query = db.query(Employee).filter(Employee.status == "Active")
    if department_id:
        employee_query = employee_query.filter(Employee.department_id == department_id)
    employee_ids = [item.id for item in employee_query.all()]
    total = len(employee_ids)

    def scoped_distribution(field, label: str):
        query = db.query(field.label(label), func.count(Employee.id).label("count")).filter(Employee.id.in_(employee_ids))
        rows = query.group_by(field).order_by(func.count(Employee.id).desc()).all() if employee_ids else []
        return [
            {
                label: row[0] or "Not specified",
                "count": row[1],
                "percent": round((row[1] / total * 100) if total else 0, 2),
            }
            for row in rows
        ]

    by_department = (
        db.query(Department.name, func.count(Employee.id).label("count"))
        .join(Employee, Employee.department_id == Department.id)
        .filter(Employee.id.in_(employee_ids))
        .group_by(Department.id, Department.name)
        .order_by(func.count(Employee.id).desc())
        .all()
        if employee_ids else []
    )
    by_grade = (
        db.query(GradeBand.name, func.count(Employee.id).label("count"))
        .join(Employee, Employee.grade_band_id == GradeBand.id)
        .filter(Employee.id.in_(employee_ids))
        .group_by(GradeBand.id, GradeBand.name)
        .order_by(GradeBand.level)
        .all()
        if employee_ids else []
    )

    result = {
        "total_active_headcount": total,
        "gender_identity": scoped_distribution(Employee.gender_identity, "gender_identity"),
        "legal_gender": scoped_distribution(Employee.gender, "gender"),
        "disability_status": scoped_distribution(Employee.disability_status, "disability_status"),
        "veteran_status": scoped_distribution(Employee.veteran_status, "veteran_status"),
        "by_department": [
            {"department": row[0] or "Not specified", "count": row[1], "percent": round((row[1] / total * 100) if total else 0, 2)}
            for row in by_department
        ],
        "by_grade_band": [
            {"grade_band": row[0] or "Not specified", "count": row[1], "percent": round((row[1] / total * 100) if total else 0, 2)}
            for row in by_grade
        ],
    }

    if include_pay_equity:
        latest_records = (
            db.query(PayrollRecord.employee_id, func.max(PayrollRecord.id).label("record_id"))
            .filter(PayrollRecord.employee_id.in_(employee_ids))
            .group_by(PayrollRecord.employee_id)
            .subquery()
        )
        rows = (
            db.query(Employee.gender_identity, func.avg(PayrollRecord.gross_salary).label("avg_gross"), func.count(Employee.id).label("count"))
            .join(latest_records, latest_records.c.employee_id == Employee.id)
            .join(PayrollRecord, PayrollRecord.id == latest_records.c.record_id)
            .group_by(Employee.gender_identity)
            .all()
        ) if employee_ids else []
        result["pay_equity"] = {
            "average_gross_by_gender_identity": [
                {
                    "gender_identity": row[0] or "Not specified",
                    "employee_count": row[2],
                    "average_gross_salary": round(float(row[1] or 0), 2),
                }
                for row in rows
            ],
            "note": "Uses latest payroll record per employee and should be reviewed with role, grade, tenure, and location context.",
        }

    return result


@router.get("/attendance-trend")
def attendance_trend(
    month: int = Query(...),
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    result = (
        db.query(
            Attendance.attendance_date,
            Attendance.status,
            func.count(Attendance.id).label("count"),
        )
        .filter(
            extract("month", Attendance.attendance_date) == month,
            extract("year", Attendance.attendance_date) == year,
        )
        .group_by(Attendance.attendance_date, Attendance.status)
        .order_by(Attendance.attendance_date)
        .all()
    )
    return [{"date": str(r[0]), "status": r[1], "count": r[2]} for r in result]


@router.get("/leave-trend")
def leave_trend(
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    result = (
        db.query(
            extract("month", LeaveRequest.from_date).label("month"),
            func.count(LeaveRequest.id).label("count"),
            LeaveRequest.status,
        )
        .filter(extract("year", LeaveRequest.from_date) == year)
        .group_by("month", LeaveRequest.status)
        .order_by("month")
        .all()
    )
    return [{"month": int(r[0]), "count": r[1], "status": r[2]} for r in result]


@router.get("/payroll-summary")
def payroll_summary(
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    result = (
        db.query(
            PayrollRun.month,
            PayrollRun.total_gross,
            PayrollRun.total_deductions,
            PayrollRun.total_net,
            PayrollRun.status,
        )
        .filter(PayrollRun.year == year)
        .order_by(PayrollRun.month)
        .all()
    )
    return [
        {"month": r[0], "gross": float(r[1] or 0), "deductions": float(r[2] or 0),
         "net": float(r[3] or 0), "status": r[4]}
        for r in result
    ]


@router.get("/employee-turnover")
def turnover_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    resigned = db.query(func.count(Employee.id)).filter(
        Employee.status.in_(["Resigned", "Terminated"]),
        Employee.date_of_exit >= from_date,
        Employee.date_of_exit <= to_date,
    ).scalar()
    joined = db.query(func.count(Employee.id)).filter(
        Employee.date_of_joining >= from_date,
        Employee.date_of_joining <= to_date,
    ).scalar()
    total = db.query(func.count(Employee.id)).filter(Employee.status == "Active").scalar()
    turnover_rate = round((resigned / total * 100) if total > 0 else 0, 2)
    return {
        "period": {"from": str(from_date), "to": str(to_date)},
        "joined": joined,
        "resigned": resigned,
        "turnover_rate": turnover_rate,
        "total_active": total,
    }


@router.get("/recruitment-funnel")
def recruitment_funnel(
    job_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    q = db.query(Candidate.status, func.count(Candidate.id).label("count"))
    if job_id:
        q = q.filter(Candidate.job_id == job_id)
    result = q.group_by(Candidate.status).all()
    return [{"status": r[0], "count": r[1]} for r in result]


@router.get("/project-utilization")
def project_utilization_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    project_id: Optional[int] = Query(None),
    export: Optional[str] = Query(None, pattern="^(csv)?$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = (
        db.query(
            Project.id,
            Project.code,
            Project.name,
            Project.client_name,
            func.coalesce(func.sum(Timesheet.total_hours), 0).label("total_hours"),
            func.coalesce(func.sum(Timesheet.billable_hours), 0).label("billable_hours"),
            func.coalesce(func.sum(Timesheet.non_billable_hours), 0).label("non_billable_hours"),
        )
        .outerjoin(Timesheet, Timesheet.project_id == Project.id)
        .filter((Timesheet.id.is_(None)) | ((Timesheet.period_start <= to_date) & (Timesheet.period_end >= from_date)))
        .group_by(Project.id, Project.code, Project.name, Project.client_name)
    )
    if project_id:
        query = query.filter(Project.id == project_id)
    rows = query.order_by(Project.name).all()
    result = []
    for row in rows:
        total = float(row.total_hours or 0)
        billable = float(row.billable_hours or 0)
        result.append({
            "project_id": row.id,
            "project_code": row.code,
            "project_name": row.name,
            "client_name": row.client_name,
            "total_hours": total,
            "billable_hours": billable,
            "non_billable_hours": float(row.non_billable_hours or 0),
            "billable_utilization_percent": round((billable / total * 100) if total else 0, 2),
        })
    if export == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "project_id",
                "project_code",
                "project_name",
                "client_name",
                "total_hours",
                "billable_hours",
                "non_billable_hours",
                "billable_utilization_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(result)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=project_utilization.csv"},
        )
    return result


@router.get("/monthly-attrition")
def monthly_attrition_report(
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    exits = (
        db.query(extract("month", Employee.date_of_exit).label("month"), func.count(Employee.id).label("count"))
        .filter(Employee.date_of_exit.isnot(None), extract("year", Employee.date_of_exit) == year)
        .group_by("month")
        .order_by("month")
        .all()
    )
    joins = (
        db.query(extract("month", Employee.date_of_joining).label("month"), func.count(Employee.id).label("count"))
        .filter(Employee.date_of_joining.isnot(None), extract("year", Employee.date_of_joining) == year)
        .group_by("month")
        .order_by("month")
        .all()
    )
    exits_by_month = {int(row.month): row.count for row in exits}
    joins_by_month = {int(row.month): row.count for row in joins}
    active = db.query(func.count(Employee.id)).filter(Employee.status == "Active").scalar() or 0
    return [
        {
            "month": month,
            "joiners": joins_by_month.get(month, 0),
            "exits": exits_by_month.get(month, 0),
            "attrition_rate": round((exits_by_month.get(month, 0) / active * 100) if active else 0, 2),
        }
        for month in range(1, 13)
    ]


@router.get("/leave-utilization")
def leave_utilization_summary(
    year: int = Query(...),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = (
        db.query(LeaveType.name, func.coalesce(func.sum(LeaveRequest.days_count), 0).label("used_days"), func.count(LeaveRequest.id).label("requests"))
        .join(LeaveRequest, LeaveRequest.leave_type_id == LeaveType.id)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .filter(LeaveRequest.status == "Approved", LeaveRequest.deleted_at.is_(None), extract("year", LeaveRequest.from_date) == year)
    )
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    rows = query.group_by(LeaveType.id, LeaveType.name).order_by(LeaveType.name).all()
    return [{"leave_type": row.name, "used_days": float(row.used_days or 0), "approved_requests": row.requests} for row in rows]


@router.get("/attendance-summary")
def attendance_summary_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(Attendance.status, func.count(Attendance.id).label("count")).join(Employee, Employee.id == Attendance.employee_id).filter(
        Attendance.attendance_date >= from_date,
        Attendance.attendance_date <= to_date,
    )
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    rows = query.group_by(Attendance.status).all()
    return {"period": {"from": from_date.isoformat(), "to": to_date.isoformat()}, "summary": [{"status": row.status, "count": row.count} for row in rows]}


@router.get("/salary-register")
def salary_register_report(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    rows = (
        db.query(PayrollRecord, PayrollRun, Employee)
        .join(PayrollRun, PayrollRun.id == PayrollRecord.payroll_run_id)
        .join(Employee, Employee.id == PayrollRecord.employee_id)
        .filter(PayrollRun.month == month, PayrollRun.year == year)
        .order_by(Employee.employee_id)
        .all()
    )
    return [
        {
            "employee_id": employee.id,
            "employee_code": employee.employee_id,
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "gross_salary": float(record.gross_salary or 0),
            "total_deductions": float(record.total_deductions or 0),
            "net_salary": float(record.net_salary or 0),
            "pf_employee": float(record.pf_employee or 0),
            "esi_employee": float(record.esi_employee or 0),
            "professional_tax": float(record.professional_tax or 0),
            "tds": float(record.tds or 0),
            "status": record.status,
        }
        for record, _run, employee in rows
    ]


@router.get("/new-joiners-exits")
def new_joiners_exits_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    joiners = db.query(Employee).filter(Employee.date_of_joining >= from_date, Employee.date_of_joining <= to_date).order_by(Employee.date_of_joining).all()
    exits = db.query(Employee).filter(Employee.date_of_exit >= from_date, Employee.date_of_exit <= to_date).order_by(Employee.date_of_exit).all()
    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "joiners": [
            {"employee_id": e.id, "employee_code": e.employee_id, "employee_name": f"{e.first_name} {e.last_name}", "date_of_joining": e.date_of_joining}
            for e in joiners
        ],
        "exits": [
            {"employee_id": e.id, "employee_code": e.employee_id, "employee_name": f"{e.first_name} {e.last_name}", "date_of_exit": e.date_of_exit, "status": e.status}
            for e in exits
        ],
    }
