from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text
from sqlalchemy.orm import relationship as orm_relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class BenefitPlan(Base):
    __tablename__ = "benefit_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    plan_type = Column(String(50), nullable=False, index=True)  # Group Health, NPS, Flexi Benefit, Insurance, ESOP
    provider_name = Column(String(150))
    policy_number = Column(String(100))
    description = Column(Text)
    employer_contribution = Column(Numeric(12, 2), default=0)
    employee_contribution = Column(Numeric(12, 2), default=0)
    taxable = Column(Boolean, default=False)
    payroll_component_code = Column(String(50))
    effective_from = Column(Date)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmployeeBenefitEnrollment(Base):
    __tablename__ = "employee_benefit_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    benefit_plan_id = Column(Integer, ForeignKey("benefit_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    coverage_level = Column(String(80), default="Self")
    enrolled_amount = Column(Numeric(12, 2), default=0)
    employee_contribution = Column(Numeric(12, 2), default=0)
    employer_contribution = Column(Numeric(12, 2), default=0)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    status = Column(String(30), default="Active", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = orm_relationship("Employee")
    plan = orm_relationship("BenefitPlan")


class BenefitEnrollmentWindow(Base):
    __tablename__ = "benefit_enrollment_windows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    plan_type = Column(String(50), nullable=True, index=True)
    description = Column(Text)
    status = Column(String(30), default="Open", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BenefitDependent(Base):
    __tablename__ = "benefit_dependents"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id = Column(Integer, ForeignKey("employee_benefit_enrollments.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(150), nullable=False)
    relationship = Column(String(50), nullable=False)
    date_of_birth = Column(Date)
    gender = Column(String(20))
    identity_number = Column(String(80))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = orm_relationship("Employee")
    enrollment = orm_relationship("EmployeeBenefitEnrollment")


class FlexiBenefitPolicy(Base):
    __tablename__ = "flexi_benefit_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    component_code = Column(String(50), nullable=False, index=True)
    monthly_limit = Column(Numeric(12, 2), default=0)
    annual_limit = Column(Numeric(12, 2), default=0)
    proof_required = Column(Boolean, default=True)
    taxable_if_unclaimed = Column(Boolean, default=True)
    carry_forward_allowed = Column(Boolean, default=False)
    effective_from = Column(Date)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmployeeFlexiBenefitAllocation(Base):
    __tablename__ = "employee_flexi_benefit_allocations"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("flexi_benefit_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    allocated_amount = Column(Numeric(12, 2), nullable=False)
    claimed_amount = Column(Numeric(12, 2), default=0)
    taxable_fallback_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(30), default="Active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = orm_relationship("Employee")
    policy = orm_relationship("FlexiBenefitPolicy")


class BenefitPayrollDeduction(Base):
    __tablename__ = "benefit_payroll_deductions"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("employee_benefit_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    employee_amount = Column(Numeric(12, 2), default=0)
    employer_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(30), default="Pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    enrollment = orm_relationship("EmployeeBenefitEnrollment")
    employee = orm_relationship("Employee")


class BenefitClaim(Base):
    __tablename__ = "benefit_claims"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    benefit_plan_id = Column(Integer, ForeignKey("benefit_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    policy_id = Column(Integer, ForeignKey("flexi_benefit_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    claim_type = Column(String(60), nullable=False, index=True)
    claim_date = Column(Date, nullable=False)
    claim_amount = Column(Numeric(12, 2), nullable=False)
    approved_amount = Column(Numeric(12, 2), default=0)
    taxable_amount = Column(Numeric(12, 2), default=0)
    tax_exempt_amount = Column(Numeric(12, 2), default=0)
    receipt_url = Column(String(500))
    status = Column(String(30), default="Submitted", index=True)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(Text)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = orm_relationship("Employee")
    plan = orm_relationship("BenefitPlan")
    policy = orm_relationship("FlexiBenefitPolicy")


class ESOPPlan(Base):
    __tablename__ = "esop_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    plan_code = Column(String(50), unique=True, nullable=False, index=True)
    grant_currency = Column(String(10), default="INR")
    exercise_price = Column(Numeric(12, 2), default=0)
    vesting_frequency = Column(String(30), default="Annual")
    cliff_months = Column(Integer, default=12)
    total_vesting_months = Column(Integer, default=48)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ESOPGrant(Base):
    __tablename__ = "esop_grants"

    id = Column(Integer, primary_key=True, index=True)
    esop_plan_id = Column(Integer, ForeignKey("esop_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    grant_date = Column(Date, nullable=False)
    granted_units = Column(Numeric(14, 2), nullable=False)
    vested_units = Column(Numeric(14, 2), default=0)
    exercised_units = Column(Numeric(14, 2), default=0)
    forfeited_units = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Active", index=True)
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = orm_relationship("ESOPPlan")
    employee = orm_relationship("Employee")


class ESOPVestingSchedule(Base):
    __tablename__ = "esop_vesting_schedules"

    id = Column(Integer, primary_key=True, index=True)
    grant_id = Column(Integer, ForeignKey("esop_grants.id", ondelete="CASCADE"), nullable=False, index=True)
    vesting_date = Column(Date, nullable=False, index=True)
    units = Column(Numeric(14, 2), nullable=False)
    status = Column(String(30), default="Scheduled", index=True)
    vested_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    grant = orm_relationship("ESOPGrant")
