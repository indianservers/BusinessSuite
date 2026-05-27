from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, EmailStr


class CompanyBase(BaseModel):
    name: str
    legal_name: Optional[str] = None
    registration_number: Optional[str] = None
    cin_number: Optional[str] = None
    pan_number: Optional[str] = None
    tan_number: Optional[str] = None
    gstin: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    pincode: Optional[str] = None
    logo_url: Optional[str] = None
    working_days_per_week: int = 5
    fiscal_year_start_month: int = 4
    default_timezone: str = "Asia/Kolkata"
    default_currency: str = "INR"


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(CompanyBase):
    name: Optional[str] = None


class CompanySchema(CompanyBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class BranchBase(BaseModel):
    name: str
    code: Optional[str] = None
    company_id: int
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BranchBase):
    name: Optional[str] = None
    company_id: Optional[int] = None


class BranchSchema(BranchBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class DepartmentBase(BaseModel):
    name: str
    code: Optional[str] = None
    branch_id: int
    description: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(DepartmentBase):
    name: Optional[str] = None
    branch_id: Optional[int] = None


class DepartmentSchema(DepartmentBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class DesignationBase(BaseModel):
    name: str
    code: Optional[str] = None
    department_id: int
    grade: Optional[str] = None
    level: int = 1
    description: Optional[str] = None


class DesignationCreate(DesignationBase):
    pass


class DesignationUpdate(DesignationBase):
    name: Optional[str] = None
    department_id: Optional[int] = None


class DesignationSchema(DesignationBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class BusinessUnitCreate(BaseModel):
    name: str
    code: str
    company_id: int
    parent_id: Optional[int] = None
    head_employee_id: Optional[int] = None
    description: Optional[str] = None


class BusinessUnitSchema(BusinessUnitCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class CostCenterCreate(BaseModel):
    name: str
    code: str
    company_id: int
    business_unit_id: Optional[int] = None
    owner_employee_id: Optional[int] = None
    budget_amount: Decimal = Decimal("0")


class CostCenterSchema(CostCenterCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class WorkLocationCreate(BaseModel):
    name: str
    code: str
    company_id: int
    branch_id: Optional[int] = None
    location_type: str = "Office"
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    radius_meters: int = 200


class WorkLocationSchema(WorkLocationCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class GradeBandCreate(BaseModel):
    name: str
    code: str
    level: int = 1
    min_ctc: Optional[Decimal] = None
    max_ctc: Optional[Decimal] = None
    currency: str = "INR"


class GradeBandSchema(GradeBandCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class JobFamilyCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class JobFamilySchema(JobFamilyCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class JobProfileCreate(BaseModel):
    title: str
    code: str
    job_family_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    required_skills_json: Optional[Any] = None


class JobProfileSchema(JobProfileCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class PositionCreate(BaseModel):
    position_code: str
    title: str
    company_id: int
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
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class PositionSchema(PositionCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class HeadcountPlanCreate(BaseModel):
    name: str
    financial_year: str
    company_id: int
    business_unit_id: Optional[int] = None
    department_id: Optional[int] = None
    planned_headcount: int = 0
    approved_headcount: int = 0
    planned_budget: Decimal = Decimal("0")
    status: str = "Draft"


class HeadcountPlanSchema(HeadcountPlanCreate):
    id: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True
