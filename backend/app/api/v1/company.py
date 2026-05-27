from datetime import datetime, timezone
from typing import List, Optional
import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.core.config import settings
from app.models.company import (
    Company, Branch, Department, Designation, BusinessUnit, CostCenter, WorkLocation,
    GradeBand, JobFamily, JobProfile, Position, HeadcountPlan,
)
from app.models.employee import Employee
from app.models.user import User
from app.schemas.company import (
    CompanyCreate, CompanyUpdate, CompanySchema,
    BranchCreate, BranchUpdate, BranchSchema,
    DepartmentCreate, DepartmentUpdate, DepartmentSchema,
    DesignationCreate, DesignationUpdate, DesignationSchema,
    BusinessUnitCreate, BusinessUnitSchema, CostCenterCreate, CostCenterSchema,
    WorkLocationCreate, WorkLocationSchema, GradeBandCreate, GradeBandSchema,
    JobFamilyCreate, JobFamilySchema, JobProfileCreate, JobProfileSchema,
    PositionCreate, PositionSchema, HeadcountPlanCreate, HeadcountPlanSchema,
)

router = APIRouter(prefix="/company", tags=["Company Setup"])


def _clean(value: Optional[str]) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _active_company(db: Session, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id, Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Active company not found")
    return company


def _active_branch(db: Session, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active == True).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Active branch not found")
    return branch


def _active_department(db: Session, department_id: int) -> Department:
    department = db.query(Department).filter(Department.id == department_id, Department.is_active == True).first()
    if not department:
        raise HTTPException(status_code=404, detail="Active department not found")
    return department


def _ensure_company_unique(db: Session, data: CompanyCreate | CompanyUpdate, exclude_id: Optional[int] = None) -> None:
    checks = {
        "name": _clean(data.name),
        "registration_number": _clean(data.registration_number),
        "pan_number": _clean(data.pan_number),
        "tan_number": _clean(data.tan_number),
        "gstin": _clean(data.gstin),
    }
    for field, value in checks.items():
        if not value:
            continue
        query = db.query(Company).filter(Company.is_active == True, func.lower(getattr(Company, field)) == value.lower())
        if exclude_id:
            query = query.filter(Company.id != exclude_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"Company {field.replace('_', ' ')} already exists")


def _ensure_branch_unique(db: Session, data: BranchCreate | BranchUpdate, company_id: int, exclude_id: Optional[int] = None) -> None:
    for field in ("name", "code"):
        value = _clean(getattr(data, field))
        if not value:
            continue
        query = db.query(Branch).filter(
            Branch.is_active == True,
            Branch.company_id == company_id,
            func.lower(getattr(Branch, field)) == value.lower(),
        )
        if exclude_id:
            query = query.filter(Branch.id != exclude_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"Branch {field} already exists for this company")


def _ensure_department_unique(db: Session, data: DepartmentCreate | DepartmentUpdate, branch_id: int, exclude_id: Optional[int] = None) -> None:
    for field in ("name", "code"):
        value = _clean(getattr(data, field))
        if not value:
            continue
        query = db.query(Department).filter(
            Department.is_active == True,
            Department.branch_id == branch_id,
            func.lower(getattr(Department, field)) == value.lower(),
        )
        if exclude_id:
            query = query.filter(Department.id != exclude_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"Department {field} already exists for this branch")


def _ensure_designation_unique(db: Session, data: DesignationCreate | DesignationUpdate, department_id: int, exclude_id: Optional[int] = None) -> None:
    for field in ("name", "code"):
        value = _clean(getattr(data, field))
        if not value:
            continue
        query = db.query(Designation).filter(
            Designation.is_active == True,
            Designation.department_id == department_id,
            func.lower(getattr(Designation, field)) == value.lower(),
        )
        if exclude_id:
            query = query.filter(Designation.id != exclude_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"Designation {field} already exists for this department")


# ── Company ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CompanySchema])
def list_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    return db.query(Company).filter(Company.is_active == True).all()


@router.post("/", response_model=CompanySchema, status_code=status.HTTP_201_CREATED)
def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    _ensure_company_unique(db, data)
    company = Company(**data.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/settings", response_model=CompanySchema)
def get_company_settings(
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    query = db.query(Company).filter(Company.is_active == True)
    if company_id:
        query = query.filter(Company.id == company_id)
    company = query.order_by(Company.id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company settings not found")
    return company


@router.put("/settings", response_model=CompanySchema)
def update_company_settings(
    data: CompanyUpdate,
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    query = db.query(Company).filter(Company.is_active == True)
    if company_id:
        query = query.filter(Company.id == company_id)
    company = query.order_by(Company.id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company settings not found")
    _ensure_company_unique(db, data, exclude_id=company.id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return company


# ── Branch ───────────────────────────────────────────────────────────────────

@router.get("/branches/", response_model=List[BranchSchema])
def list_branches(
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    q = db.query(Branch).filter(Branch.is_active == True)
    if company_id:
        q = q.filter(Branch.company_id == company_id)
    return q.all()


@router.post("/branches/", response_model=BranchSchema, status_code=201)
def create_branch(
    data: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    _active_company(db, data.company_id)
    _ensure_branch_unique(db, data, data.company_id)
    branch = Branch(**data.model_dump())
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


@router.put("/branches/{branch_id}", response_model=BranchSchema)
def update_branch(
    branch_id: int,
    data: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    target_company_id = data.company_id if data.company_id is not None else branch.company_id
    _active_company(db, target_company_id)
    _ensure_branch_unique(db, data, target_company_id, exclude_id=branch_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(branch, k, v)
    db.commit()
    db.refresh(branch)
    return branch


@router.delete("/branches/{branch_id}")
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    branch.is_active = False
    db.commit()
    return {"message": "Branch deactivated"}


# ── Department ───────────────────────────────────────────────────────────────

@router.get("/departments/", response_model=List[DepartmentSchema])
def list_departments(
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    q = db.query(Department).filter(Department.is_active == True)
    if branch_id:
        q = q.filter(Department.branch_id == branch_id)
    return q.all()


@router.post("/departments/", response_model=DepartmentSchema, status_code=201)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    _active_branch(db, data.branch_id)
    _ensure_department_unique(db, data, data.branch_id)
    dept = Department(**data.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.put("/departments/{dept_id}", response_model=DepartmentSchema)
def update_department(
    dept_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    target_branch_id = data.branch_id if data.branch_id is not None else dept.branch_id
    _active_branch(db, target_branch_id)
    _ensure_department_unique(db, data, target_branch_id, exclude_id=dept_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(dept, k, v)
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/departments/{dept_id}")
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    dept.is_active = False
    db.commit()
    return {"message": "Department deactivated"}


# ── Designation ──────────────────────────────────────────────────────────────

@router.get("/designations/", response_model=List[DesignationSchema])
def list_designations(
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    q = db.query(Designation).filter(Designation.is_active == True)
    if department_id:
        q = q.filter(Designation.department_id == department_id)
    return q.all()


@router.post("/designations/", response_model=DesignationSchema, status_code=201)
def create_designation(
    data: DesignationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    _active_department(db, data.department_id)
    _ensure_designation_unique(db, data, data.department_id)
    desig = Designation(**data.model_dump())
    db.add(desig)
    db.commit()
    db.refresh(desig)
    return desig


@router.put("/designations/{desig_id}", response_model=DesignationSchema)
def update_designation(
    desig_id: int,
    data: DesignationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    desig = db.query(Designation).filter(Designation.id == desig_id).first()
    if not desig:
        raise HTTPException(status_code=404, detail="Designation not found")
    target_department_id = data.department_id if data.department_id is not None else desig.department_id
    _active_department(db, target_department_id)
    _ensure_designation_unique(db, data, target_department_id, exclude_id=desig_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(desig, k, v)
    db.commit()
    db.refresh(desig)
    return desig


@router.delete("/designations/{desig_id}")
def delete_designation(
    desig_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    desig = db.query(Designation).filter(Designation.id == desig_id).first()
    if not desig:
        raise HTTPException(status_code=404, detail="Designation not found")
    desig.is_active = False
    db.commit()
    return {"message": "Designation deactivated"}


def _create_org_master(db: Session, model, data):
    item = model(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _list_active(db: Session, model):
    return db.query(model).filter(model.is_active == True).order_by(model.id.desc()).all()


@router.post("/business-units", response_model=BusinessUnitSchema, status_code=201)
def create_business_unit(data: BusinessUnitCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    _active_company(db, data.company_id)
    return _create_org_master(db, BusinessUnit, data)


@router.get("/business-units", response_model=List[BusinessUnitSchema])
def list_business_units(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return _list_active(db, BusinessUnit)


@router.post("/cost-centers", response_model=CostCenterSchema, status_code=201)
def create_cost_center(data: CostCenterCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    _active_company(db, data.company_id)
    return _create_org_master(db, CostCenter, data)


@router.get("/cost-centers", response_model=List[CostCenterSchema])
def list_cost_centers(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return _list_active(db, CostCenter)


@router.post("/locations", response_model=WorkLocationSchema, status_code=201)
def create_work_location(data: WorkLocationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    _active_company(db, data.company_id)
    return _create_org_master(db, WorkLocation, data)


@router.get("/locations", response_model=List[WorkLocationSchema])
def list_work_locations(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return _list_active(db, WorkLocation)


@router.post("/grade-bands", response_model=GradeBandSchema, status_code=201)
def create_grade_band(data: GradeBandCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    return _create_org_master(db, GradeBand, data)


@router.get("/grade-bands", response_model=List[GradeBandSchema])
def list_grade_bands(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return _list_active(db, GradeBand)


@router.post("/job-families", response_model=JobFamilySchema, status_code=201)
def create_job_family(data: JobFamilyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    return _create_org_master(db, JobFamily, data)


@router.get("/job-families", response_model=List[JobFamilySchema])
def list_job_families(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return _list_active(db, JobFamily)


@router.post("/job-profiles", response_model=JobProfileSchema, status_code=201)
def create_job_profile(data: JobProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    return _create_org_master(db, JobProfile, data)


@router.get("/job-profiles", response_model=List[JobProfileSchema])
def list_job_profiles(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return _list_active(db, JobProfile)


@router.post("/positions", response_model=PositionSchema, status_code=201)
def create_position(data: PositionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    _active_company(db, data.company_id)
    position = _create_org_master(db, Position, data)
    return position


@router.get("/positions", response_model=List[PositionSchema])
def list_positions(status_filter: Optional[str] = Query(None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    query = db.query(Position).filter(Position.is_active == True)
    if status_filter:
        query = query.filter(Position.status == status_filter)
    return query.order_by(Position.position_code).all()


@router.get("/org-chart")
def org_chart(
    department_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    grade_band_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    query = db.query(Position).filter(Position.is_active == True)
    if department_id:
        query = query.filter(Position.department_id == department_id)
    if location_id:
        query = query.filter(Position.location_id == location_id)
    if grade_band_id:
        query = query.filter(Position.grade_band_id == grade_band_id)
    positions = query.order_by(Position.manager_position_id.nullsfirst(), Position.position_code).all()

    employee_ids = [item.incumbent_employee_id for item in positions if item.incumbent_employee_id]
    employees = {
        item.id: item for item in db.query(Employee).filter(
            Employee.id.in_(employee_ids or [0]),
            Employee.deleted_at.is_(None),
        ).all()
    }
    departments = {item.id: item.name for item in db.query(Department).all()}
    locations = {item.id: item.name for item in db.query(WorkLocation).all()}
    grade_bands = {item.id: item.name for item in db.query(GradeBand).all()}
    designations = {item.id: item.name for item in db.query(Designation).all()}

    return [
        {
            "position_id": item.id,
            "position_code": item.position_code,
            "title": item.title,
            "manager_position_id": item.manager_position_id,
            "incumbent_employee_id": item.incumbent_employee_id,
            "employee_name": f"{employees[item.incumbent_employee_id].first_name} {employees[item.incumbent_employee_id].last_name}" if item.incumbent_employee_id in employees else None,
            "employee_code": employees[item.incumbent_employee_id].employee_id if item.incumbent_employee_id in employees else None,
            "profile_photo_url": employees[item.incumbent_employee_id].profile_photo_url if item.incumbent_employee_id in employees else None,
            "department_id": item.department_id,
            "department_name": departments.get(item.department_id),
            "location_id": item.location_id,
            "location_name": locations.get(item.location_id),
            "grade_band_id": item.grade_band_id,
            "grade_band_name": grade_bands.get(item.grade_band_id),
            "designation_name": designations.get(item.designation_id),
            "status": item.status,
            "is_vacant": not item.incumbent_employee_id or item.status.lower() == "vacant",
        }
        for item in positions
    ]


@router.get("/manager-hierarchy/validate")
def validate_manager_hierarchy(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    errors = []
    positions = {item.id: item.manager_position_id for item in db.query(Position).filter(Position.is_active == True).all()}
    for position_id in positions:
        seen = set()
        current = position_id
        while current:
            if current in seen:
                errors.append({"position_id": position_id, "error": "Manager position cycle detected"})
                break
            seen.add(current)
            current = positions.get(current)
    return {"valid": not errors, "errors": errors}


@router.post("/headcount-plans", response_model=HeadcountPlanSchema, status_code=201)
def create_headcount_plan(data: HeadcountPlanCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    _active_company(db, data.company_id)
    return _create_org_master(db, HeadcountPlan, data)


@router.get("/headcount-plans", response_model=List[HeadcountPlanSchema])
def list_headcount_plans(financial_year: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    query = db.query(HeadcountPlan)
    if financial_year:
        query = query.filter(HeadcountPlan.financial_year == financial_year)
    return query.order_by(HeadcountPlan.id.desc()).all()


@router.put("/headcount-plans/{plan_id}/approve", response_model=HeadcountPlanSchema)
def approve_headcount_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    plan = db.query(HeadcountPlan).filter(HeadcountPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Headcount plan not found")
    plan.status = "Approved"
    plan.approved_by = current_user.id
    plan.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(plan)
    return plan


# Dynamic company routes must stay after the static organization routes above.
@router.get("/{company_id}", response_model=CompanySchema)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanySchema)
def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    _ensure_company_unique(db, data, exclude_id=company_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(company, k, v)
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/logo")
async def upload_company_logo(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    company = db.query(Company).filter(Company.id == company_id, Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or WebP logos are allowed")
    upload_path = os.path.join(settings.UPLOAD_DIR, "company_logos")
    os.makedirs(upload_path, exist_ok=True)
    filename = f"{company_id}_{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(upload_path, filename)
    with open(file_path, "wb") as target:
        shutil.copyfileobj(file.file, target)
    company.logo_url = f"/uploads/company_logos/{filename}"
    db.commit()
    return {"url": company.logo_url}


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.is_active = False
    db.commit()
    return {"message": "Company deactivated"}
