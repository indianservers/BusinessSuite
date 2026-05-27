from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class OrgMasterBase(BaseModel):
    organization_id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True


class OrgMasterUpdate(BaseModel):
    organization_id: Optional[int] = None
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class OrgMasterResponse(BaseModel):
    id: int
    organization_id: Optional[int] = None
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None


class DepartmentCreate(OrgMasterBase):
    branch_id: int


class DepartmentUpdate(OrgMasterUpdate):
    branch_id: Optional[int] = None


class DepartmentResponse(OrgMasterResponse):
    branch_id: int


class DesignationCreate(OrgMasterBase):
    department_id: int


class DesignationUpdate(OrgMasterUpdate):
    department_id: Optional[int] = None


class DesignationResponse(OrgMasterResponse):
    department_id: int


class BranchCreate(OrgMasterBase):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class BranchUpdate(OrgMasterUpdate):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class BranchResponse(OrgMasterResponse):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class LocationCreate(OrgMasterBase):
    branch_id: Optional[int] = None
    location_type: str = "Office"
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    radius_meters: int = 200


class LocationUpdate(OrgMasterUpdate):
    branch_id: Optional[int] = None
    location_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    radius_meters: Optional[int] = None


class LocationResponse(OrgMasterResponse):
    branch_id: Optional[int] = None
    location_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    radius_meters: Optional[int] = None


class GradeBandCreate(OrgMasterBase):
    level: int = 1
    min_ctc: Optional[Decimal] = None
    max_ctc: Optional[Decimal] = None
    currency: str = "INR"


class GradeBandUpdate(OrgMasterUpdate):
    level: Optional[int] = None
    min_ctc: Optional[Decimal] = None
    max_ctc: Optional[Decimal] = None
    currency: Optional[str] = None


class GradeBandResponse(OrgMasterResponse):
    level: Optional[int] = None
    min_ctc: Optional[Decimal] = None
    max_ctc: Optional[Decimal] = None
    currency: Optional[str] = None


class CostCenterCreate(OrgMasterBase):
    business_unit_id: Optional[int] = None
    owner_employee_id: Optional[int] = None
    budget_amount: Decimal = Decimal("0")


class CostCenterUpdate(OrgMasterUpdate):
    business_unit_id: Optional[int] = None
    owner_employee_id: Optional[int] = None
    budget_amount: Optional[Decimal] = None


class CostCenterResponse(OrgMasterResponse):
    business_unit_id: Optional[int] = None
    owner_employee_id: Optional[int] = None
    budget_amount: Optional[Decimal] = None


class BusinessUnitCreate(OrgMasterBase):
    parent_id: Optional[int] = None
    head_employee_id: Optional[int] = None


class BusinessUnitUpdate(OrgMasterUpdate):
    parent_id: Optional[int] = None
    head_employee_id: Optional[int] = None


class BusinessUnitResponse(OrgMasterResponse):
    parent_id: Optional[int] = None
    head_employee_id: Optional[int] = None


class PositionCreate(OrgMasterBase):
    business_unit_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    location_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    job_profile_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    manager_position_id: Optional[int] = None
    incumbent_employee_id: Optional[int] = None
    status: str = "Vacant"
    budgeted_ctc: Optional[Decimal] = None


class PositionUpdate(OrgMasterUpdate):
    business_unit_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    location_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    job_profile_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    manager_position_id: Optional[int] = None
    incumbent_employee_id: Optional[int] = None
    status: Optional[str] = None
    budgeted_ctc: Optional[Decimal] = None


class PositionResponse(OrgMasterResponse):
    business_unit_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    location_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    job_profile_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    manager_position_id: Optional[int] = None
    incumbent_employee_id: Optional[int] = None
    status: Optional[str] = None
    budgeted_ctc: Optional[Decimal] = None
