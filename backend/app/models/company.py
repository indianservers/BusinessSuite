from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    legal_name = Column(String(200))
    registration_number = Column(String(100))
    cin_number = Column(String(30))
    pan_number = Column(String(20))
    tan_number = Column(String(20))
    gstin = Column(String(20))
    website = Column(String(200))
    email = Column(String(100))
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100), default="India")
    pincode = Column(String(20))
    logo_url = Column(String(500))
    working_days_per_week = Column(Integer, default=5)
    fiscal_year_start_month = Column(Integer, default=4)
    default_timezone = Column(String(80), default="Asia/Kolkata")
    default_currency = Column(String(10), default="INR")
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    branches = relationship("Branch", back_populates="company", cascade="all, delete-orphan", foreign_keys="Branch.company_id")


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(20))
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(Text)
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100), default="India")
    pincode = Column(String(20))
    phone = Column(String(20))
    email = Column(String(100))
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("Company", back_populates="branches", foreign_keys=[company_id])
    departments = relationship("Department", back_populates="branch", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="branch")


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True)
    head_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL", use_alter=True), nullable=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("Company", foreign_keys=[company_id])
    parent = relationship("BusinessUnit", remote_side=[id])


class CostCenter(Base):
    __tablename__ = "cost_centers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL", use_alter=True), nullable=True)
    budget_amount = Column(Numeric(14, 2), default=0)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("Company", foreign_keys=[company_id])
    business_unit = relationship("BusinessUnit")


class WorkLocation(Base):
    __tablename__ = "work_locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    location_type = Column(String(50), default="Office")
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100), default="India")
    description = Column(Text)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    radius_meters = Column(Integer, default=200)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("Company", foreign_keys=[company_id])
    branch = relationship("Branch")


class GradeBand(Base):
    __tablename__ = "grade_bands"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    description = Column(Text)
    level = Column(Integer, default=1)
    min_ctc = Column(Numeric(14, 2))
    max_ctc = Column(Numeric(14, 2))
    currency = Column(String(10), default="INR")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class JobFamily(Base):
    __tablename__ = "job_families"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobProfile(Base):
    __tablename__ = "job_profiles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    job_family_id = Column(Integer, ForeignKey("job_families.id", ondelete="SET NULL"), nullable=True, index=True)
    grade_band_id = Column(Integer, ForeignKey("grade_bands.id", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(Text)
    responsibilities = Column(Text)
    required_skills_json = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_family = relationship("JobFamily")
    grade_band = relationship("GradeBand")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    position_code = Column(String(50), nullable=False, unique=True, index=True)
    title = Column(String(150), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(Text)
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("work_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True, index=True)
    job_profile_id = Column(Integer, ForeignKey("job_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    grade_band_id = Column(Integer, ForeignKey("grade_bands.id", ondelete="SET NULL"), nullable=True, index=True)
    manager_position_id = Column(Integer, ForeignKey("positions.id", ondelete="SET NULL"), nullable=True)
    incumbent_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    status = Column(String(30), default="Vacant", index=True)
    budgeted_ctc = Column(Numeric(14, 2))
    effective_from = Column(Date)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("Company", foreign_keys=[company_id])
    business_unit = relationship("BusinessUnit")
    cost_center = relationship("CostCenter")
    location = relationship("WorkLocation")
    manager_position = relationship("Position", remote_side=[id])


class HeadcountPlan(Base):
    __tablename__ = "headcount_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    financial_year = Column(String(20), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    planned_headcount = Column(Integer, default=0)
    approved_headcount = Column(Integer, default=0)
    planned_budget = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Draft", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    business_unit = relationship("BusinessUnit")


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(20))
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    head_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL", use_alter=True), nullable=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    branch = relationship("Branch", back_populates="departments")
    designations = relationship("Designation", back_populates="department", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="department", foreign_keys="Employee.department_id")


class Designation(Base):
    __tablename__ = "designations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    code = Column(String(20))
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    grade = Column(String(20))
    level = Column(Integer, default=1)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    department = relationship("Department", back_populates="designations")
    employees = relationship("Employee", back_populates="designation")
