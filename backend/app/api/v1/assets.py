from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.apps.srm.services.commercial import tenant
from app.models.employee import Employee
from app.models.exit import ExitRecord
from app.core.deps import get_current_user, get_db, RequirePermission
from app.models.asset import Asset, AssetAssignment, AssetCategory
from app.models.user import User
from app.schemas.asset import (
    AssetAssignmentCreate,
    AssetAssignmentSchema,
    AssetCategoryCreate,
    AssetCategorySchema,
    AssetCreate,
    AssetSchema,
    AssetUpdate,
)

router = APIRouter(prefix="/assets", tags=["Asset Management"])


def _asset(db, asset_id, user, lock=False):
    query = db.query(Asset).filter(Asset.id == asset_id, Asset.organization_id == tenant(user))
    if lock:
        query = query.with_for_update()
    asset = query.first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset


def _employee(db, employee_id, user):
    from app.models.company import Branch
    query = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None))
    if not user.is_superuser:
        query = query.filter((Employee.branch_id.is_(None) & (tenant(user) == 1)) |
                             Employee.branch.has(Branch.company_id == tenant(user)))
    employee = query.first()
    if not employee:
        raise HTTPException(404, "Employee not found")
    return employee


@router.get("/capabilities")
def capabilities(current_user: User = Depends(RequirePermission("asset_view"))):
    from app.access.catalog import permission_objects
    return {"can_manage": current_user.is_superuser or "asset_manage" in {p.name for p in permission_objects(current_user)}}


@router.get("/employees")
def employee_options(search: str = "", db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    from app.models.company import Branch
    query = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.status == "Active")
    if not current_user.is_superuser:
        query = query.filter((Employee.branch_id.is_(None) & (tenant(current_user) == 1)) | Employee.branch.has(Branch.company_id == tenant(current_user)))
    if search:
        query = query.filter((Employee.first_name + " " + Employee.last_name).ilike(f"%{search}%") | Employee.employee_id.ilike(f"%{search}%"))
    return [{"id": row.id, "name": f"{row.first_name} {row.last_name}", "employee_code": row.employee_id}
            for row in query.order_by(Employee.first_name, Employee.id).limit(50).all()]


@router.get("/assignments")
def list_assignments(employee_id: Optional[int] = None, active: bool = True,
                     db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    query = db.query(AssetAssignment).join(Asset).options(joinedload(AssetAssignment.asset), joinedload(AssetAssignment.employee)).filter(
        Asset.organization_id == tenant(current_user), AssetAssignment.is_active == active)
    if employee_id:
        _employee(db, employee_id, current_user)
        query = query.filter(AssetAssignment.employee_id == employee_id)
    return [{"id": row.id, "asset_id": row.asset_id, "asset_name": row.asset.name, "asset_tag": row.asset.asset_tag,
             "employee_id": row.employee_id, "employee_name": f"{row.employee.first_name} {row.employee.last_name}",
             "assigned_date": row.assigned_date, "returned_date": row.returned_date,
             "condition": row.condition_at_assignment, "condition_at_return": row.condition_at_return,
             "acknowledged": row.acknowledgement_signed, "acknowledged_at": row.acknowledged_at,
             "acknowledged_by": row.acknowledged_by, "returned_by": row.returned_by, "remarks": row.remarks}
            for row in query.order_by(AssetAssignment.assigned_date.desc(), AssetAssignment.id.desc()).all()]


@router.get("/exit-clearance")
def exit_clearance(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    exits = db.query(ExitRecord).join(Employee).filter(ExitRecord.status.notin_(["Completed", "Cancelled"])).all()
    result = []
    for record in exits:
        try:
            employee = _employee(db, record.employee_id, current_user)
        except HTTPException:
            continue
        items = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(current_user),
            AssetAssignment.employee_id == employee.id, AssetAssignment.is_active.is_(True)).all()
        result.append({"exit_id": record.id, "employee_id": employee.id,
                       "employee_name": f"{employee.first_name} {employee.last_name}", "last_working_date": record.last_working_date,
                       "cleared": not items, "outstanding_assets": [{"assignment_id": row.id, "name": row.asset.name,
                       "asset_tag": row.asset.asset_tag} for row in items]})
    return result


@router.get("/categories", response_model=list[AssetCategorySchema])
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    return db.query(AssetCategory).order_by(AssetCategory.name).all()


@router.post("/categories", response_model=AssetCategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(data: AssetCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    category = AssetCategory(**data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/", response_model=list[AssetSchema])
def list_assets(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("asset_view")),
):
    query = db.query(Asset).filter(Asset.organization_id == tenant(current_user))
    if search:
        like = f"%{search}%"
        query = query.filter((Asset.name.ilike(like)) | (Asset.asset_tag.ilike(like)) | (Asset.serial_number.ilike(like)))
    if status_filter:
        query = query.filter(Asset.status == status_filter)
    return query.order_by(Asset.created_at.desc()).limit(200).all()


@router.get("/my", response_model=list[AssetAssignmentSchema])
def my_asset_assignments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    rows = db.query(AssetAssignment).options(joinedload(AssetAssignment.asset)).filter(
        AssetAssignment.employee_id == current_user.employee.id,
        AssetAssignment.is_active == True,
    ).order_by(AssetAssignment.assigned_date.desc()).all()
    return [{**AssetAssignmentSchema.model_validate(row).model_dump(), "asset_name": row.asset.name,
             "asset_tag": row.asset.asset_tag, "serial_number": row.asset.serial_number} for row in rows]


@router.post("/", response_model=AssetSchema, status_code=status.HTTP_201_CREATED)
def create_asset(data: AssetCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    asset = Asset(**data.model_dump(), organization_id=tenant(current_user))
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/{asset_id}", response_model=AssetSchema)
def update_asset(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    asset = _asset(db, asset_id, current_user)
    if data.status is not None and data.status not in {"Available", "Assigned", "Under Repair", "Retired"}:
        raise HTTPException(422, "Choose a valid inventory status")
    active_assignment = db.query(AssetAssignment.id).filter(AssetAssignment.asset_id == asset.id, AssetAssignment.is_active.is_(True)).first()
    if data.status in {"Available", "Retired", "Under Repair"} and active_assignment:
        raise HTTPException(409, "Record the employee's return before changing inventory availability")
    if data.status == "Assigned" and not active_assignment:
        raise HTTPException(409, "Assign this asset through an employee handover")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/assignments", response_model=AssetAssignmentSchema, status_code=status.HTTP_201_CREATED)
def assign_asset(data: AssetAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    from datetime import date
    asset = _asset(db, data.asset_id, current_user, lock=True)
    employee = _employee(db, data.employee_id, current_user)
    if data.assigned_date > date.today():
        raise HTTPException(422, "Assignment date cannot be in the future")
    if employee.status != "Active":
        raise HTTPException(409, "Only active employees can receive assets")
    exiting = db.query(ExitRecord).filter(ExitRecord.employee_id == employee.id, ExitRecord.status.notin_(["Cancelled"])).first()
    if exiting and exiting.status == "Completed":
        raise HTTPException(409, "Assets cannot be assigned after the employee's exit is completed")
    if asset.status != "Available" or db.query(AssetAssignment.id).filter(AssetAssignment.asset_id == asset.id, AssetAssignment.is_active.is_(True)).first():
        raise HTTPException(409, "This asset is not available for assignment")
    assignment = AssetAssignment(**data.model_dump(exclude={"remarks"}), remarks=data.remarks or asset.description, assigned_by=current_user.id)
    asset.status = "Assigned"
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.put("/assignments/{assignment_id}/acknowledge", response_model=AssetAssignmentSchema)
def acknowledge_asset_assignment(assignment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    _asset(db, assignment.asset_id, current_user)
    if not assignment.is_active:
        raise HTTPException(409, "Returned assets cannot be acknowledged")
    if not current_user.is_superuser and (not current_user.employee or assignment.employee_id != current_user.employee.id):
        raise HTTPException(status_code=403, detail="Only the assigned employee can acknowledge this asset")
    from datetime import datetime, timezone
    if not assignment.acknowledgement_signed:
        assignment.acknowledgement_signed = True
        assignment.acknowledged_at = datetime.now(timezone.utc)
        assignment.acknowledged_by = current_user.id
    db.commit()
    db.refresh(assignment)
    return assignment


@router.put("/assignments/{assignment_id}/return", response_model=AssetAssignmentSchema)
def return_asset(assignment_id: int, condition_at_return: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    from datetime import date
    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    asset = _asset(db, assignment.asset_id, current_user, lock=True)
    if not assignment.is_active:
        raise HTTPException(409, "This asset has already been returned")
    condition_at_return = condition_at_return or assignment.condition_at_assignment or "Good"
    if condition_at_return not in {"New", "Good", "Fair", "Poor", "Damaged"}:
        raise HTTPException(422, "Record the condition at return")
    assignment.returned_date = date.today()
    assignment.returned_by = current_user.id
    assignment.condition_at_return = condition_at_return
    assignment.is_active = False
    asset.status = "Under Repair" if condition_at_return in {"Poor", "Damaged"} else "Available"
    db.commit()
    db.refresh(assignment)
    return assignment
