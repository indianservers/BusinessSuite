from typing import Optional
from app.services import asset_lifecycle as lifecycle
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
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
    return lifecycle.asset(db, user, asset_id, lock=lock)


def _employee(db, employee_id, user):
    return lifecycle.person(db, user, employee_id)


def _persist(db, *, flush_only=False):
    try:
        db.flush() if flush_only else db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The asset identifier or custody record changed concurrently; reload and retry")


@router.get("/capabilities")
def capabilities(current_user: User = Depends(RequirePermission("asset_view"))):
    from app.access.catalog import permission_objects
    return {"can_manage": current_user.is_superuser or "asset_manage" in {p.name for p in permission_objects(current_user)}}


@router.get("/employees")
def employee_options(search: str = "", db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    from app.services.metrics.queries import employee_records
    query = employee_records(db, current_user).filter(Employee.status == "Active")
    if search:
        query = query.filter((Employee.first_name + " " + Employee.last_name).ilike(f"%{search}%") | Employee.employee_id.ilike(f"%{search}%"))
    return [{"id": row.id, "name": f"{row.first_name} {row.last_name}", "employee_code": row.employee_id}
            for row in query.order_by(Employee.first_name, Employee.id).limit(50).all()]


@router.get("/assignments")
def list_assignments(employee_id: Optional[int] = None, active: bool = True,
                     search: str = "", status: str = "", group: str = "", department: str = "",
                     from_date: Optional[str] = None, to_date: Optional[str] = None, descending: bool = True,
                     offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=200), paged: bool = False,
                     db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    query = db.query(AssetAssignment).join(Asset).options(joinedload(AssetAssignment.asset), joinedload(AssetAssignment.employee)).filter(
        Asset.organization_id == tenant(current_user), AssetAssignment.is_active == active)
    if employee_id:
        _employee(db, employee_id, current_user)
        query = query.filter(AssetAssignment.employee_id == employee_id)
    if search:
        query = query.join(Employee).filter(or_(Asset.name.ilike(f"%{search}%"), Asset.asset_tag.ilike(f"%{search}%"),
            (Employee.first_name + " " + Employee.last_name).ilike(f"%{search}%"), Employee.employee_id.ilike(f"%{search}%")))
    if status:
        if status == "Acknowledged": query = query.filter(AssetAssignment.acknowledgement_signed.is_(True))
        elif status == "Acknowledgment pending": query = query.filter(AssetAssignment.acknowledgement_signed.is_(False))
        elif status == "Overdue":
            from app.services.metrics.queries import business_day
            query = query.filter(AssetAssignment.expected_return_date < business_day(db, current_user))
        elif status in {"Pending", "Awaiting Approval", "Approved", "Rejected"}: query = query.filter(AssetAssignment.inspection_status == status)
        elif status == "Outstanding Recovery": query = query.filter(AssetAssignment.recovery_status.in_(["Pending", "Approved"]))
    from datetime import date
    field = AssetAssignment.assigned_date if active else AssetAssignment.returned_date
    for value, lower in [(from_date, True), (to_date, False)]:
        if value:
            try: parsed = date.fromisoformat(value)
            except ValueError: raise HTTPException(422, "Use an ISO date for the register date range")
            query = query.filter(field >= parsed if lower else field <= parsed)
    if department:
        from app.models.company import Department
        query = query.filter(AssetAssignment.employee.has(Employee.department.has(Department.name == department)))
    total = query.count()
    from sqlalchemy import func
    summary = [{"label": "Assigned assets" if active else "Total returns", "value": total},
        {"label": "Employees with assets" if active else "Pending inspections", "value": query.with_entities(func.count(func.distinct(AssetAssignment.employee_id))).scalar() if active else query.filter(AssetAssignment.inspection_status.in_(["Pending", "Awaiting Approval", "Rejected"])).count()},
        {"label": "Pending handover" if active else "Damaged returns", "value": query.filter(AssetAssignment.acknowledgement_signed.is_(False)).count() if active else query.filter(AssetAssignment.condition_at_return.in_(["Poor", "Damaged"])).count()}]
    from app.services.metrics.queries import business_day
    from datetime import timedelta
    today = business_day(db, current_user)
    if active:
        summary += [{"label": "Overdue returns", "value": query.filter(AssetAssignment.expected_return_date < today).count()},
            {"label": "Due within 30 days", "value": query.filter(AssetAssignment.expected_return_date >= today, AssetAssignment.expected_return_date <= today + timedelta(days=30)).count()},
            {"label": "Damaged in custody", "value": query.filter(Asset.condition.in_(["Poor", "Damaged"])).count()}]
    else:
        summary += [{"label": "Returned this month", "value": query.filter(AssetAssignment.returned_date >= today.replace(day=1)).count()},
            {"label": "Good condition", "value": query.filter(AssetAssignment.condition_at_return.in_(["New", "Good"])).count()},
            {"label": "Under repair", "value": query.filter(Asset.status == "Under Repair").count()},
            {"label": "Outstanding recoveries", "value": str(query.filter(AssetAssignment.recovery_status.in_(["Pending", "Approved"])).with_entities(func.coalesce(func.sum(AssetAssignment.recovery_amount), 0)).scalar())}]
    sort_field = AssetAssignment.assigned_date if active else AssetAssignment.returned_date
    ordering = [sort_field.desc() if descending else sort_field.asc(), AssetAssignment.id.desc()]
    from sqlalchemy import select
    grouping = {"employee": AssetAssignment.employee_id, "department": select(Employee.department_id).where(Employee.id == AssetAssignment.employee_id).correlate(AssetAssignment).scalar_subquery(),
        "branch": Asset.location, "category": Asset.category_id, "status": AssetAssignment.acknowledgement_signed if active else AssetAssignment.inspection_status}.get(group)
    if grouping is not None:
        ordering.insert(0, grouping)
    result = [{"id": row.id, "asset_id": row.asset_id, "asset_name": row.asset.name, "asset_tag": row.asset.asset_tag,
             "employee_id": row.employee_id, "employee_code": row.employee.employee_id,
             "employee_photo": row.employee.profile_photo_url, "asset_category": row.asset.category.name if row.asset.category else "Uncategorized", "branch": row.asset.location or "Unspecified", "department": row.employee.department.name if row.employee.department else "Unassigned",
             "expected_return_date": row.expected_return_date, "accessories": row.accessories,
             "inspection_status": row.inspection_status, "return_details": row.return_details,
             "recovery_status": row.recovery_status, "recovery_amount": str(row.recovery_amount),
             "condition_at_assignment": row.condition_at_assignment, "handover_group": row.handover_group,
             "employee_name": f"{row.employee.first_name} {row.employee.last_name}",
             "assigned_date": row.assigned_date, "returned_date": row.returned_date,
             "condition": row.condition_at_assignment, "condition_at_return": row.condition_at_return,
             "acknowledged": row.acknowledgement_signed, "acknowledged_at": row.acknowledged_at,
             "acknowledged_by": row.acknowledged_by, "returned_by": row.returned_by, "remarks": row.remarks}
            for row in query.order_by(*ordering).offset(offset).limit(limit).all()]
    return {"items": result, "total": total, "summary": summary} if paged else result


@router.get("/exit-clearance")
def exit_clearance(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    from app.services.metrics.queries import employee_records
    exits = db.query(ExitRecord).filter(ExitRecord.employee_id.in_(employee_records(db, current_user, include_archived=True).with_entities(Employee.id)), ExitRecord.status != "Cancelled").all()
    result = []
    for record in exits:
        employee = record.employee
        items = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(current_user), AssetAssignment.employee_id == employee.id, AssetAssignment.is_active.is_(True)).all()
        issues = lifecycle.blockers_for_employee(db, current_user, employee.id)
        from app.models.exit import ExitChecklistItem
        tasks = db.query(ExitChecklistItem).filter_by(exit_record_id=record.id).all()
        all_rows = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(current_user), AssetAssignment.employee_id == employee.id).all()
        result.append({"exit_id": record.id, "employee_id": employee.id,
            "employee_name": f"{employee.first_name} {employee.last_name}", "employee_code": employee.employee_id,
            "department": employee.department.name if employee.department else "Unassigned", "last_working_date": record.last_working_date,
            "exit_type": record.exit_type, "exit_status": record.status, "cleared": not issues,
            "assets_returned": sum(not r.is_active for r in all_rows), "assets_assigned": len(all_rows), "issues": issues,
            "checklist": [{"id": t.id, "task_name": t.task_name, "department": t.assigned_to_role, "completed": t.is_completed, "remarks": t.remarks} for t in tasks],
            "outstanding_assets": [{"assignment_id": r.id, "asset_id": r.asset_id, "name": r.asset.name, "asset_tag": r.asset.asset_tag} for r in items]})
    return result


@router.get("/categories", response_model=list[AssetCategorySchema])
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    return db.query(AssetCategory).order_by(AssetCategory.name).all()


@router.post("/categories", response_model=AssetCategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(data: AssetCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    category = AssetCategory(**data.model_dump())
    db.add(category)
    _persist(db)
    db.refresh(category)
    return category


@router.get("/summary")
def asset_summary(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_view"))):
    from sqlalchemy import func
    rows = db.query(Asset.status, func.count(Asset.id)).filter(Asset.organization_id == tenant(current_user)).group_by(Asset.status).all()
    categories = db.query(Asset.category_id, func.count(Asset.id)).filter(Asset.organization_id == tenant(current_user)).group_by(Asset.category_id).all()
    returned = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(current_user), AssetAssignment.returned_date.is_not(None), AssetAssignment.is_active.is_(False)).count()
    return {"returned": returned, "total": sum(count for _, count in rows), "statuses": dict(rows), "categories": [{"category_id": key, "count": count} for key, count in categories]}


@router.get("/", response_model=list[AssetSchema])
def list_assets(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    category_id: Optional[int] = None,
    sort: str = Query("created_at", pattern="^(created_at|name|asset_tag|status|purchase_cost|warranty_expiry)$"),
    descending: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("asset_view")),
):
    query = db.query(Asset).filter(Asset.organization_id == tenant(current_user))
    if search:
        like = f"%{search}%"
        query = query.filter((Asset.name.ilike(like)) | (Asset.asset_tag.ilike(like)) | (Asset.serial_number.ilike(like)))
    if status_filter == "Returned":
        query = query.filter(Asset.assignments.any(AssetAssignment.returned_date.is_not(None)))
    elif status_filter == "Lost / Damaged":
        query = query.filter(Asset.status.in_(["Lost", "Damaged"]))
    elif status_filter == "Retired / Disposed":
        query = query.filter(Asset.status.in_(["Retired", "Disposed"]))
    elif status_filter:
        query = query.filter(Asset.status == status_filter)
    if category_id is not None:
        query = query.filter(Asset.category_id == category_id)
    column = getattr(Asset, sort)
    return query.options(joinedload(Asset.assignments).joinedload(AssetAssignment.employee)).order_by(column.desc() if descending else column.asc(), Asset.id.desc()).offset(offset).limit(limit).all()


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
    values = data.model_dump()
    lifecycle.validate_asset_values(db, current_user, values)
    if values.get("status") != "Available":
        raise HTTPException(422, "New assets must be available; use lifecycle actions for custody and repairs")
    if values.get("condition") in {"Poor", "Damaged"}:
        values["status"] = "Under Repair"
    asset = Asset(**values, organization_id=tenant(current_user))
    db.add(asset)
    _persist(db, flush_only=True)
    lifecycle.audit(db, current_user, asset, "registered", after=values)
    _persist(db)
    db.refresh(asset)
    return asset


@router.put("/{asset_id}", response_model=AssetSchema)
def update_asset(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    asset = _asset(db, asset_id, current_user, lock=True)
    values = data.model_dump(exclude_unset=True)
    lifecycle.validate_asset_values(db, current_user, values, current=asset)
    if asset.status == "Pending Inspection" and data.status is not None:
        raise HTTPException(409, "Complete the inspection approval before changing availability")
    if data.status is not None and data.status not in lifecycle.STATUSES:
        raise HTTPException(422, "Choose a valid inventory status")
    active_assignment = db.query(AssetAssignment.id).filter(AssetAssignment.asset_id == asset.id, AssetAssignment.is_active.is_(True)).first()
    if data.status is not None and data.status != "Assigned" and active_assignment:
        raise HTTPException(409, "Record the employee's return before changing inventory availability")
    if data.status == "Assigned" and not active_assignment:
        raise HTTPException(409, "Assign this asset through an employee handover")
    if values.get("status") == "Available" and values.get("condition", asset.condition) in {"Poor", "Damaged", "Lost"}:
        raise HTTPException(422, "Confirm a serviceable condition before making the asset available")
    before = {key: getattr(asset, key) for key in values}
    for key, value in values.items():
        setattr(asset, key, value)
    lifecycle.audit(db, current_user, asset, "modified", before=before, after=values)
    _persist(db)
    db.refresh(asset)
    return asset


@router.post("/assignments", response_model=AssetAssignmentSchema, status_code=status.HTTP_201_CREATED)
def assign_asset(data: AssetAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    from app.schemas.asset import AssetHandover
    from uuid import uuid4
    values = data.model_dump()
    values["remarks"] = data.remarks or _asset(db, data.asset_id, current_user).description or ""
    batch = AssetHandover(**{key: value for key, value in values.items() if key != "asset_id"}, asset_ids=[data.asset_id], request_key=str(uuid4()))
    rows = lifecycle.issue_batch(db, current_user, batch)
    _persist(db)
    return rows[0]


@router.put("/assignments/{assignment_id}/acknowledge", response_model=AssetAssignmentSchema)
def acknowledge_asset_assignment(assignment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assignment, item = lifecycle.assignment(db, current_user, assignment_id, lock=True)
    if not assignment.is_active:
        raise HTTPException(409, "Returned assets cannot be acknowledged")
    if not current_user.is_superuser and (not current_user.employee or assignment.employee_id != current_user.employee.id):
        raise HTTPException(status_code=403, detail="Only the assigned employee can acknowledge this asset")
    from datetime import datetime, timezone
    if not assignment.acknowledgement_signed:
        assignment.acknowledgement_signed = True
        assignment.acknowledged_at = datetime.now(timezone.utc)
        assignment.acknowledged_by = current_user.id
        lifecycle.audit(db, current_user, item, "handover_acknowledged", row=assignment)
    _persist(db)
    db.refresh(assignment)
    return assignment


@router.put("/assignments/{assignment_id}/return", response_model=AssetAssignmentSchema)
def return_asset(assignment_id: int, condition_at_return: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("asset_manage"))):
    from app.schemas.asset import AssetReturn
    from app.services.metrics.queries import business_day
    assignment, item = lifecycle.assignment(db, current_user, assignment_id, lock=True)
    data = AssetReturn(return_date=business_day(db, current_user), condition=condition_at_return or assignment.condition_at_assignment or "Good")
    lifecycle.receive_return(db, current_user, assignment, item, data)
    _persist(db)
    return assignment


@router.delete('/{asset_id}',status_code=204)
def delete_unused_asset(asset_id:int,db:Session=Depends(get_db),user:User=Depends(RequirePermission('asset_manage'))):
    asset=_asset(db,asset_id,user,lock=True)
    if db.query(AssetAssignment).filter_by(asset_id=asset.id).first():raise HTTPException(409,'Assets with custody history must be retained; change their status instead')
    db.delete(asset);db.commit()


from app.api.v1.asset_workflows import router as workflow_router
router.include_router(workflow_router)
