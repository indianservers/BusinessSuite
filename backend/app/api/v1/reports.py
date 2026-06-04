from typing import List, Optional
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import case, func, extract
import csv
import io
from app.core.deps import get_current_user, get_db, RequirePermission
from app.models.user import User
from app.models.employee import Employee, EmployeeChangeRequest
from app.models.attendance import Attendance, AttendanceRegularization, Holiday
from app.models.leave import LeaveRequest, LeaveType, LeaveBalance
from app.models.helpdesk import HelpdeskTicket
from app.models.document import CompanyPolicy, GeneratedDocument
from app.models.payroll import PayrollRecord, PayrollRun, Reimbursement, EmployeeLoan, FullFinalSettlement
from app.models.audit import AuditLog
from app.models.recruitment import Candidate, Job
from app.models.timesheet import Project, Timesheet
from app.models.platform import MetricDefinition, ReportDefinition, ReportRun, ReportSchedule
from app.models.asset import AssetAssignment
from app.models.performance import OneOnOneRecord, PerformanceGoal, PerformanceReview
from app.schemas.platform import ReportDefinitionCreate, ReportDefinitionSchema, ReportRunSchema, ReportScheduleCreate, ReportScheduleSchema

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


GOVERNED_HR_METRICS = [
    {
        "code": "pay_equity",
        "name": "Pay Equity",
        "module": "hr_analytics",
        "owner_role": "HR Analytics",
        "formula_json": {
            "description": "Compares average latest gross pay by protected/person attributes with contextual drilldowns.",
            "inputs": ["latest_payroll_record", "gender_identity", "grade_band_id", "department_id", "location_id"],
        },
    },
    {
        "code": "span_of_control",
        "name": "Span of Control",
        "module": "hr_analytics",
        "owner_role": "HR Business Partner",
        "formula_json": {"description": "Direct active reportees per manager."},
    },
    {
        "code": "manager_effectiveness",
        "name": "Manager Effectiveness",
        "module": "hr_analytics",
        "owner_role": "HR Business Partner",
        "formula_json": {"description": "Composite of team attrition, goal completion, review completion, and 1:1 cadence."},
    },
    {
        "code": "attrition_trend",
        "name": "Attrition Trend",
        "module": "hr_analytics",
        "owner_role": "HR Analytics",
        "formula_json": {"description": "Exited employees divided by average active headcount for the period."},
    },
    {
        "code": "absenteeism",
        "name": "Absenteeism",
        "module": "hr_analytics",
        "owner_role": "HR Operations",
        "formula_json": {"description": "Absent attendance records as a percentage of attendance records."},
    },
    {
        "code": "dei_representation",
        "name": "DE&I Representation",
        "module": "hr_analytics",
        "owner_role": "DEI Lead",
        "formula_json": {"description": "Representation mix across gender identity, disability, veteran status, department, and grade."},
    },
]


def _ensure_governed_metrics(db: Session) -> None:
    existing = {row.code for row in db.query(MetricDefinition).filter(MetricDefinition.code.in_([m["code"] for m in GOVERNED_HR_METRICS])).all()}
    for metric in GOVERNED_HR_METRICS:
        if metric["code"] not in existing:
            db.add(MetricDefinition(refresh_frequency="Daily", is_active=True, **metric))
    db.flush()


def _employee_scope(
    db: Session,
    *,
    department_id: int | None = None,
    grade_band_id: int | None = None,
    location_id: int | None = None,
    employment_type: str | None = None,
    tenure_band: str | None = None,
):
    query = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.status == "Active")
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if grade_band_id:
        query = query.filter(Employee.grade_band_id == grade_band_id)
    if location_id:
        query = query.filter(Employee.location_id == location_id)
    if employment_type:
        query = query.filter(Employee.employment_type == employment_type)
    today = date.today()
    if tenure_band:
        if tenure_band == "0-1":
            query = query.filter(Employee.date_of_joining >= today - timedelta(days=365))
        elif tenure_band == "1-3":
            query = query.filter(Employee.date_of_joining < today - timedelta(days=365), Employee.date_of_joining >= today - timedelta(days=365 * 3))
        elif tenure_band == "3-5":
            query = query.filter(Employee.date_of_joining < today - timedelta(days=365 * 3), Employee.date_of_joining >= today - timedelta(days=365 * 5))
        elif tenure_band == "5+":
            query = query.filter(Employee.date_of_joining < today - timedelta(days=365 * 5))
    return query


def _metric_filters(**kwargs) -> dict:
    return {key: value for key, value in kwargs.items() if value not in (None, "")}


def _latest_payroll_subquery(db: Session, employee_ids: list[int]):
    return (
        db.query(PayrollRecord.employee_id, func.max(PayrollRecord.id).label("record_id"))
        .filter(PayrollRecord.employee_id.in_(employee_ids or [0]))
        .group_by(PayrollRecord.employee_id)
        .subquery()
    )


def _run_report_rows(db: Session, definition: ReportDefinition) -> tuple[list[str], list[dict]]:
    fields = definition.selected_fields_json or REPORT_FIELD_CATALOG.get(definition.module, [])
    limit = 500
    rows: list[dict] = []
    if definition.module == "employees":
        for employee in db.query(Employee).filter(Employee.deleted_at.is_(None)).limit(limit).all():
            source = {
                "id": employee.id,
                "employee_code": employee.employee_id,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "department_id": employee.department_id,
                "designation_id": employee.designation_id,
                "status": employee.status,
                "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
            }
            rows.append({field: source.get(field) for field in fields})
    elif definition.module == "attendance":
        for item in db.query(Attendance).limit(limit).all():
            source = {
                "employee_id": item.employee_id,
                "attendance_date": item.attendance_date.isoformat() if item.attendance_date else None,
                "status": item.status,
                "total_hours": float(item.total_hours or 0),
                "late_minutes": item.late_minutes,
                "overtime_hours": float(item.overtime_hours or 0),
                "source": item.source,
            }
            rows.append({field: source.get(field) for field in fields})
    elif definition.module == "payroll":
        for item in db.query(PayrollRecord).limit(limit).all():
            source = {
                "employee_id": item.employee_id,
                "payroll_run_id": item.payroll_run_id,
                "gross_salary": float(item.gross_salary or 0),
                "total_deductions": float(item.total_deductions or 0),
                "net_salary": float(item.net_salary or 0),
            }
            rows.append({field: source.get(field) for field in fields})
    elif definition.module == "recruitment":
        for item in db.query(Candidate).limit(limit).all():
            source = {
                "id": item.id,
                "job_id": item.job_id,
                "first_name": item.first_name,
                "last_name": item.last_name,
                "email": item.email,
                "status": item.status,
                "source": item.source,
            }
            rows.append({field: source.get(field) for field in fields})
    return fields, rows


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


@router.get("/definitions/{definition_id}/run")
def preview_report_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    definition = db.query(ReportDefinition).filter(ReportDefinition.id == definition_id, ReportDefinition.is_active == True).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Report definition not found")
    columns, rows = _run_report_rows(db, definition)
    return {"definition_id": definition.id, "columns": columns, "rows": rows, "row_count": len(rows)}


@router.post("/schedules", response_model=ReportScheduleSchema, status_code=201)
def create_report_schedule(
    data: ReportScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_manage")),
):
    definition = db.query(ReportDefinition).filter(ReportDefinition.id == data.report_definition_id, ReportDefinition.is_active == True).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Report definition not found")
    item = ReportSchedule(**data.model_dump(), created_by=current_user.id)
    definition.schedule_cron = data.cron_expression
    definition.export_format = data.export_format
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/schedules", response_model=List[ReportScheduleSchema])
def list_report_schedules(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(ReportSchedule)
    if status:
        query = query.filter(ReportSchedule.status == status)
    return query.order_by(ReportSchedule.created_at.desc(), ReportSchedule.id.desc()).limit(200).all()


@router.post("/schedules/{schedule_id}/run", response_model=ReportRunSchema)
def run_report_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    definition = db.query(ReportDefinition).filter(ReportDefinition.id == schedule.report_definition_id).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Report definition not found")
    _, rows = _run_report_rows(db, definition)
    run = ReportRun(
        report_definition_id=definition.id,
        status="Completed",
        row_count=len(rows),
        file_url=f"/uploads/reports/{definition.code}.{schedule.export_format}",
        requested_by=current_user.id,
    )
    schedule.last_run_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/analytics/metric-definitions")
def governed_metric_definitions(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    _ensure_governed_metrics(db)
    db.commit()
    rows = db.query(MetricDefinition).filter(MetricDefinition.module == "hr_analytics", MetricDefinition.is_active == True).order_by(MetricDefinition.name).all()
    return [
        {
            "code": row.code,
            "name": row.name,
            "module": row.module,
            "formula_json": row.formula_json,
            "owner_role": row.owner_role,
            "refresh_frequency": row.refresh_frequency,
        }
        for row in rows
    ]


@router.get("/analytics/drilldown")
def analytics_drilldown(
    metric: str = Query(...),
    department_id: Optional[int] = Query(None),
    grade_band_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    employment_type: Optional[str] = Query(None),
    tenure_band: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    scoped = _employee_scope(
        db,
        department_id=department_id,
        grade_band_id=grade_band_id,
        location_id=location_id,
        employment_type=employment_type,
        tenure_band=tenure_band,
    )
    employees = scoped.all()
    employee_ids = [employee.id for employee in employees]
    filters = _metric_filters(
        department_id=department_id,
        grade_band_id=grade_band_id,
        location_id=location_id,
        employment_type=employment_type,
        tenure_band=tenure_band,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
    )
    today = date.today()
    from_date = from_date or today.replace(month=1, day=1)
    to_date = to_date or today

    if metric == "pay_equity":
        latest = _latest_payroll_subquery(db, employee_ids)
        rows = (
            db.query(Employee.gender_identity, Employee.grade_band_id, func.avg(PayrollRecord.gross_salary), func.count(Employee.id))
            .join(latest, latest.c.employee_id == Employee.id)
            .join(PayrollRecord, PayrollRecord.id == latest.c.record_id)
            .filter(Employee.id.in_(employee_ids or [0]))
            .group_by(Employee.gender_identity, Employee.grade_band_id)
            .all()
        )
        result_rows = [
            {
                "gender_identity": row[0] or "Not specified",
                "grade_band_id": row[1],
                "average_gross_salary": round(float(row[2] or 0), 2),
                "employee_count": row[3],
            }
            for row in rows
        ]
        values = [row["average_gross_salary"] for row in result_rows]
        return {"metric": metric, "filters": filters, "summary": {"groups": len(result_rows), "gap": round((max(values) - min(values)) if values else 0, 2)}, "rows": result_rows}

    if metric == "span_of_control":
        rows = (
            db.query(Employee.reporting_manager_id, func.count(Employee.id))
            .filter(Employee.id.in_(employee_ids or [0]), Employee.reporting_manager_id.isnot(None))
            .group_by(Employee.reporting_manager_id)
            .all()
        )
        result_rows = [{"manager_employee_id": row[0], "direct_reports": row[1]} for row in rows]
        avg = round(sum(row["direct_reports"] for row in result_rows) / len(result_rows), 2) if result_rows else 0
        return {"metric": metric, "filters": filters, "summary": {"manager_count": len(result_rows), "average_span": avg}, "rows": result_rows}

    if metric == "manager_effectiveness":
        managers = {employee.reporting_manager_id for employee in employees if employee.reporting_manager_id}
        result_rows = []
        for manager_id in managers:
            team_ids = [employee.id for employee in employees if employee.reporting_manager_id == manager_id]
            goals = db.query(PerformanceGoal).filter(PerformanceGoal.employee_id.in_(team_ids or [0])).all()
            completed = sum(1 for goal in goals if (goal.status or "").lower() == "completed")
            reviews = db.query(PerformanceReview).filter(PerformanceReview.employee_id.in_(team_ids or [0]), PerformanceReview.submitted_at >= datetime.combine(from_date, datetime.min.time())).count()
            one_on_ones = db.query(OneOnOneRecord).filter(OneOnOneRecord.manager_id == manager_id, OneOnOneRecord.meeting_date >= from_date, OneOnOneRecord.meeting_date <= to_date).count()
            exited = db.query(Employee).filter(Employee.reporting_manager_id == manager_id, Employee.date_of_exit >= from_date, Employee.date_of_exit <= to_date).count()
            goal_score = (completed / len(goals) * 40) if goals else 20
            review_score = min(reviews, len(team_ids)) / len(team_ids) * 25 if team_ids else 0
            cadence_score = min(one_on_ones, len(team_ids)) / len(team_ids) * 25 if team_ids else 0
            attrition_penalty = min(exited * 5, 20)
            score = round(max(goal_score + review_score + cadence_score - attrition_penalty, 0), 2)
            result_rows.append({"manager_employee_id": manager_id, "team_size": len(team_ids), "score": score, "one_on_ones": one_on_ones, "reviews": reviews, "exits": exited})
        avg = round(sum(row["score"] for row in result_rows) / len(result_rows), 2) if result_rows else 0
        return {"metric": metric, "filters": filters, "summary": {"average_score": avg, "manager_count": len(result_rows)}, "rows": result_rows}

    if metric == "attrition_trend":
        exited = db.query(Employee).filter(Employee.id.in_(employee_ids or [0]), Employee.date_of_exit >= from_date, Employee.date_of_exit <= to_date).count()
        active = len(employee_ids)
        return {"metric": metric, "filters": filters, "summary": {"exits": exited, "active_headcount": active, "attrition_rate": round((exited / active * 100) if active else 0, 2)}, "rows": []}

    if metric == "absenteeism":
        attendance_rows = db.query(Attendance.status, func.count(Attendance.id)).filter(
            Attendance.employee_id.in_(employee_ids or [0]),
            Attendance.attendance_date >= from_date,
            Attendance.attendance_date <= to_date,
        ).group_by(Attendance.status).all()
        rows = [{"status": row[0] or "Unknown", "count": row[1]} for row in attendance_rows]
        total = sum(row["count"] for row in rows)
        absent = sum(row["count"] for row in rows if row["status"] in {"Absent", "Leave", "LOP"})
        return {"metric": metric, "filters": filters, "summary": {"attendance_records": total, "absent_records": absent, "absenteeism_rate": round((absent / total * 100) if total else 0, 2)}, "rows": rows}

    if metric == "dei_representation":
        rows = db.query(Employee.gender_identity, Employee.disability_status, func.count(Employee.id)).filter(Employee.id.in_(employee_ids or [0])).group_by(Employee.gender_identity, Employee.disability_status).all()
        return {
            "metric": metric,
            "filters": filters,
            "summary": {"headcount": len(employee_ids)},
            "rows": [{"gender_identity": row[0] or "Not specified", "disability_status": row[1] or "Not specified", "count": row[2]} for row in rows],
        }

    raise HTTPException(status_code=400, detail="Unsupported analytics metric")


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
    today = date.today()
    recent_attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.attendance_date >= today - timedelta(days=30),
    ).order_by(Attendance.attendance_date.desc()).limit(30).all()
    attendance_summary = {
        "present": sum(Decimal("0.5") if item.status == "Half-day" else Decimal("1") for item in recent_attendance if item.status in {"Present", "WFH", "On Duty", "Half-day"}),
        "absent": sum(1 for item in recent_attendance if item.status == "Absent"),
        "leave": sum(1 for item in recent_attendance if item.status in {"Leave", "On Leave"}),
        "weekly_off": sum(1 for item in recent_attendance if item.status in {"Weekly Off", "Weekend"}),
        "holiday": sum(1 for item in recent_attendance if item.status == "Holiday"),
    }
    leave_balances = db.query(LeaveBalance, LeaveType).join(LeaveType, LeaveType.id == LeaveBalance.leave_type_id).filter(
        LeaveBalance.employee_id == employee.id,
        LeaveBalance.year == today.year,
    ).all()
    claims = db.query(Reimbursement).filter(Reimbursement.employee_id == employee.id).order_by(Reimbursement.created_at.desc()).limit(12).all()
    return {
        "employee": {"id": employee.id, "employee_id": employee.employee_id, "name": f"{employee.first_name} {employee.last_name}"},
        "attendance": {
            "window_days": 30,
            "summary": attendance_summary,
            "recent": [
                {
                    "id": item.id,
                    "date": item.attendance_date,
                    "status": item.status,
                    "total_hours": item.total_hours,
                    "late_minutes": item.late_minutes,
                    "overtime_hours": item.overtime_hours,
                    "source": item.source,
                }
                for item in recent_attendance[:10]
            ],
        },
        "leave_balances": [
            {
                "leave_type_id": leave_type.id,
                "leave_type": leave_type.name,
                "code": leave_type.code,
                "allocated": balance.allocated,
                "used": balance.used,
                "pending": balance.pending,
                "carried_forward": balance.carried_forward,
                "available": (balance.allocated or 0) + (balance.carried_forward or 0) - (balance.used or 0) - (balance.pending or 0),
            }
            for balance, leave_type in leave_balances
        ],
        "claims": [
            {
                "id": item.id,
                "category": item.category,
                "amount": item.amount,
                "date": item.date,
                "status": item.status,
                "payroll_record_id": item.payroll_record_id,
            }
            for item in claims
        ],
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
    return [{"department": r[0], "department_name": r[0], "count": r[1]} for r in result]


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

    legal_gender = scoped_distribution(Employee.gender, "gender")
    department_diversity_rows = (
        db.query(Department.name, Employee.gender, func.count(Employee.id).label("count"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .filter(Employee.id.in_(employee_ids))
        .group_by(Department.name, Employee.gender)
        .all()
        if employee_ids else []
    )
    department_diversity: dict[str, dict[str, object]] = {}
    for department_name, gender, count in department_diversity_rows:
        key = department_name or "Not specified"
        row = department_diversity.setdefault(key, {"department_name": key, "Male": 0, "Female": 0, "Other": 0})
        label = gender if gender in {"Male", "Female"} else "Other"
        row[label] = int(row[label]) + int(count or 0)

    latest_records = (
        db.query(PayrollRecord.employee_id, func.max(PayrollRecord.id).label("record_id"))
        .filter(PayrollRecord.employee_id.in_(employee_ids))
        .group_by(PayrollRecord.employee_id)
        .subquery()
    )
    avg_pay_by_gender_rows = (
        db.query(Employee.gender, func.avg(PayrollRecord.gross_salary).label("avg_gross"))
        .join(latest_records, latest_records.c.employee_id == Employee.id)
        .join(PayrollRecord, PayrollRecord.id == latest_records.c.record_id)
        .group_by(Employee.gender)
        .all()
        if employee_ids else []
    )

    result = {
        "total_active_headcount": total,
        "gender_identity": scoped_distribution(Employee.gender_identity, "gender_identity"),
        "legal_gender": legal_gender,
        "gender_distribution": [
            {"label": row["gender"], "count": row["count"], "percent": row["percent"]}
            for row in legal_gender
        ],
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
        "department_diversity": list(department_diversity.values()),
        "avg_gross_by_gender": [
            {"label": row[0] or "Not specified", "avg_gross_pay": round(float(row[1] or 0), 2)}
            for row in avg_pay_by_gender_rows
        ],
    }

    if include_pay_equity:
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
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    today = date.today()
    year = year or today.year
    if month is None:
        months = [((today.replace(day=1) - timedelta(days=idx * 31)).replace(day=1)) for idx in range(5, -1, -1)]
        rows = []
        for period in months:
            monthly = (
                db.query(Attendance.status, func.count(Attendance.id).label("count"))
                .filter(
                    extract("month", Attendance.attendance_date) == period.month,
                    extract("year", Attendance.attendance_date) == period.year,
                )
                .group_by(Attendance.status)
                .all()
            )
            counts = {str(status or "").lower(): count for status, count in monthly}
            rows.append({
                "month": f"{period.year}-{period.month:02d}",
                "present_days": counts.get("present", 0),
                "absent_days": counts.get("absent", 0),
                "wfh_days": counts.get("work_from_home", 0) + counts.get("wfh", 0),
            })
        return rows

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
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    year = year or date.today().year
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
    months = {month: {"month": f"{year}-{month:02d}", "approved_count": 0, "pending_count": 0, "rejected_count": 0} for month in range(1, 13)}
    for row in result:
        month = int(row[0])
        status = str(row[2] or "").lower()
        if status == "approved":
            months[month]["approved_count"] += int(row[1] or 0)
        elif status == "rejected":
            months[month]["rejected_count"] += int(row[1] or 0)
        else:
            months[month]["pending_count"] += int(row[1] or 0)
    return list(months.values())


@router.get("/payroll-summary")
def payroll_summary(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    year = year or date.today().year
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
        {
            "month": f"{year}-{int(r[0]):02d}" if isinstance(r[0], int) else r[0],
            "gross": float(r[1] or 0),
            "gross_pay": float(r[1] or 0),
            "deductions": float(r[2] or 0),
            "total_deductions": float(r[2] or 0),
            "net": float(r[3] or 0),
            "net_pay": float(r[3] or 0),
            "status": r[4],
        }
        for r in result
    ]


@router.get("/employee-turnover")
def turnover_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    if not from_date or not to_date:
        today = date.today()
        periods = [((today.replace(day=1) - timedelta(days=idx * 31)).replace(day=1)) for idx in range(11, -1, -1)]
        active_total = db.query(func.count(Employee.id)).filter(Employee.status == "Active").scalar() or 0
        trend = []
        for period in periods:
            next_month = (period.replace(day=28) + timedelta(days=4)).replace(day=1)
            joined = db.query(func.count(Employee.id)).filter(
                Employee.date_of_joining >= period,
                Employee.date_of_joining < next_month,
            ).scalar() or 0
            exited = db.query(func.count(Employee.id)).filter(
                Employee.status.in_(["Resigned", "Terminated"]),
                Employee.date_of_exit >= period,
                Employee.date_of_exit < next_month,
            ).scalar() or 0
            trend.append({
                "month": f"{period.year}-{period.month:02d}",
                "joined": joined,
                "exited": exited,
                "attrition_rate": round((exited / active_total * 100) if active_total else 0, 2),
            })
        return trend

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
    return [{"status": r[0], "stage": r[0] or "Not specified", "count": r[1]} for r in result]


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


@router.get("/employee-report")
def employee_report(
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if branch_id:
        query = query.filter(Employee.branch_id == branch_id)
    if status:
        query = query.filter(Employee.status == status)
    employees = query.order_by(Employee.employee_id).limit(1000).all()
    status_counts = dict(
        db.query(Employee.status, func.count(Employee.id))
        .filter(Employee.deleted_at.is_(None))
        .group_by(Employee.status)
        .all()
    )
    return {
        "count": len(employees),
        "status_counts": status_counts,
        "items": [
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "name": f"{item.first_name} {item.last_name}",
                "status": item.status,
                "department_id": item.department_id,
                "designation_id": item.designation_id,
                "branch_id": item.branch_id,
                "location_id": item.location_id,
                "employment_type": item.employment_type,
                "date_of_joining": item.date_of_joining,
                "date_of_exit": item.date_of_exit,
                "reporting_manager_id": item.reporting_manager_id,
            }
            for item in employees
        ],
    }


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


@router.get("/reimbursement-report")
def reimbursement_report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(Reimbursement).join(Employee, Employee.id == Reimbursement.employee_id)
    if from_date:
        query = query.filter(Reimbursement.date >= from_date)
    if to_date:
        query = query.filter(Reimbursement.date <= to_date)
    if status:
        query = query.filter(Reimbursement.status == status)
    claims = query.order_by(Reimbursement.created_at.desc()).limit(1000).all()
    return {
        "count": len(claims),
        "total_amount": sum((item.amount or 0) for item in claims),
        "status_counts": dict(
            db.query(Reimbursement.status, func.count(Reimbursement.id))
            .group_by(Reimbursement.status)
            .all()
        ),
        "items": [
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "category": item.category,
                "amount": item.amount,
                "date": item.date,
                "status": item.status,
                "payroll_record_id": item.payroll_record_id,
            }
            for item in claims
        ],
    }


@router.get("/loan-outstanding-report")
def loan_outstanding_report(
    status: Optional[str] = Query("Active"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(EmployeeLoan).join(Employee, Employee.id == EmployeeLoan.employee_id)
    if status:
        query = query.filter(EmployeeLoan.status == status)
    loans = query.order_by(EmployeeLoan.created_at.desc()).limit(1000).all()
    return {
        "count": len(loans),
        "total_outstanding": sum((item.balance_amount or 0) for item in loans),
        "items": [
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "loan_type": item.loan_type,
                "principal_amount": item.principal_amount,
                "total_payable": item.total_payable,
                "emi_amount": item.emi_amount,
                "balance_amount": item.balance_amount,
                "start_month": item.start_month,
                "start_year": item.start_year,
                "status": item.status,
            }
            for item in loans
        ],
    }


@router.get("/fnf-report")
def fnf_report(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(FullFinalSettlement).join(Employee, Employee.id == FullFinalSettlement.employee_id)
    if status:
        query = query.filter(FullFinalSettlement.status == status)
    settlements = query.order_by(FullFinalSettlement.created_at.desc()).limit(1000).all()
    return {
        "count": len(settlements),
        "total_net_payable": sum((item.net_payable or 0) for item in settlements),
        "items": [
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "settlement_date": item.settlement_date,
                "last_working_date": item.last_working_date,
                "status": item.status,
                "unpaid_salary": item.unpaid_salary,
                "leave_encashment_amount": item.leave_encashment_amount,
                "notice_recovery_amount": item.notice_recovery_amount,
                "loan_recovery_amount": item.loan_recovery_amount,
                "net_payable": item.net_payable,
            }
            for item in settlements
        ],
    }


@router.get("/audit-log-report")
def audit_log_report(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {
        "count": len(logs),
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "method": item.method,
                "endpoint": item.endpoint,
                "status_code": item.status_code,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "action": item.action,
                "description": item.description,
                "created_at": item.created_at,
            }
            for item in logs
        ],
    }


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
