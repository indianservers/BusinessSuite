from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.employee import Employee
from app.models.timesheet import Project, Timesheet, TimesheetEntry
from app.models.user import User
from app.schemas.timesheet import (
    ProjectCreate,
    ProjectSchema,
    TimesheetCreate,
    TimesheetEntryCreate,
    TimesheetEntrySchema,
    TimesheetReview,
    TimesheetSchema,
)

router = APIRouter(prefix="/timesheets", tags=["Timesheets"])


def _recalculate_timesheet(sheet: Timesheet) -> None:
    total = Decimal("0")
    billable = Decimal("0")
    for entry in sheet.entries:
        total += entry.hours
        if entry.is_billable:
            billable += entry.hours
    sheet.total_hours = total
    sheet.billable_hours = billable
    sheet.non_billable_hours = total - billable


def _ensure_timesheet_owner(sheet: Timesheet, current_user: User) -> None:
    if current_user.is_superuser:
        return
    if not current_user.employee or sheet.employee_id != current_user.employee.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this timesheet")


@router.get("/projects", response_model=list[ProjectSchema])
def list_projects(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_view")),
):
    query = db.query(Project)
    if status_filter:
        query = query.filter(Project.status == status_filter)
    return query.order_by(Project.name).all()


@router.post("/projects", response_model=ProjectSchema, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_manage")),
):
    if db.query(Project).filter(Project.code == data.code).first():
        raise HTTPException(status_code=400, detail="Project code already exists")
    from app.apps.srm.services.commercial import tenant
    project = Project(**data.model_dump(), created_by=current_user.id, organization_id=tenant(current_user))
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/", response_model=list[TimesheetSchema])
def list_timesheets(
    employee_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_view")),
):
    query = db.query(Timesheet).options(joinedload(Timesheet.entries))
    if employee_id:
        query = query.filter(Timesheet.employee_id == employee_id)
    elif current_user.role and current_user.role.name == "employee" and current_user.employee:
        query = query.filter(Timesheet.employee_id == current_user.employee.id)
    if project_id:
        query = query.filter(Timesheet.project_id == project_id)
    if status_filter:
        query = query.filter(Timesheet.status == status_filter)
    return query.order_by(Timesheet.period_start.desc(), Timesheet.id.desc()).limit(500).all()


@router.post("/", response_model=TimesheetSchema, status_code=status.HTTP_201_CREATED)
def create_timesheet(
    data: TimesheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_view")),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile linked to this user")
    if data.period_end < data.period_start:
        raise HTTPException(status_code=400, detail="Timesheet period end cannot be before start")
    project = db.query(Project).filter(Project.id == data.project_id, Project.status == "Active").first()
    if not project:
        raise HTTPException(status_code=404, detail="Active project not found")
    existing = db.query(Timesheet).filter(
        Timesheet.employee_id == current_user.employee.id,
        Timesheet.project_id == data.project_id,
        Timesheet.period_start == data.period_start,
        Timesheet.period_end == data.period_end,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Timesheet already exists for this project and period")
    sheet = Timesheet(employee_id=current_user.employee.id, **data.model_dump())
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet


@router.post("/{timesheet_id}/entries", response_model=TimesheetEntrySchema, status_code=status.HTTP_201_CREATED)
def add_timesheet_entry(
    timesheet_id: int,
    data: TimesheetEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_view")),
):
    sheet = db.query(Timesheet).options(joinedload(Timesheet.entries)).filter(Timesheet.id == timesheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    if sheet.status != "Draft":
        raise HTTPException(status_code=400, detail="Only draft timesheets can be edited")
    _ensure_timesheet_owner(sheet, current_user)
    if data.work_date < sheet.period_start or data.work_date > sheet.period_end:
        raise HTTPException(status_code=400, detail="Entry date must be inside timesheet period")
    if data.hours <= 0 or data.hours > 24:
        raise HTTPException(status_code=400, detail="Entry hours must be between 0 and 24")
    entry = TimesheetEntry(timesheet_id=timesheet_id, **data.model_dump())
    sheet.entries.append(entry)
    _recalculate_timesheet(sheet)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/{timesheet_id}/submit", response_model=TimesheetSchema)
def submit_timesheet(
    timesheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_view")),
):
    sheet = db.query(Timesheet).options(joinedload(Timesheet.entries)).filter(Timesheet.id == timesheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    _ensure_timesheet_owner(sheet, current_user)
    if not sheet.entries:
        raise HTTPException(status_code=400, detail="Cannot submit an empty timesheet")
    _recalculate_timesheet(sheet)
    sheet.status = "Submitted"
    sheet.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sheet)
    return sheet


@router.put("/{timesheet_id}/review", response_model=TimesheetSchema)
def review_timesheet(
    timesheet_id: int,
    data: TimesheetReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("timesheet_approve")),
):
    if data.status not in {"Approved", "Rejected"}:
        raise HTTPException(status_code=400, detail="Review status must be Approved or Rejected")
    sheet = db.query(Timesheet).options(joinedload(Timesheet.entries)).filter(Timesheet.id == timesheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    if sheet.status != "Submitted":
        raise HTTPException(status_code=400, detail="Only submitted timesheets can be reviewed")
    sheet.status = data.status
    sheet.reviewed_by = current_user.id
    sheet.reviewed_at = datetime.now(timezone.utc)
    sheet.review_remarks = data.review_remarks
    db.commit()
    db.refresh(sheet)
    return sheet


@router.put('/projects/{identity}',response_model=ProjectSchema)
def edit_timesheet_project(identity:int,data:ProjectCreate,db:Session=Depends(get_db),user:User=Depends(RequirePermission('timesheet_manage'))):
    from app.apps.srm.services.commercial import tenant
    row=db.query(Project).filter_by(id=identity,organization_id=tenant(user)).first()
    if not row:raise HTTPException(404,'Timesheet project not found')
    for key,value in data.model_dump().items():setattr(row,key,value)
    db.commit();db.refresh(row);return row
@router.delete('/projects/{identity}',status_code=204)
def delete_timesheet_project(identity:int,db:Session=Depends(get_db),user:User=Depends(RequirePermission('timesheet_manage'))):
    from app.apps.srm.services.commercial import tenant
    row=db.query(Project).filter_by(id=identity,organization_id=tenant(user)).first()
    if not row:raise HTTPException(404,'Timesheet project not found')
    if db.query(Timesheet).filter_by(project_id=identity).first():raise HTTPException(409,'Projects with time entries must be retained; mark the project inactive instead')
    db.delete(row);db.commit()


@router.get('/projects/{identity}',response_model=ProjectSchema)
def read_timesheet_project(identity:int,db:Session=Depends(get_db),user:User=Depends(RequirePermission('timesheet_view'))):
    from app.apps.srm.services.commercial import tenant
    row=db.query(Project).filter_by(id=identity,organization_id=tenant(user)).first()
    if not row:raise HTTPException(404,'Timesheet project not found')
    return row
