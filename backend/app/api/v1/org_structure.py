from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import RequirePermission, get_current_user, get_db
from app.crud.crud_org_structure import OrgStructureCRUD, to_org_response
from app.models.company import (
    Branch,
    BusinessUnit,
    CostCenter,
    Department,
    Designation,
    GradeBand,
    Position,
    WorkLocation,
)
from app.models.user import User
from app.schemas.org_structure import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    BusinessUnitCreate,
    BusinessUnitResponse,
    BusinessUnitUpdate,
    CostCenterCreate,
    CostCenterResponse,
    CostCenterUpdate,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DesignationCreate,
    DesignationResponse,
    DesignationUpdate,
    GradeBandCreate,
    GradeBandResponse,
    GradeBandUpdate,
    LocationCreate,
    LocationResponse,
    LocationUpdate,
    PositionCreate,
    PositionResponse,
    PositionUpdate,
)

router = APIRouter(prefix="/org", tags=["Organization Structure"])


department_crud = OrgStructureCRUD(Department)
designation_crud = OrgStructureCRUD(Designation)
branch_crud = OrgStructureCRUD(Branch)
location_crud = OrgStructureCRUD(WorkLocation)
grade_band_crud = OrgStructureCRUD(GradeBand, company_attr=None)
cost_center_crud = OrgStructureCRUD(CostCenter)
business_unit_crud = OrgStructureCRUD(BusinessUnit)
position_crud = OrgStructureCRUD(Position, name_attr="title", code_attr="position_code")


def _item_or_404(crud: OrgStructureCRUD, db: Session, item_id: int, label: str) -> Any:
    item = crud.get_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return item


def _list(
    crud: OrgStructureCRUD,
    db: Session,
    organization_id: int | None,
    include_inactive: bool,
    *,
    name_attr: str = "name",
    code_attr: str = "code",
) -> list[dict[str, Any]]:
    return [
        to_org_response(item, name_attr=name_attr, code_attr=code_attr)
        for item in crud.get_all(db, organization_id=organization_id, include_inactive=include_inactive)
    ]


def _create(crud: OrgStructureCRUD, db: Session, data: Any, current_user: User, *, name_attr: str = "name", code_attr: str = "code") -> dict[str, Any]:
    item = crud.create(db, data=data.model_dump(), created_by=current_user.id)
    return to_org_response(item, name_attr=name_attr, code_attr=code_attr)


def _update(
    crud: OrgStructureCRUD,
    db: Session,
    item_id: int,
    data: Any,
    label: str,
    *,
    name_attr: str = "name",
    code_attr: str = "code",
) -> dict[str, Any]:
    item = _item_or_404(crud, db, item_id, label)
    item = crud.update(db, item=item, data=data.model_dump(exclude_unset=True))
    return to_org_response(item, name_attr=name_attr, code_attr=code_attr)


def _soft_delete(crud: OrgStructureCRUD, db: Session, item_id: int, label: str) -> dict[str, Any]:
    item = _item_or_404(crud, db, item_id, label)
    crud.soft_delete(db, item=item)
    return {"message": f"{label} deactivated"}


@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(department_crud, db, organization_id, include_inactive)


@router.post("/departments", response_model=DepartmentResponse, status_code=201)
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(department_crud, db, data, current_user)


@router.put("/departments/{item_id}", response_model=DepartmentResponse)
def update_department(item_id: int, data: DepartmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(department_crud, db, item_id, data, "Department")


@router.delete("/departments/{item_id}")
def delete_department(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(department_crud, db, item_id, "Department")


@router.get("/designations", response_model=list[DesignationResponse])
def list_designations(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(designation_crud, db, organization_id, include_inactive)


@router.post("/designations", response_model=DesignationResponse, status_code=201)
def create_designation(data: DesignationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(designation_crud, db, data, current_user)


@router.put("/designations/{item_id}", response_model=DesignationResponse)
def update_designation(item_id: int, data: DesignationUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(designation_crud, db, item_id, data, "Designation")


@router.delete("/designations/{item_id}")
def delete_designation(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(designation_crud, db, item_id, "Designation")


@router.get("/branches", response_model=list[BranchResponse])
def list_branches(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(branch_crud, db, organization_id, include_inactive)


@router.post("/branches", response_model=BranchResponse, status_code=201)
def create_branch(data: BranchCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(branch_crud, db, data, current_user)


@router.put("/branches/{item_id}", response_model=BranchResponse)
def update_branch(item_id: int, data: BranchUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(branch_crud, db, item_id, data, "Branch")


@router.delete("/branches/{item_id}")
def delete_branch(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(branch_crud, db, item_id, "Branch")


@router.get("/locations", response_model=list[LocationResponse])
def list_locations(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(location_crud, db, organization_id, include_inactive)


@router.post("/locations", response_model=LocationResponse, status_code=201)
def create_location(data: LocationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(location_crud, db, data, current_user)


@router.put("/locations/{item_id}", response_model=LocationResponse)
def update_location(item_id: int, data: LocationUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(location_crud, db, item_id, data, "Location")


@router.delete("/locations/{item_id}")
def delete_location(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(location_crud, db, item_id, "Location")


@router.get("/grade-bands", response_model=list[GradeBandResponse])
def list_grade_bands(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(grade_band_crud, db, organization_id, include_inactive)


@router.post("/grade-bands", response_model=GradeBandResponse, status_code=201)
def create_grade_band(data: GradeBandCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(grade_band_crud, db, data, current_user)


@router.put("/grade-bands/{item_id}", response_model=GradeBandResponse)
def update_grade_band(item_id: int, data: GradeBandUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(grade_band_crud, db, item_id, data, "Grade band")


@router.delete("/grade-bands/{item_id}")
def delete_grade_band(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(grade_band_crud, db, item_id, "Grade band")


@router.get("/cost-centers", response_model=list[CostCenterResponse])
def list_cost_centers(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(cost_center_crud, db, organization_id, include_inactive)


@router.post("/cost-centers", response_model=CostCenterResponse, status_code=201)
def create_cost_center(data: CostCenterCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(cost_center_crud, db, data, current_user)


@router.put("/cost-centers/{item_id}", response_model=CostCenterResponse)
def update_cost_center(item_id: int, data: CostCenterUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(cost_center_crud, db, item_id, data, "Cost center")


@router.delete("/cost-centers/{item_id}")
def delete_cost_center(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(cost_center_crud, db, item_id, "Cost center")


@router.get("/business-units", response_model=list[BusinessUnitResponse])
def list_business_units(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(business_unit_crud, db, organization_id, include_inactive)


@router.post("/business-units", response_model=BusinessUnitResponse, status_code=201)
def create_business_unit(data: BusinessUnitCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(business_unit_crud, db, data, current_user)


@router.put("/business-units/{item_id}", response_model=BusinessUnitResponse)
def update_business_unit(item_id: int, data: BusinessUnitUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(business_unit_crud, db, item_id, data, "Business unit")


@router.delete("/business-units/{item_id}")
def delete_business_unit(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(business_unit_crud, db, item_id, "Business unit")


@router.get("/positions", response_model=list[PositionResponse])
def list_positions(
    organization_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list(position_crud, db, organization_id, include_inactive, name_attr="title", code_attr="position_code")


@router.post("/positions", response_model=PositionResponse, status_code=201)
def create_position(data: PositionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _create(position_crud, db, data, current_user, name_attr="title", code_attr="position_code")


@router.put("/positions/{item_id}", response_model=PositionResponse)
def update_position(item_id: int, data: PositionUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _update(position_crud, db, item_id, data, "Position", name_attr="title", code_attr="position_code")


@router.delete("/positions/{item_id}")
def delete_position(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("hr_admin"))):
    return _soft_delete(position_crud, db, item_id, "Position")
