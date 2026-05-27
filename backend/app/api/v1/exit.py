from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.models.exit import ExitChecklistItem, ExitInterview, ExitRecord
from app.models.user import User
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


DEFAULT_EXIT_CHECKLIST = [
    ("IT handover and access revocation", "IT"),
    ("Asset return and condition check", "IT"),
    ("Finance clearance", "Finance"),
    ("Knowledge transfer sign-off", "Manager"),
    ("HR exit documentation", "HR"),
]


@router.get("/records", response_model=list[ExitRecordSchema])
def list_exit_records(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_view"))):
    return db.query(ExitRecord).order_by(ExitRecord.created_at.desc()).limit(200).all()


@router.post("/records", response_model=ExitRecordSchema, status_code=status.HTTP_201_CREATED)
def create_exit_record(data: ExitRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = ExitRecord(**data.model_dump())
    db.add(record)
    db.flush()
    for task_name, role in DEFAULT_EXIT_CHECKLIST:
        db.add(ExitChecklistItem(exit_record_id=record.id, task_name=task_name, assigned_to_role=role))
    db.commit()
    db.refresh(record)
    return record


@router.put("/records/{record_id}", response_model=ExitRecordSchema)
def update_exit_record(record_id: int, data: ExitRecordUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = db.get(ExitRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Exit record not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.put("/records/{record_id}/approve", response_model=ExitRecordSchema)
def approve_exit_record(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = db.get(ExitRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Exit record not found")
    record.status = "In Progress"
    record.approved_by = current_user.id
    record.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


@router.post("/checklist", response_model=ExitChecklistItemSchema, status_code=status.HTTP_201_CREATED)
def create_checklist_item(data: ExitChecklistItemCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
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
    item.is_completed = True
    item.completed_at = datetime.now(timezone.utc)
    if remarks:
        item.remarks = remarks
    db.commit()
    db.refresh(item)
    return item


@router.get("/records/{record_id}/checklist", response_model=list[ExitChecklistItemSchema])
def list_exit_checklist(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_view"))):
    return db.query(ExitChecklistItem).filter(ExitChecklistItem.exit_record_id == record_id).order_by(ExitChecklistItem.id).all()


@router.post("/interviews", response_model=ExitInterviewSchema, status_code=status.HTTP_201_CREATED)
def create_exit_interview(data: ExitInterviewCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    if not db.get(ExitRecord, data.exit_record_id):
        raise HTTPException(status_code=404, detail="Exit record not found")
    interview = ExitInterview(**data.model_dump(), conducted_by=current_user.id)
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.put("/records/{record_id}/complete", response_model=ExitRecordSchema)
def complete_exit_record(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("exit_manage"))):
    record = db.get(ExitRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Exit record not found")
    pending = db.query(ExitChecklistItem).filter(ExitChecklistItem.exit_record_id == record_id, ExitChecklistItem.is_completed == False).count()
    if pending:
        raise HTTPException(status_code=400, detail="All exit checklist items must be completed before closing")
    record.status = "Completed"
    db.commit()
    db.refresh(record)
    return record
