from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.models.exit import ExitChecklistItem, ExitInterview, ExitRecord
from app.models.user import User
from app.services.employee_exit import scoped_exit, create_exit, validate_exit_dates
from app.services.metrics.queries import employee_records
from app.models.employee import Employee
from app.schemas.exit import (
    ExitChecklistItemCreate,
    ExitChecklistItemSchema,
    ExitInterviewCreate,
    ExitInterviewSchema,
    ExitRecordCreate,
    ExitRecordSchema,
    ExitRecordUpdate,
)

router = APIRouter(prefix="/exit", tags=["Exit Management"])


@router.get("/employees")
def employee_options(search: str = "", db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    from app.models.employee import Employee
    query = employee_records(db, current_user)
    if search:
        query = query.filter((Employee.first_name + " " + Employee.last_name).icontains(search, autoescape=True) | Employee.employee_id.icontains(search, autoescape=True))
    return [{"id": row.id, "name": f"{row.first_name} {row.last_name}", "employee_code": row.employee_id}
            for row in query.order_by(Employee.first_name, Employee.id).limit(50).all()]


@router.get("/records", response_model=list[ExitRecordSchema])
def list_exit_records(employee_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_view"))):
    query = db.query(ExitRecord).filter(ExitRecord.employee_id.in_(employee_records(db,current_user,include_archived=True).with_entities(Employee.id)))
    if employee_id: query = query.filter(ExitRecord.employee_id == employee_id)
    return query.order_by(ExitRecord.created_at.desc()).limit(200).all()


@router.post("/records", response_model=ExitRecordSchema, status_code=status.HTTP_201_CREATED)
def create_exit_record(data: ExitRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = create_exit(db, current_user, data.model_dump())
    db.commit()
    db.refresh(record)
    return record


@router.put("/records/{record_id}", response_model=ExitRecordSchema)
def update_exit_record(record_id: int, data: ExitRecordUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = scoped_exit(db, current_user, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Exit record not found")
    if record.status == "Completed":
        raise HTTPException(409, "Completed exit history cannot be overwritten")
    if data.status == "Completed":
        raise HTTPException(422, "Use the completion action after clearance checks")
    values = data.model_dump(exclude_unset=True)
    validate_exit_dates(db.get(Employee, record.employee_id), values)
    for key, value in values.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.put("/records/{record_id}/approve", response_model=ExitRecordSchema)
def approve_exit_record(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = scoped_exit(db, current_user, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Exit record not found")
    if record.status != "Initiated": raise HTTPException(409, "Only an initiated exit can be approved")
    record.status = "In Progress"
    record.approved_by = current_user.id
    record.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


@router.post("/checklist", response_model=ExitChecklistItemSchema, status_code=status.HTTP_201_CREATED)
def create_checklist_item(data: ExitChecklistItemCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    parent = scoped_exit(db, current_user, data.exit_record_id)
    if parent.status in {"Completed", "Cancelled"}: raise HTTPException(409, "Exit is closed")
    item = ExitChecklistItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/checklist/{item_id}/complete", response_model=ExitChecklistItemSchema)
def complete_checklist_item(item_id: int, remarks: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    item = db.get(ExitChecklistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    parent = scoped_exit(db, current_user, item.exit_record_id)
    if parent.status in {"Completed", "Cancelled"}: raise HTTPException(409, "Exit is closed")
    person = db.get(Employee, parent.employee_id)
    from app.models.asset import AssetAssignment
    if "access" in item.task_name.lower() and person.user and person.user.is_active:
        raise HTTPException(409, "Disable the linked login before signing off access clearance")
    from app.services.asset_lifecycle import blockers_for_employee
    if "asset" in item.task_name.lower() and blockers_for_employee(db, current_user, person.id):
        raise HTTPException(409, "Return company assets before signing off clearance")
    item.is_completed = True
    item.completed_at = datetime.now(timezone.utc)
    if remarks:
        item.remarks = remarks
    db.commit()
    db.refresh(item)
    return item


@router.get("/records/{record_id}/checklist", response_model=list[ExitChecklistItemSchema])
def list_exit_checklist(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_view"))):
    scoped_exit(db, current_user, record_id)
    return db.query(ExitChecklistItem).filter(ExitChecklistItem.exit_record_id == record_id).order_by(ExitChecklistItem.id).all()


@router.post("/interviews", response_model=ExitInterviewSchema, status_code=status.HTTP_201_CREATED)
def create_exit_interview(data: ExitInterviewCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    if not scoped_exit(db, current_user, data.exit_record_id):
        raise HTTPException(status_code=404, detail="Exit record not found")
    interview = ExitInterview(**data.model_dump(), conducted_by=current_user.id)
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.put("/records/{record_id}/complete", response_model=ExitRecordSchema)
def complete_exit_record(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = scoped_exit(db, current_user, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Exit record not found")
    from app.models.asset import AssetAssignment
    db.query(Employee).filter(Employee.id == record.employee_id).populate_existing().with_for_update().one()
    from app.services.asset_lifecycle import blockers_for_employee
    if blockers_for_employee(db, current_user, record.employee_id):
        raise HTTPException(409, "Company assets are still assigned. Complete asset returns before closing the exit.")
    pending = db.query(ExitChecklistItem).filter(ExitChecklistItem.exit_record_id == record_id, ExitChecklistItem.is_completed == False).count()
    if pending:
        raise HTTPException(status_code=400, detail="All exit checklist items must be completed before closing")
    if record.status == "Completed": return record
    if record.status == "Cancelled": raise HTTPException(409, "Cancelled exit cannot be completed")
    person = db.get(Employee, record.employee_id)
    if person.user and person.user.is_active:
        raise HTTPException(409, "Disable the linked login before completing exit")
    from app.services.metrics.queries import business_day
    if record.last_working_date and record.last_working_date > business_day(db, current_user):
        raise HTTPException(409, "Last working date has not arrived")
    from app.models.employee import EmployeeLifecycleEvent
    previous = person.status
    person.status = {"Termination": "Terminated", "Retirement": "Retired", "Absconding": "Absconding"}.get(record.exit_type, "Resigned")
    person.date_of_exit = record.last_working_date or business_day(db, current_user)
    db.add(EmployeeLifecycleEvent(employee_id=person.id, event_type="Exit completed", event_date=person.date_of_exit,
        from_status=previous, to_status=person.status, reason=record.reason or "Exit clearance completed", created_by=current_user.id))
    record.status = "Completed"
    db.commit()
    db.refresh(record)
    return record
