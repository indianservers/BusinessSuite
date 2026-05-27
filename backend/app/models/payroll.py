from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class SalaryComponent(Base):
    __tablename__ = "salary_components"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(30), unique=True, nullable=False)
    component_type = Column(String(20), nullable=False)  # Earning, Deduction, Statutory
    calculation_type = Column(String(20), default="Fixed")  # Fixed, Percentage, Formula
    amount = Column(Numeric(12, 2), default=0)
    percentage_of = Column(String(50))  # basic, gross, ctc
    formula_expression = Column(Text)
    payslip_group = Column(String(50), default="Earnings")  # Earnings, Deductions, Employer Contributions, Reimbursements
    display_sequence = Column(Integer, default=100)
    is_taxable = Column(Boolean, default=True)
    is_pf_applicable = Column(Boolean, default=False)
    is_esi_applicable = Column(Boolean, default=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("salary_component_categories.id", ondelete="SET NULL"), nullable=True)
    earning_type = Column(String(50))
    deduction_timing = Column(String(50))
    pay_frequency = Column(String(30), default="Monthly")
    taxable_treatment = Column(String(50), default="Taxable")
    exemption_section = Column(String(50))
    appears_in_ctc = Column(Boolean, default=True)
    appears_in_payslip = Column(Boolean, default=True)
    pro_rata_rule = Column(String(50), default="Calendar Days")
    lop_applicable = Column(Boolean, default=True)
    pf_wage_flag = Column(Boolean, default=False)
    esi_wage_flag = Column(Boolean, default=False)
    gratuity_wage_flag = Column(Boolean, default=False)
    min_amount = Column(Numeric(12, 2))
    max_amount = Column(Numeric(12, 2))
    rounding_rule = Column(String(50), default="Nearest Rupee")
    effective_from = Column(Date)
    effective_to = Column(Date)
    is_currency_fixed = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    category = relationship("SalaryComponentCategory")
    formula_rules = relationship("SalaryComponentFormulaRule", back_populates="component", cascade="all, delete-orphan")


class SalaryComponentCategory(Base):
    __tablename__ = "salary_component_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    code = Column(String(40), nullable=False, unique=True)
    category_type = Column(String(50), nullable=False)  # Earning, Deduction, Statutory, Perquisite
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SalaryComponentFormulaRule(Base):
    __tablename__ = "salary_component_formula_rules"

    id = Column(Integer, primary_key=True, index=True)
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_expression = Column(Text, nullable=False)
    dependency_order = Column(Integer, default=100)
    formula_scope = Column(String(40), default="Salary Preview")
    effective_from = Column(Date)
    effective_to = Column(Date)
    validation_status = Column(String(30), default="Draft", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    component = relationship("SalaryComponent", back_populates="formula_rules")


class SalaryStructure(Base):
    __tablename__ = "salary_structures"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    version = Column(String(20), default="1.0")
    parent_structure_id = Column(Integer, ForeignKey("salary_structures.id", ondelete="SET NULL"), nullable=True)
    effective_from = Column(Date)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    components = relationship("SalaryStructureComponent", back_populates="structure", cascade="all, delete-orphan")
    employee_salaries = relationship("EmployeeSalary", back_populates="structure")


class PayrollPayGroup(Base):
    __tablename__ = "payroll_pay_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    code = Column(String(30), nullable=False, unique=True)
    description = Column(Text)
    pay_frequency = Column(String(30), default="Monthly")
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    state = Column(String(100))
    pay_cycle_day = Column(Integer, default=1)
    pay_date_rule = Column(String(80), default="Last Working Day")
    attendance_cutoff_day = Column(Integer, default=25)
    reimbursement_cutoff_day = Column(Integer, default=25)
    tax_deduction_frequency = Column(String(30), default="Monthly")
    default_tax_regime = Column(String(40), default="NEW")
    rounding_policy = Column(String(60), default="Nearest Rupee")
    include_weekends_in_lop = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollCalendar(Base):
    __tablename__ = "payroll_calendars"

    id = Column(Integer, primary_key=True, index=True)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    payroll_date = Column(Date, nullable=False)
    attendance_cutoff_date = Column(Date)
    status = Column(String(30), default="Open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pay_group = relationship("PayrollPayGroup")


class PayrollStatutoryProfile(Base):
    __tablename__ = "payroll_statutory_profiles"

    id = Column(Integer, primary_key=True, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    pf_establishment_code = Column(String(50))
    pf_signatory = Column(String(120))
    esi_employer_code = Column(String(50))
    pt_registration_number = Column(String(80))
    lwf_registration_number = Column(String(80))
    tan_circle = Column(String(80))
    tax_deductor_type = Column(String(80), default="Company")
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"

    id = Column(Integer, primary_key=True, index=True)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    financial_year = Column(String(20), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    attendance_cutoff_at = Column(DateTime(timezone=True))
    input_cutoff_at = Column(DateTime(timezone=True))
    payroll_date = Column(Date, nullable=False)
    status = Column(String(30), default="Open", index=True)
    locked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pay_group = relationship("PayrollPayGroup")


class SalaryTemplate(Base):
    __tablename__ = "salary_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    grade = Column(String(80))
    location = Column(String(120))
    description = Column(Text)
    residual_component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="SET NULL"), nullable=True)
    effective_from = Column(Date)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    components = relationship("SalaryTemplateComponent", back_populates="template", cascade="all, delete-orphan")


class SalaryTemplateComponent(Base):
    __tablename__ = "salary_template_components"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("salary_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), default=0)
    percentage = Column(Numeric(8, 4))
    formula_expression = Column(Text)
    min_amount = Column(Numeric(12, 2))
    max_amount = Column(Numeric(12, 2))
    is_employee_editable = Column(Boolean, default=False)
    order_sequence = Column(Integer, default=100)

    template = relationship("SalaryTemplate", back_populates="components")
    component = relationship("SalaryComponent")


class EmployeeSalaryTemplateAssignment(Base):
    __tablename__ = "employee_salary_template_assignments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("salary_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    ctc = Column(Numeric(14, 2), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    status = Column(String(30), default="Active", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    template = relationship("SalaryTemplate")


class EmployeeSalaryComponentOverride(Base):
    __tablename__ = "employee_salary_component_overrides"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("employee_salary_template_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="CASCADE"), nullable=False, index=True)
    override_type = Column(String(30), nullable=False)  # Amount, Percentage, Formula
    amount = Column(Numeric(12, 2))
    percentage = Column(Numeric(8, 4))
    formula_expression = Column(Text)
    reason = Column(Text)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    assignment = relationship("EmployeeSalaryTemplateAssignment")
    component = relationship("SalaryComponent")


class TaxRegime(Base):
    __tablename__ = "tax_regimes"

    id = Column(Integer, primary_key=True, index=True)
    country = Column(String(80), default="India", index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    regime_code = Column(String(40), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    is_default = Column(Boolean, default=False, index=True)
    rebate_rules_json = Column(JSON)
    surcharge_rules_json = Column(JSON)
    cess_percent = Column(Numeric(6, 2), default=4)
    standard_deduction_amount = Column(Numeric(12, 2), default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    slabs = relationship("TaxSlab", back_populates="regime", cascade="all, delete-orphan")


class TaxSlab(Base):
    __tablename__ = "tax_slabs"

    id = Column(Integer, primary_key=True, index=True)
    tax_regime_id = Column(Integer, ForeignKey("tax_regimes.id", ondelete="CASCADE"), nullable=False, index=True)
    min_income = Column(Numeric(14, 2), default=0)
    max_income = Column(Numeric(14, 2))
    rate_percent = Column(Numeric(6, 2), default=0)
    fixed_amount = Column(Numeric(14, 2), default=0)
    sequence = Column(Integer, default=1)

    regime = relationship("TaxRegime", back_populates="slabs")


class TaxSection(Base):
    __tablename__ = "tax_sections"

    id = Column(Integer, primary_key=True, index=True)
    section_code = Column(String(40), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    proof_required = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TaxSectionLimit(Base):
    __tablename__ = "tax_section_limits"

    id = Column(Integer, primary_key=True, index=True)
    tax_section_id = Column(Integer, ForeignKey("tax_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    tax_regime_id = Column(Integer, ForeignKey("tax_regimes.id", ondelete="CASCADE"), nullable=True, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    limit_amount = Column(Numeric(14, 2), nullable=False)
    effective_from = Column(Date)
    effective_to = Column(Date)

    section = relationship("TaxSection")
    regime = relationship("TaxRegime")


class EmployeeTaxRegimeElection(Base):
    __tablename__ = "employee_tax_regime_elections"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    tax_regime_id = Column(Integer, ForeignKey("tax_regimes.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_at = Column(DateTime(timezone=True), server_default=func.now())
    locked_at = Column(DateTime(timezone=True))
    locked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    regime = relationship("TaxRegime")


class EmployeeTaxWorksheet(Base):
    __tablename__ = "employee_tax_worksheets"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    tax_regime_id = Column(Integer, ForeignKey("tax_regimes.id", ondelete="SET NULL"), nullable=True, index=True)
    gross_taxable_income = Column(Numeric(14, 2), default=0)
    exemptions = Column(Numeric(14, 2), default=0)
    deductions = Column(Numeric(14, 2), default=0)
    previous_employment_income = Column(Numeric(14, 2), default=0)
    previous_tds = Column(Numeric(14, 2), default=0)
    projected_tax = Column(Numeric(14, 2), default=0)
    monthly_tds = Column(Numeric(14, 2), default=0)
    paid_tds = Column(Numeric(14, 2), default=0)
    balance_tax = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Projected", index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    lines = relationship("EmployeeTaxWorksheetLine", back_populates="worksheet", cascade="all, delete-orphan")


class EmployeeTaxWorksheetLine(Base):
    __tablename__ = "employee_tax_worksheet_lines"

    id = Column(Integer, primary_key=True, index=True)
    worksheet_id = Column(Integer, ForeignKey("employee_tax_worksheets.id", ondelete="CASCADE"), nullable=False, index=True)
    line_type = Column(String(50), nullable=False)
    section_code = Column(String(40))
    description = Column(Text)
    amount = Column(Numeric(14, 2), default=0)
    taxable_amount = Column(Numeric(14, 2), default=0)
    tax_saving_amount = Column(Numeric(14, 2), default=0)

    worksheet = relationship("EmployeeTaxWorksheet", back_populates="lines")


class PreviousEmploymentTaxDetail(Base):
    __tablename__ = "previous_employment_tax_details"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    employer_name = Column(String(180), nullable=False)
    taxable_income = Column(Numeric(14, 2), default=0)
    pf = Column(Numeric(14, 2), default=0)
    professional_tax = Column(Numeric(14, 2), default=0)
    tds_deducted = Column(Numeric(14, 2), default=0)
    proof_url = Column(String(500))
    verified_status = Column(String(30), default="Pending", index=True)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PFRule(Base):
    __tablename__ = "pf_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    wage_ceiling = Column(Numeric(12, 2), default=15000)
    employee_rate = Column(Numeric(6, 2), default=12)
    employer_rate = Column(Numeric(6, 2), default=12)
    eps_rate = Column(Numeric(6, 2), default=8.33)
    edli_rate = Column(Numeric(6, 3), default=0.5)
    admin_charge_rate = Column(Numeric(6, 3), default=0.5)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    rounding_rule = Column(String(50), default="Nearest Rupee")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ESIRule(Base):
    __tablename__ = "esi_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    wage_threshold = Column(Numeric(12, 2), default=21000)
    employee_rate = Column(Numeric(6, 3), default=0.75)
    employer_rate = Column(Numeric(6, 3), default=3.25)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    rounding_rule = Column(String(50), default="Nearest Rupee")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProfessionalTaxSlab(Base):
    __tablename__ = "professional_tax_slabs"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(100), nullable=False, index=True)
    salary_from = Column(Numeric(12, 2), default=0)
    salary_to = Column(Numeric(12, 2))
    employee_amount = Column(Numeric(12, 2), default=0)
    month = Column(Integer)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LWFSlab(Base):
    __tablename__ = "lwf_slabs"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(100), nullable=False, index=True)
    salary_from = Column(Numeric(12, 2), default=0)
    salary_to = Column(Numeric(12, 2))
    employee_amount = Column(Numeric(12, 2), default=0)
    employer_amount = Column(Numeric(12, 2), default=0)
    deduction_month = Column(Integer)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GratuityRule(Base):
    __tablename__ = "gratuity_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    days_per_year = Column(Numeric(6, 2), default=15)
    wage_days_divisor = Column(Numeric(6, 2), default=26)
    min_service_years = Column(Numeric(6, 2), default=5)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    rounding_rule = Column(String(50), default="Nearest Rupee")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmployeeStatutoryProfile(Base):
    __tablename__ = "employee_statutory_profiles"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    uan = Column(String(30))
    pf_join_date = Column(Date)
    pf_exit_date = Column(Date)
    pf_applicable = Column(Boolean, default=True)
    pension_applicable = Column(Boolean, default=True)
    esi_ip_number = Column(String(30))
    esi_applicable = Column(Boolean, default=False)
    pt_state = Column(String(100))
    lwf_applicable = Column(Boolean, default=False)
    nominee_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollStatutoryContributionLine(Base):
    __tablename__ = "payroll_statutory_contribution_lines"

    id = Column(Integer, primary_key=True, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    component = Column(String(40), nullable=False, index=True)
    wage_base = Column(Numeric(12, 2), default=0)
    employee_amount = Column(Numeric(12, 2), default=0)
    employer_amount = Column(Numeric(12, 2), default=0)
    admin_charge = Column(Numeric(12, 2), default=0)
    edli_amount = Column(Numeric(12, 2), default=0)
    rule_id = Column(Integer)
    rule_type = Column(String(40))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_record = relationship("PayrollRecord")


class PayrollAttendanceInput(Base):
    __tablename__ = "payroll_attendance_inputs"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    working_days = Column(Numeric(6, 2), default=0)
    payable_days = Column(Numeric(6, 2), default=0)
    present_days = Column(Numeric(6, 2), default=0)
    paid_leave_days = Column(Numeric(6, 2), default=0)
    unpaid_leave_days = Column(Numeric(6, 2), default=0)
    lop_days = Column(Numeric(6, 2), default=0)
    holiday_days = Column(Numeric(6, 2), default=0)
    weekly_off_days = Column(Numeric(6, 2), default=0)
    ot_hours = Column(Numeric(8, 2), default=0)
    source_status = Column(String(30), default="Draft", index=True)
    locked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    period = relationship("PayrollPeriod")


class LOPAdjustment(Base):
    __tablename__ = "lop_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    adjustment_days = Column(Numeric(6, 2), default=0)
    reason = Column(Text)
    source = Column(String(40), default="Manual", index=True)
    status = Column(String(30), default="Pending", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    period = relationship("PayrollPeriod")


class OvertimePolicy(Base):
    __tablename__ = "overtime_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    wage_base = Column(String(50), default="Basic")
    regular_multiplier = Column(Numeric(6, 2), default=1.5)
    weekend_multiplier = Column(Numeric(6, 2), default=2)
    holiday_multiplier = Column(Numeric(6, 2), default=2)
    min_hours = Column(Numeric(6, 2), default=0)
    max_hours_per_month = Column(Numeric(6, 2))
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="SET NULL"), nullable=True)
    approval_required = Column(Boolean, default=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OvertimePayLine(Base):
    __tablename__ = "overtime_pay_lines"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("overtime_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_overtime_request_id = Column(Integer, ForeignKey("overtime_requests.id", ondelete="SET NULL"), nullable=True)
    ot_date = Column(Date)
    hours = Column(Numeric(8, 2), default=0)
    multiplier = Column(Numeric(6, 2), default=1)
    hourly_rate = Column(Numeric(12, 2), default=0)
    amount = Column(Numeric(12, 2), default=0)
    source = Column(String(40), default="Reconciliation")
    status = Column(String(30), default="Pending", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    period = relationship("PayrollPeriod")
    policy = relationship("OvertimePolicy")


class LeaveEncashmentPolicy(Base):
    __tablename__ = "leave_encashment_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    formula = Column(String(120), default="basic_per_day * days")
    max_days = Column(Numeric(6, 2))
    tax_treatment = Column(String(50), default="Taxable")
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="SET NULL"), nullable=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LeaveEncashmentLine(Base):
    __tablename__ = "leave_encashment_lines"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("leave_encashment_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="SET NULL"), nullable=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    days = Column(Numeric(6, 2), default=0)
    rate_per_day = Column(Numeric(12, 2), default=0)
    amount = Column(Numeric(12, 2), default=0)
    tax_treatment = Column(String(50), default="Taxable")
    status = Column(String(30), default="Pending", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    period = relationship("PayrollPeriod")
    policy = relationship("LeaveEncashmentPolicy")


class LeaveEncashmentRequest(Base):
    __tablename__ = "leave_encashment_requests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    days_to_encash = Column(Numeric(6, 2), nullable=False)
    encashment_rate = Column(Numeric(12, 2), default=0)
    amount = Column(Numeric(12, 2), default=0)
    status = Column(String(30), default="draft", index=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    leave_encashment_line_id = Column(Integer, ForeignKey("leave_encashment_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    remarks = Column(Text)

    employee = relationship("Employee")
    leave_type = relationship("LeaveType")
    payroll_run = relationship("PayrollRun")
    leave_encashment_line = relationship("LeaveEncashmentLine")


class PayrollLWPEntry(Base):
    __tablename__ = "payroll_lwp_entries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_month = Column(String(7), nullable=False, index=True)
    lwp_days = Column(Numeric(6, 2), default=0)
    source = Column(String(40), default="leave", index=True)
    amount_deducted = Column(Numeric(12, 2), default=0)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    payroll_attendance_input_id = Column(Integer, ForeignKey("payroll_attendance_inputs.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee")
    payroll_run = relationship("PayrollRun")
    payroll_attendance_input = relationship("PayrollAttendanceInput")


class StatutoryChallan(Base):
    __tablename__ = "statutory_challans"

    id = Column(Integer, primary_key=True, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    challan_type = Column(String(40), nullable=False, index=True)
    due_date = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Draft", index=True)
    payment_reference = Column(String(120))
    paid_at = Column(DateTime(timezone=True))
    file_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    return_files = relationship("StatutoryReturnFile", back_populates="challan", cascade="all, delete-orphan")


class StatutoryReturnFile(Base):
    __tablename__ = "statutory_return_files"

    id = Column(Integer, primary_key=True, index=True)
    challan_id = Column(Integer, ForeignKey("statutory_challans.id", ondelete="CASCADE"), nullable=False, index=True)
    return_type = Column(String(50), nullable=False, index=True)
    format_version = Column(String(30), default="v1")
    file_url = Column(String(500))
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    validation_status = Column(String(30), default="Pending", index=True)
    validation_errors_json = Column(JSON)

    challan = relationship("StatutoryChallan", back_populates="return_files")


class StatutoryComplianceCalendar(Base):
    __tablename__ = "statutory_compliance_calendar"

    id = Column(Integer, primary_key=True)
    statutory_type = Column(String(50), index=True)
    due_date = Column(Date, nullable=False, index=True)
    period_start = Column(Date)
    period_end = Column(Date)
    description = Column(String(500))
    status = Column(String(30), default="Pending", index=True)
    filed_at = Column(DateTime(timezone=True))
    filed_by = Column(Integer, ForeignKey("users.id"))
    remarks = Column(Text)
    company_id = Column(Integer, ForeignKey("companies.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StatutoryFilingSubmission(Base):
    __tablename__ = "statutory_filing_submissions"

    id = Column(Integer, primary_key=True)
    statutory_type = Column(String(50), index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id"), index=True)
    file_type = Column(String(20))
    generated_file_path = Column(String(500))
    validation_status = Column(String(30), default="pending", index=True)
    validation_errors_json = Column(JSON)
    row_count = Column(Integer)
    total_amount = Column(Numeric(18, 2))
    submitted_at = Column(DateTime(timezone=True))
    submitted_by = Column(Integer, ForeignKey("users.id"))
    portal_reference = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun")


class StatutoryExport(Base):
    __tablename__ = "statutory_exports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    export_type = Column(String(40), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    total_employees = Column(Integer, default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    downloaded_at = Column(DateTime(timezone=True))
    download_count = Column(Integer, default=0)

    payroll_run = relationship("PayrollRun")


class PayrollComplianceRule(Base):
    __tablename__ = "payroll_compliance_rules"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(80), nullable=False)
    rule_type = Column(String(30), nullable=False)  # PT, LWF
    salary_from = Column(Numeric(12, 2), default=0)
    salary_to = Column(Numeric(12, 2))
    employee_amount = Column(Numeric(12, 2), default=0)
    employer_amount = Column(Numeric(12, 2), default=0)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BankAdviceFormat(Base):
    __tablename__ = "bank_advice_formats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    bank_name = Column(String(120), nullable=False)
    file_format = Column(String(20), default="CSV")
    delimiter = Column(String(5), default=",")
    include_header = Column(Boolean, default=True)
    column_order = Column(Text, default="employee_id,employee_name,account_number,ifsc,net_salary")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SalaryStructureComponent(Base):
    __tablename__ = "salary_structure_components"

    id = Column(Integer, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(12, 2), default=0)
    percentage = Column(Numeric(5, 2))
    order_sequence = Column(Integer, default=1)

    structure = relationship("SalaryStructure", back_populates="components")
    component = relationship("SalaryComponent")


class EmployeeSalary(Base):
    __tablename__ = "employee_salaries"
    __table_args__ = (
        Index("idx_employee_salary_effective", "employee_id", "effective_from", "effective_to"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    structure_id = Column(Integer, ForeignKey("salary_structures.id", ondelete="SET NULL"), nullable=True)
    ctc = Column(Numeric(14, 2), nullable=False)
    basic = Column(Numeric(12, 2))
    hra = Column(Numeric(12, 2))
    effective_from = Column(Date, nullable=False)
    effective_date = Column(Date)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    structure = relationship("SalaryStructure", back_populates="employee_salaries")


class SalaryRevisionRequest(Base):
    __tablename__ = "salary_revision_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    current_salary_id = Column(Integer, ForeignKey("employee_salaries.id", ondelete="SET NULL"), nullable=True)
    proposed_structure_id = Column(Integer, ForeignKey("salary_structures.id", ondelete="SET NULL"), nullable=True)
    current_ctc = Column(Numeric(14, 2), default=0)
    proposed_ctc = Column(Numeric(14, 2), nullable=False)
    effective_from = Column(Date, nullable=False)
    reason = Column(Text)
    status = Column(String(30), default="Pending", index=True)  # Pending, Approved, Rejected, Applied
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    checked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    checked_at = Column(DateTime(timezone=True))
    checker_remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SensitiveSalaryAuditLog(Base):
    __tablename__ = "sensitive_salary_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(Integer)
    action = Column(String(80), nullable=False, index=True)
    field_name = Column(String(80))
    old_value_masked = Column(String(120))
    new_value_masked = Column(String(120))
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        Index("idx_payroll_run_period", "pay_period_start", "pay_period_end", "company_id"),
        Index("idx_payroll_run_active_month", "deleted_at", "year", "month"),
        Index("idx_payroll_run_company_active_month", "company_id", "deleted_at", "year", "month"),
        Index("idx_payroll_run_company_status_month", "company_id", "status", "year", "month"),
    )

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    pay_period_start = Column(Date)
    pay_period_end = Column(Date)
    run_date = Column(Date)
    status = Column(String(20), default="draft")  # draft -> inputs_pending -> calculated -> approved -> locked -> paid
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    locked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at = Column(DateTime(timezone=True))
    total_gross = Column(Numeric(16, 2), default=0)
    total_deductions = Column(Numeric(16, 2), default=0)
    total_net = Column(Numeric(16, 2), default=0)
    remarks = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    records = relationship("PayrollRecord", back_populates="payroll_run", cascade="all, delete-orphan")
    variance_items = relationship("PayrollVarianceItem", back_populates="payroll_run", cascade="all, delete-orphan")
    export_batches = relationship("PayrollExportBatch", back_populates="payroll_run", cascade="all, delete-orphan")
    audit_logs = relationship("PayrollRunAuditLog", back_populates="payroll_run", cascade="all, delete-orphan")
    pre_run_checks = relationship("PayrollPreRunCheck", back_populates="payroll_run", cascade="all, delete-orphan")
    manual_inputs = relationship("PayrollManualInput", back_populates="payroll_run", cascade="all, delete-orphan")
    run_employees = relationship("PayrollRunEmployee", back_populates="payroll_run", cascade="all, delete-orphan")


class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    working_days = Column(Integer)
    present_days = Column(Numeric(5, 1))
    lop_days = Column(Numeric(5, 1), default=0)
    paid_days = Column(Numeric(5, 1))
    basic = Column(Numeric(12, 2), default=0)
    hra = Column(Numeric(12, 2), default=0)
    da = Column(Numeric(12, 2), default=0)
    ta = Column(Numeric(12, 2), default=0)
    other_allowances = Column(Numeric(12, 2), default=0)
    gross_salary = Column(Numeric(12, 2), default=0)
    pf_employee = Column(Numeric(10, 2), default=0)
    pf_employer = Column(Numeric(10, 2), default=0)
    esi_employee = Column(Numeric(10, 2), default=0)
    esi_employer = Column(Numeric(10, 2), default=0)
    professional_tax = Column(Numeric(10, 2), default=0)
    tds = Column(Numeric(10, 2), default=0)
    other_deductions = Column(Numeric(10, 2), default=0)
    total_deductions = Column(Numeric(12, 2), default=0)
    reimbursements = Column(Numeric(10, 2), default=0)
    bonus = Column(Numeric(10, 2), default=0)
    net_salary = Column(Numeric(12, 2), default=0)
    salary_currency = Column(String(3), default="INR")
    exchange_rate = Column(Numeric(14, 6))
    converted_currency = Column(String(3), default="INR")
    payslip_pdf_url = Column(String(500))
    payslip_generated_at = Column(DateTime(timezone=True))
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(Text)
    status = Column(String(20), default="Draft")  # Draft, Approved, Paid

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    payroll_run = relationship("PayrollRun", back_populates="records")
    employee = relationship("Employee", back_populates="payrolls")
    components = relationship("PayrollComponent", back_populates="record", cascade="all, delete-orphan")


class PayrollComponent(Base):
    __tablename__ = "payroll_components"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="SET NULL"), nullable=True)
    component_name = Column(String(100))
    component_type = Column(String(20))
    amount = Column(Numeric(12, 2), default=0)
    source_type = Column(String(50))
    source_id = Column(Integer)
    taxable_amount = Column(Numeric(12, 2), default=0)
    exempt_amount = Column(Numeric(12, 2), default=0)
    wage_base_flags = Column(JSON)
    calculation_order = Column(Integer, default=100)
    formula_trace_json = Column(JSON)
    is_manual = Column(Boolean, default=False)
    is_arrear = Column(Boolean, default=False)
    is_reversal = Column(Boolean, default=False)

    record = relationship("PayrollRecord", back_populates="components")


class PayrollRunEmployee(Base):
    __tablename__ = "payroll_run_employees"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="Draft", index=True)
    hold_reason = Column(Text)
    skip_reason = Column(Text)
    input_status = Column(String(30), default="Pending", index=True)
    calculation_status = Column(String(30), default="Pending", index=True)
    approval_status = Column(String(30), default="Pending", index=True)
    gross_salary = Column(Numeric(12, 2), default=0)
    total_deductions = Column(Numeric(12, 2), default=0)
    net_salary = Column(Numeric(12, 2), default=0)
    variance_status = Column(String(30), default="Not Checked")
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    payroll_run = relationship("PayrollRun", back_populates="run_employees")
    snapshots = relationship("PayrollCalculationSnapshot", back_populates="run_employee", cascade="all, delete-orphan")


class PayrollCalculationSnapshot(Base):
    __tablename__ = "payroll_calculation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    run_employee_id = Column(Integer, ForeignKey("payroll_run_employees.id", ondelete="CASCADE"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_type = Column(String(50), default="Worksheet", index=True)
    salary_template_json = Column(JSON)
    tax_worksheet_json = Column(JSON)
    attendance_input_json = Column(JSON)
    statutory_profile_json = Column(JSON)
    formula_version_json = Column(JSON)
    result_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run_employee = relationship("PayrollRunEmployee", back_populates="snapshots")


class PayrollArrearRun(Base):
    __tablename__ = "payroll_arrear_runs"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(150), nullable=False)
    reason = Column(Text)
    status = Column(String(30), default="Draft", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lines = relationship("PayrollArrearLine", back_populates="arrear_run", cascade="all, delete-orphan")


class PayrollArrearLine(Base):
    __tablename__ = "payroll_arrear_lines"

    id = Column(Integer, primary_key=True, index=True)
    arrear_run_id = Column(Integer, ForeignKey("payroll_arrear_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey("salary_components.id", ondelete="SET NULL"), nullable=True)
    component_name = Column(String(120), nullable=False)
    arrear_type = Column(String(50), default="Earning")
    from_date = Column(Date)
    to_date = Column(Date)
    amount = Column(Numeric(12, 2), default=0)
    reason = Column(Text)
    status = Column(String(30), default="Pending", index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    arrear_run = relationship("PayrollArrearRun", back_populates="lines")


class OffCyclePayrollRun(Base):
    __tablename__ = "off_cycle_payroll_runs"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    run_type = Column(String(50), default="Correction", index=True)
    pay_group_id = Column(Integer, ForeignKey("payroll_pay_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text)
    status = Column(String(30), default="Draft", index=True)
    total_amount = Column(Numeric(14, 2), default=0)
    scheduled_payment_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollPaymentBatch(Base):
    __tablename__ = "payroll_payment_batches"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_format_id = Column(Integer, ForeignKey("bank_advice_formats.id", ondelete="SET NULL"), nullable=True)
    debit_account = Column(String(120))
    total_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Draft", index=True)
    generated_file_url = Column(String(500))
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    released_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun")
    lines = relationship("PayrollPaymentLine", back_populates="batch", cascade="all, delete-orphan")


class PayrollPaymentLine(Base):
    __tablename__ = "payroll_payment_lines"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("payroll_payment_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    net_amount = Column(Numeric(14, 2), default=0)
    bank_account = Column(String(120))
    ifsc = Column(String(20))
    payment_status = Column(String(30), default="Pending", index=True)
    utr_number = Column(String(120), index=True)
    failure_reason = Column(Text)
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("PayrollPaymentBatch", back_populates="lines")


class AccountingLedger(Base):
    __tablename__ = "accounting_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    ledger_type = Column(String(50), nullable=False)  # Expense, Liability, Asset
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollGLMapping(Base):
    __tablename__ = "payroll_gl_mappings"

    id = Column(Integer, primary_key=True, index=True)
    component_name = Column(String(120), nullable=False, index=True)
    component_type = Column(String(50), nullable=False)
    debit_ledger_id = Column(Integer, ForeignKey("accounting_ledgers.id", ondelete="SET NULL"), nullable=True)
    credit_ledger_id = Column(Integer, ForeignKey("accounting_ledgers.id", ondelete="SET NULL"), nullable=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    cost_center = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollJournalEntry(Base):
    __tablename__ = "payroll_journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    legal_entity_id = Column(Integer, ForeignKey("payroll_legal_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    cost_center = Column(String(100))
    status = Column(String(30), default="Draft", index=True)
    total_debit = Column(Numeric(14, 2), default=0)
    total_credit = Column(Numeric(14, 2), default=0)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    posted_at = Column(DateTime(timezone=True))

    payroll_run = relationship("PayrollRun")
    lines = relationship("PayrollJournalLine", back_populates="journal", cascade="all, delete-orphan")


class PayrollJournalLine(Base):
    __tablename__ = "payroll_journal_lines"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("payroll_journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey("accounting_ledgers.id", ondelete="SET NULL"), nullable=True)
    ledger_code = Column(String(50))
    ledger_name = Column(String(150))
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    component_name = Column(String(120))
    debit = Column(Numeric(14, 2), default=0)
    credit = Column(Numeric(14, 2), default=0)
    memo = Column(Text)

    journal = relationship("PayrollJournalEntry", back_populates="lines")


class StatutoryFileValidation(Base):
    __tablename__ = "statutory_file_validations"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    file_type = Column(String(50), nullable=False, index=True)
    status = Column(String(30), default="Pending", index=True)
    total_rows = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    output_file_url = Column(String(500))
    validation_errors_json = Column(JSON)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class StatutoryTemplateFile(Base):
    __tablename__ = "statutory_template_files"

    id = Column(Integer, primary_key=True, index=True)
    template_type = Column(String(50), nullable=False, index=True)
    format_version = Column(String(30), default="v1")
    file_url = Column(String(500), nullable=False)
    status = Column(String(30), default="Generated", index=True)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollVarianceItem(Base):
    __tablename__ = "payroll_variance_items"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True)
    current_gross = Column(Numeric(12, 2), default=0)
    previous_gross = Column(Numeric(12, 2), default=0)
    gross_delta = Column(Numeric(12, 2), default=0)
    gross_delta_percent = Column(Numeric(8, 2), default=0)
    current_net = Column(Numeric(12, 2), default=0)
    previous_net = Column(Numeric(12, 2), default=0)
    net_delta = Column(Numeric(12, 2), default=0)
    net_delta_percent = Column(Numeric(8, 2), default=0)
    severity = Column(String(20), default="Info")
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun", back_populates="variance_items")


class PayrollExportBatch(Base):
    __tablename__ = "payroll_export_batches"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    export_type = Column(String(50), nullable=False, index=True)
    status = Column(String(30), default="Generated", index=True)
    output_file_url = Column(String(500))
    total_records = Column(Integer, default=0)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    remarks = Column(Text)

    payroll_run = relationship("PayrollRun", back_populates="export_batches")


class PayrollBankExport(Base):
    __tablename__ = "payroll_bank_exports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    export_type = Column(String(20), nullable=False, index=True)
    bank_name = Column(String(120))
    total_employees = Column(Integer, default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    file_path = Column(String(500), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    downloaded_at = Column(DateTime(timezone=True))
    download_count = Column(Integer, default=0)

    payroll_run = relationship("PayrollRun")


class PayrollRunAuditLog(Base):
    __tablename__ = "payroll_run_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun", back_populates="audit_logs")


class PayrollPreRunCheck(Base):
    __tablename__ = "payroll_pre_run_checks"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    check_type = Column(String(80), nullable=False, index=True)
    status = Column(String(30), default="Pending", index=True)  # Passed, Warning, Failed
    severity = Column(String(20), default="Info")
    message = Column(Text)
    affected_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun", back_populates="pre_run_checks")


class PayrollManualInput(Base):
    __tablename__ = "payroll_manual_inputs"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    input_type = Column(String(40), nullable=False, index=True)  # Bonus, Arrear, Incentive, Deduction
    component_name = Column(String(120), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    remarks = Column(Text)
    status = Column(String(30), default="Pending", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun", back_populates="manual_inputs")


class PayrollUnlockRequest(Base):
    __tablename__ = "payroll_unlock_requests"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    status = Column(String(30), default="Pending", index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payroll_run = relationship("PayrollRun")


class PayslipPublishBatch(Base):
    __tablename__ = "payslip_publish_batches"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), default="Queued", index=True)
    total_payslips = Column(Integer, default=0)
    published_count = Column(Integer, default=0)
    email_dispatch_status = Column(String(30), default="Not Started")
    output_file_url = Column(String(500))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    payroll_run = relationship("PayrollRun")


class Reimbursement(Base):
    __tablename__ = "reimbursements"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100))  # Travel, Medical, Food, etc.
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date)
    description = Column(Text)
    receipt_url = Column(String(500))
    status = Column(String(20), default="Pending")  # Pending, Approved, Rejected, Paid
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReimbursementLedger(Base):
    __tablename__ = "reimbursement_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    reimbursement_id = Column(Integer, ForeignKey("reimbursements.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    amount = Column(Numeric(12, 2), default=0)
    status_from = Column(String(30))
    status_to = Column(String(30))
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmployeeLoan(Base):
    __tablename__ = "employee_loans"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_type = Column(String(80), default="Salary Advance")
    principal_amount = Column(Numeric(14, 2), nullable=False)
    interest_rate = Column(Numeric(6, 2), default=0)
    total_payable = Column(Numeric(14, 2), nullable=False)
    emi_amount = Column(Numeric(12, 2), nullable=False)
    start_month = Column(Integer, nullable=False)
    start_year = Column(Integer, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    balance_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(30), default="Active", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    installments = relationship("EmployeeLoanInstallment", back_populates="loan", cascade="all, delete-orphan")
    ledger_entries = relationship("EmployeeLoanLedger", back_populates="loan", cascade="all, delete-orphan")


class EmployeeLoanInstallment(Base):
    __tablename__ = "employee_loan_installments"

    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("employee_loans.id", ondelete="CASCADE"), nullable=False, index=True)
    installment_number = Column(Integer, nullable=False)
    due_month = Column(Integer, nullable=False)
    due_year = Column(Integer, nullable=False)
    due_amount = Column(Numeric(12, 2), nullable=False)
    principal_component = Column(Numeric(12, 2), default=0)
    interest_component = Column(Numeric(12, 2), default=0)
    status = Column(String(30), default="Scheduled", index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True)
    paid_at = Column(DateTime(timezone=True))

    loan = relationship("EmployeeLoan", back_populates="installments")


class EmployeeLoanLedger(Base):
    __tablename__ = "employee_loan_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("employee_loans.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    amount = Column(Numeric(12, 2), default=0)
    balance_after = Column(Numeric(14, 2), default=0)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    loan = relationship("EmployeeLoan", back_populates="ledger_entries")


class FullFinalSettlement(Base):
    __tablename__ = "full_final_settlements"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    exit_record_id = Column(Integer, ForeignKey("exit_records.id", ondelete="SET NULL"), nullable=True)
    settlement_date = Column(Date, nullable=False)
    last_working_date = Column(Date)
    status = Column(String(30), default="Draft", index=True)
    unpaid_salary = Column(Numeric(12, 2), default=0)
    leave_encashment_amount = Column(Numeric(12, 2), default=0)
    notice_recovery_amount = Column(Numeric(12, 2), default=0)
    gratuity_amount = Column(Numeric(12, 2), default=0)
    loan_recovery_amount = Column(Numeric(12, 2), default=0)
    reimbursement_payable = Column(Numeric(12, 2), default=0)
    bonus_payable = Column(Numeric(12, 2), default=0)
    other_earnings = Column(Numeric(12, 2), default=0)
    other_deductions = Column(Numeric(12, 2), default=0)
    other_payables = Column(Numeric(12, 2), default=0)
    other_recoveries = Column(Numeric(12, 2), default=0)
    net_payable = Column(Numeric(14, 2), default=0)
    settlement_letter_url = Column(String(500))
    prepared_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    rejected_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    lines = relationship("FullFinalSettlementLine", back_populates="settlement", cascade="all, delete-orphan")


class FullFinalSettlementLine(Base):
    __tablename__ = "full_final_settlement_lines"

    id = Column(Integer, primary_key=True, index=True)
    settlement_id = Column(Integer, ForeignKey("full_final_settlements.id", ondelete="CASCADE"), nullable=False, index=True)
    line_type = Column(String(30), nullable=False)  # Payable, Recovery
    component_name = Column(String(120), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    source = Column(String(80))
    is_manual_adjustment = Column(Boolean, default=False)
    remarks = Column(Text)

    settlement = relationship("FullFinalSettlement", back_populates="lines")


class TaxDeclarationCycle(Base):
    __tablename__ = "tax_declaration_cycles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    financial_year = Column(String(20), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    proof_due_date = Column(Date)
    status = Column(String(30), default="Open")  # Open, Proof, Locked
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    declarations = relationship("TaxDeclaration", back_populates="cycle", cascade="all, delete-orphan")


class TaxDeclaration(Base):
    __tablename__ = "tax_declarations"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("tax_declaration_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(40), nullable=False)  # 80C, HRA, LTA
    declared_amount = Column(Numeric(12, 2), default=0)
    approved_amount = Column(Numeric(12, 2), default=0)
    description = Column(Text)
    status = Column(String(30), default="Submitted")  # Submitted, Proof Submitted, Approved, Rejected
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cycle = relationship("TaxDeclarationCycle", back_populates="declarations")
    proofs = relationship("TaxDeclarationProof", back_populates="declaration", cascade="all, delete-orphan")


class TaxDeclarationProof(Base):
    __tablename__ = "tax_declaration_proofs"

    id = Column(Integer, primary_key=True, index=True)
    declaration_id = Column(Integer, ForeignKey("tax_declarations.id", ondelete="CASCADE"), nullable=False, index=True)
    file_url = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    status = Column(String(30), default="Submitted")  # Submitted, Verified, Rejected
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True))
    verification_remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    declaration = relationship("TaxDeclaration", back_populates="proofs")


class TaxDeclarationCategory(Base):
    __tablename__ = "tax_declaration_categories"
    __table_args__ = (
        Index("idx_tax_declaration_category_fy_code", "organization_id", "financial_year", "code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    section = Column(String(80), nullable=False)
    max_limit = Column(Numeric(14, 2), default=0)
    requires_proof = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    items = relationship("EmployeeTaxDeclarationItem", back_populates="category")


class EmployeeTaxDeclaration(Base):
    __tablename__ = "employee_tax_declarations"
    __table_args__ = (
        Index("idx_employee_tax_declaration_employee_fy", "employee_id", "financial_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    status = Column(String(30), default="draft", index=True)
    submitted_at = Column(DateTime(timezone=True))
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee")
    items = relationship("EmployeeTaxDeclarationItem", back_populates="declaration", cascade="all, delete-orphan")


class EmployeeTaxDeclarationItem(Base):
    __tablename__ = "employee_tax_declaration_items"

    id = Column(Integer, primary_key=True, index=True)
    declaration_id = Column(Integer, ForeignKey("employee_tax_declarations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("tax_declaration_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    declared_amount = Column(Numeric(14, 2), default=0)
    approved_amount = Column(Numeric(14, 2), default=0)
    remarks = Column(Text)
    status = Column(String(30), default="draft", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    declaration = relationship("EmployeeTaxDeclaration", back_populates="items")
    category = relationship("TaxDeclarationCategory", back_populates="items")
    proofs = relationship("EmployeeTaxProof", back_populates="declaration_item", cascade="all, delete-orphan")


class EmployeeTaxProof(Base):
    __tablename__ = "employee_tax_proofs"

    id = Column(Integer, primary_key=True, index=True)
    declaration_item_id = Column(Integer, ForeignKey("employee_tax_declaration_items.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(120))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    declaration_item = relationship("EmployeeTaxDeclarationItem", back_populates="proofs")


class PayslipDeliveryLog(Base):
    __tablename__ = "payslip_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(30), nullable=False, index=True)  # email, whatsapp, sms
    destination = Column(String(180))
    status = Column(String(30), default="Queued", index=True)
    message = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayslipQuery(Base):
    __tablename__ = "payslip_queries"

    id = Column(Integer, primary_key=True, index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(30), default="Open", index=True)
    priority = Column(String(20), default="Medium", index=True)
    resolution = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SalaryAdvance(Base):
    __tablename__ = "salary_advances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_amount = Column(Numeric(14, 2), nullable=False)
    approved_amount = Column(Numeric(14, 2), default=0)
    reason = Column(Text)
    requested_deduction_month = Column(Integer, nullable=False)
    requested_deduction_year = Column(Integer, nullable=False)
    status = Column(String(30), default="Pending", index=True)
    payroll_record_id = Column(Integer, ForeignKey("payroll_records.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SalaryRevisionBatch(Base):
    __tablename__ = "salary_revision_batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    effective_from = Column(Date, nullable=False)
    status = Column(String(30), default="Draft", index=True)
    total_rows = Column(Integer, default=0)
    applied_rows = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    applied_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    applied_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lines = relationship("SalaryRevisionBatchLine", back_populates="batch", cascade="all, delete-orphan")


class SalaryRevisionBatchLine(Base):
    __tablename__ = "salary_revision_batch_lines"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("salary_revision_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    current_ctc = Column(Numeric(14, 2), default=0)
    new_ctc = Column(Numeric(14, 2), nullable=False)
    structure_id = Column(Integer, ForeignKey("salary_structures.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="Pending", index=True)
    error_message = Column(Text)

    batch = relationship("SalaryRevisionBatch", back_populates="lines")


class BonusPolicy(Base):
    __tablename__ = "bonus_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    bonus_type = Column(String(60), default="Festival", index=True)
    amount_type = Column(String(30), default="Fixed")  # Fixed, PercentageOfCTC, PercentageOfBasic
    amount_value = Column(Numeric(12, 2), nullable=False)
    applicable_month = Column(Integer)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    grade_band_id = Column(Integer, ForeignKey("grade_bands.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GratuityAccrual(Base):
    __tablename__ = "gratuity_accruals"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    gratuity_wage = Column(Numeric(14, 2), default=0)
    accrual_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Posted", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SalaryCertificate(Base):
    __tablename__ = "salary_certificates"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(160), nullable=False)
    period_from = Column(Date)
    period_to = Column(Date)
    annual_ctc = Column(Numeric(14, 2), default=0)
    monthly_gross = Column(Numeric(14, 2), default=0)
    file_url = Column(String(500))
    status = Column(String(30), default="Generated", index=True)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollBudget(Base):
    __tablename__ = "payroll_budgets"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    budget_amount = Column(Numeric(16, 2), nullable=False)
    currency = Column(String(3), default="INR")
    remarks = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollBankValidation(Base):
    __tablename__ = "payroll_bank_validations"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(30), default="Pending", index=True)
    error_code = Column(String(80))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollBankFileValidation(Base):
    __tablename__ = "payroll_bank_file_validations"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_name = Column(String(120), nullable=False, index=True)
    status = Column(String(30), default="Pending", index=True)
    error_count = Column(Integer, default=0)
    warnings_json = Column(JSON)
    errors_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TDS26ASReconciliation(Base):
    __tablename__ = "tds_26as_reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    company_tds = Column(Numeric(14, 2), default=0)
    reported_26as_tds = Column(Numeric(14, 2), default=0)
    difference = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="Pending", index=True)
    remarks = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Form12BARecord(Base):
    __tablename__ = "form_12ba_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    perquisites_json = Column(JSON)
    total_perquisite_value = Column(Numeric(14, 2), default=0)
    file_url = Column(String(500))
    status = Column(String(30), default="Generated", index=True)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollExchangeRate(Base):
    __tablename__ = "payroll_exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(3), nullable=False, index=True)
    to_currency = Column(String(3), default="INR", nullable=False, index=True)
    rate = Column(Numeric(14, 6), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    source = Column(String(80), default="Manual")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PayrollReportDefinition(Base):
    __tablename__ = "payroll_report_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    report_type = Column(String(80), nullable=False, index=True)
    filters_json = Column(JSON)
    columns_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
