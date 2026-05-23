from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, EmailStr


class EmployeeEducationBase(BaseModel):
    degree: str
    specialization: Optional[str] = None
    institution: Optional[str] = None
    board_university: Optional[str] = None
    pass_year: Optional[int] = None
    percentage_cgpa: Optional[Decimal] = None
    document_url: Optional[str] = None


class EmployeeEducationCreate(EmployeeEducationBase):
    pass


class EmployeeEducationSchema(EmployeeEducationBase):
    id: int
    employee_id: int

    class Config:
        from_attributes = True


class EmployeeExperienceBase(BaseModel):
    company_name: str
    designation: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    is_current: bool = False
    responsibilities: Optional[str] = None
    relieving_letter_url: Optional[str] = None


class EmployeeExperienceCreate(EmployeeExperienceBase):
    pass


class EmployeeExperienceSchema(EmployeeExperienceBase):
    id: int
    employee_id: int

    class Config:
        from_attributes = True


class EmployeeSkillBase(BaseModel):
    skill_name: str
    proficiency: Optional[str] = None
    years_experience: Optional[Decimal] = None


class EmployeeSkillCreate(EmployeeSkillBase):
    pass


class EmployeeSkillSchema(EmployeeSkillBase):
    id: int
    employee_id: int

    class Config:
        from_attributes = True


class EmployeeDocumentBase(BaseModel):
    document_type: str
    document_name: Optional[str] = None
    document_number: Optional[str] = None
    file_url: Optional[str] = None
    expiry_date: Optional[date] = None


class EmployeeDocumentCreate(EmployeeDocumentBase):
    pass


class EmployeeDocumentSchema(EmployeeDocumentBase):
    id: int
    employee_id: int
    verification_status: str = "Pending"
    is_verified: bool
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    verifier_name: Optional[str] = None
    verifier_company: Optional[str] = None
    verification_notes: Optional[str] = None

    class Config:
        from_attributes = True


class EmployeeDocumentVerificationUpdate(BaseModel):
    verification_status: str
    verifier_name: Optional[str] = None
    verifier_company: Optional[str] = None
    verification_notes: Optional[str] = None


class EmployeeLifecycleEventBase(BaseModel):
    event_type: str
    event_date: date
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    from_branch_id: Optional[int] = None
    to_branch_id: Optional[int] = None
    from_department_id: Optional[int] = None
    to_department_id: Optional[int] = None
    from_designation_id: Optional[int] = None
    to_designation_id: Optional[int] = None
    from_manager_id: Optional[int] = None
    to_manager_id: Optional[int] = None
    reason: Optional[str] = None
    remarks: Optional[str] = None


class EmployeeLifecycleEventCreate(BaseModel):
    event_type: str
    event_date: date
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    to_status: Optional[str] = None
    to_branch_id: Optional[int] = None
    to_department_id: Optional[int] = None
    to_designation_id: Optional[int] = None
    to_manager_id: Optional[int] = None
    reason: Optional[str] = None
    remarks: Optional[str] = None
    apply_to_employee: bool = False


class EmployeeLifecycleEventSchema(EmployeeLifecycleEventBase):
    id: int
    employee_id: int
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class EmployeeBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    marital_status: Optional[str] = None
    blood_group: Optional[str] = None
    nationality: str = "Indian"
    religion: Optional[str] = None
    category: Optional[str] = None
    gender_identity: Optional[str] = None
    disability_status: Optional[str] = None
    veteran_status: Optional[str] = None
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    phone_number: Optional[str] = None
    alternate_phone: Optional[str] = None
    office_extension: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    present_address: Optional[str] = None
    permanent_address: Optional[str] = None
    present_city: Optional[str] = None
    present_state: Optional[str] = None
    present_pincode: Optional[str] = None
    permanent_city: Optional[str] = None
    permanent_state: Optional[str] = None
    permanent_pincode: Optional[str] = None
    date_of_joining: date
    date_of_confirmation: Optional[date] = None
    branch_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    location_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    position_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None
    employment_type: str = "Full-time"
    worker_type: Optional[str] = "Employee"
    status: str = "Active"
    work_location: str = "Office"
    shift_id: Optional[int] = None
    probation_period_months: int = 6
    desk_code: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    manager_chain_path: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    account_number: Optional[str] = None
    account_type: str = "Savings"
    ifsc_code: Optional[str] = None
    pan_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    uan_number: Optional[str] = None
    pf_number: Optional[str] = None
    esic_number: Optional[str] = None
    salary_currency: str = "INR"
    preferred_display_name: Optional[str] = None
    directory_visibility: str = "public"
    skills_tags: Optional[str] = None
    profile_completeness: int = 0
    bio: Optional[str] = None
    interests: Optional[str] = None
    research_work: Optional[str] = None
    family_information: Optional[str] = None
    health_information: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    employee_id: Optional[str] = None  # auto-generated if not provided
    create_user_account: bool = True
    user_email: Optional[EmailStr] = None
    user_password: Optional[str] = None


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    marital_status: Optional[str] = None
    blood_group: Optional[str] = None
    nationality: Optional[str] = None
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    phone_number: Optional[str] = None
    alternate_phone: Optional[str] = None
    office_extension: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    present_address: Optional[str] = None
    permanent_address: Optional[str] = None
    present_city: Optional[str] = None
    present_state: Optional[str] = None
    present_pincode: Optional[str] = None
    permanent_city: Optional[str] = None
    permanent_state: Optional[str] = None
    permanent_pincode: Optional[str] = None
    branch_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    location_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    position_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None
    employment_type: Optional[str] = None
    worker_type: Optional[str] = None
    status: Optional[str] = None
    work_location: Optional[str] = None
    shift_id: Optional[int] = None
    desk_code: Optional[str] = None
    timezone: Optional[str] = None
    manager_chain_path: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    account_number: Optional[str] = None
    account_type: Optional[str] = None
    ifsc_code: Optional[str] = None
    pan_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    uan_number: Optional[str] = None
    salary_currency: Optional[str] = None
    profile_photo_url: Optional[str] = None
    preferred_display_name: Optional[str] = None
    directory_visibility: Optional[str] = None
    skills_tags: Optional[str] = None
    profile_completeness: Optional[int] = None
    bio: Optional[str] = None
    interests: Optional[str] = None
    research_work: Optional[str] = None
    family_information: Optional[str] = None
    health_information: Optional[str] = None


class EmployeeListSchema(BaseModel):
    id: int
    employee_id: str
    first_name: str
    last_name: str
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    phone_number: Optional[str] = None
    office_extension: Optional[str] = None
    designation_id: Optional[int] = None
    department_id: Optional[int] = None
    branch_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    location_id: Optional[int] = None
    grade_band_id: Optional[int] = None
    position_id: Optional[int] = None
    employment_type: str
    status: str
    date_of_joining: date
    profile_photo_url: Optional[str] = None
    salary_currency: str = "INR"
    preferred_display_name: Optional[str] = None
    directory_visibility: str = "public"
    skills_tags: Optional[str] = None
    profile_completeness: int = 0
    desk_code: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    manager_chain_path: Optional[str] = None

    class Config:
        from_attributes = True


class EmployeeSchema(EmployeeBase):
    id: int
    employee_id: str
    user_id: Optional[int] = None
    profile_photo_url: Optional[str] = None
    educations: List[EmployeeEducationSchema] = []
    experiences: List[EmployeeExperienceSchema] = []
    skills: List[EmployeeSkillSchema] = []
    documents: List[EmployeeDocumentSchema] = []
    lifecycle_events: List[EmployeeLifecycleEventSchema] = []

    class Config:
        from_attributes = True


class EmployeeChangeRequestCreate(BaseModel):
    employee_id: int
    request_type: str
    effective_date: Optional[date] = None
    field_changes_json: Any
    reason: Optional[str] = None
    field_name: Optional[str] = None
    document_path: Optional[str] = None


class EmployeeChangeRequestReview(BaseModel):
    status: str
    review_remarks: Optional[str] = None
    apply_changes: bool = True


class EmployeeChangeRequestSchema(EmployeeChangeRequestCreate):
    id: int
    organization_id: Optional[int] = None
    old_value_json: Optional[Any] = None
    new_value_json: Optional[Any] = None
    status: str
    requested_by: Optional[int] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_remarks: Optional[str] = None
    created_at: datetime
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    current_values_json: Optional[Any] = None

    class Config:
        from_attributes = True
