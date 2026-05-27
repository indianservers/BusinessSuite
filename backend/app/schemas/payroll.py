from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel


class SalaryComponentBase(BaseModel):
    name: str
    code: str
    component_type: str
    calculation_type: str = "Fixed"
    amount: Decimal = Decimal("0")
    percentage_of: Optional[str] = None
    formula_expression: Optional[str] = None
    payslip_group: str = "Earnings"
    display_sequence: int = 100
    is_taxable: bool = True
    is_pf_applicable: bool = False
    is_esi_applicable: bool = False
    description: Optional[str] = None
    category_id: Optional[int] = None
    earning_type: Optional[str] = None
    deduction_timing: Optional[str] = None
    pay_frequency: str = "Monthly"
    taxable_treatment: str = "Taxable"
    exemption_section: Optional[str] = None
    appears_in_ctc: bool = True
    appears_in_payslip: bool = True
    pro_rata_rule: str = "Calendar Days"
    lop_applicable: bool = True
    pf_wage_flag: bool = False
    esi_wage_flag: bool = False
    gratuity_wage_flag: bool = False
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    rounding_rule: str = "Nearest Rupee"
    effective_from: Optional[date_type] = None
    effective_to: Optional[date_type] = None
    is_currency_fixed: bool = True


class SalaryComponentCreate(SalaryComponentBase):
    pass


class SalaryComponentSchema(SalaryComponentBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class SalaryComponentCategoryCreate(BaseModel):
    name: str
    code: str
    category_type: str
    description: Optional[str] = None


class SalaryComponentCategorySchema(SalaryComponentCategoryCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class SalaryComponentFormulaRuleCreate(BaseModel):
    component_id: int
    formula_expression: str
    dependency_order: int = 100
    formula_scope: str = "Salary Preview"
    effective_from: Optional[date_type] = None
    effective_to: Optional[date_type] = None
    validation_status: str = "Active"


class SalaryComponentFormulaRuleSchema(SalaryComponentFormulaRuleCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SalaryStructureComponentInput(BaseModel):
    component_id: int
    amount: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    order_sequence: int = 1


class SalaryStructureCreate(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    parent_structure_id: Optional[int] = None
    effective_from: Optional[date_type] = None
    components: List[SalaryStructureComponentInput] = []


class SalaryStructureSchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    parent_structure_id: Optional[int] = None
    effective_from: Optional[date_type] = None
    is_active: bool
    components: List[dict] = []

    class Config:
        from_attributes = True


class SalaryStructurePreviewRequest(BaseModel):
    ctc: Decimal


class SalaryStructurePreviewLine(BaseModel):
    component_id: int
    component_name: str
    component_code: str
    payslip_group: str
    display_sequence: int
    monthly_amount: Decimal
    annual_amount: Decimal
    formula_expression: Optional[str] = None
    formula_trace: Optional[dict] = None


class SalaryStructurePreviewSchema(BaseModel):
    structure_id: int
    structure_name: str
    version: str
    monthly_ctc: Decimal
    annual_ctc: Decimal
    lines: List[SalaryStructurePreviewLine]
    formula_order: List[str] = []
    warnings: List[str] = []


class PayrollPayGroupCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    pay_frequency: str = "Monthly"
    legal_entity_id: Optional[int] = None
    branch_id: Optional[int] = None
    state: Optional[str] = None
    pay_cycle_day: int = 1
    pay_date_rule: str = "Last Working Day"
    attendance_cutoff_day: int = 25
    reimbursement_cutoff_day: int = 25
    tax_deduction_frequency: str = "Monthly"
    default_tax_regime: str = "NEW"
    rounding_policy: str = "Nearest Rupee"
    include_weekends_in_lop: bool = False
    is_default: bool = False


class PayrollPayGroupSchema(PayrollPayGroupCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class PayrollStatutoryProfileCreate(BaseModel):
    legal_entity_id: int
    pf_establishment_code: Optional[str] = None
    pf_signatory: Optional[str] = None
    esi_employer_code: Optional[str] = None
    pt_registration_number: Optional[str] = None
    lwf_registration_number: Optional[str] = None
    tan_circle: Optional[str] = None
    tax_deductor_type: str = "Company"
    effective_from: date_type
    effective_to: Optional[date_type] = None


class PayrollStatutoryProfileSchema(PayrollStatutoryProfileCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class PayrollPeriodCreate(BaseModel):
    pay_group_id: int
    month: int
    year: int
    financial_year: str
    period_start: date_type
    period_end: date_type
    attendance_cutoff_at: Optional[datetime] = None
    input_cutoff_at: Optional[datetime] = None
    payroll_date: date_type
    status: str = "Open"


class PayrollPeriodGenerateRequest(BaseModel):
    pay_group_id: int
    year: int
    financial_year: str


class PayrollPeriodSchema(PayrollPeriodCreate):
    id: int
    locked_by: Optional[int] = None
    locked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SalaryTemplateComponentCreate(BaseModel):
    component_id: int
    amount: Decimal = Decimal("0")
    percentage: Optional[Decimal] = None
    formula_expression: Optional[str] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    is_employee_editable: bool = False
    order_sequence: int = 100


class SalaryTemplateCreate(BaseModel):
    name: str
    code: str
    pay_group_id: Optional[int] = None
    grade: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    residual_component_id: Optional[int] = None
    effective_from: Optional[date_type] = None
    effective_to: Optional[date_type] = None
    components: List[SalaryTemplateComponentCreate] = []


class SalaryTemplateComponentSchema(SalaryTemplateComponentCreate):
    id: int
    template_id: int

    class Config:
        from_attributes = True


class SalaryTemplateSchema(BaseModel):
    id: int
    name: str
    code: str
    pay_group_id: Optional[int] = None
    grade: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    residual_component_id: Optional[int] = None
    effective_from: Optional[date_type] = None
    effective_to: Optional[date_type] = None
    is_active: bool
    components: List[SalaryTemplateComponentSchema] = []

    class Config:
        from_attributes = True


class EmployeeSalaryTemplateAssignmentCreate(BaseModel):
    employee_id: int
    template_id: int
    ctc: Decimal
    effective_from: date_type
    effective_to: Optional[date_type] = None
    status: str = "Active"


class EmployeeSalaryTemplateAssignmentSchema(EmployeeSalaryTemplateAssignmentCreate):
    id: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeSalaryComponentOverrideCreate(BaseModel):
    assignment_id: int
    component_id: int
    override_type: str
    amount: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    formula_expression: Optional[str] = None
    reason: Optional[str] = None


class EmployeeSalaryComponentOverrideSchema(EmployeeSalaryComponentOverrideCreate):
    id: int
    approved_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollCalendarCreate(BaseModel):
    pay_group_id: int
    month: int
    year: int
    period_start: date_type
    period_end: date_type
    payroll_date: date_type
    attendance_cutoff_date: Optional[date_type] = None
    status: str = "Open"


class PayrollCalendarSchema(PayrollCalendarCreate):
    id: int

    class Config:
        from_attributes = True


class PayrollComplianceRuleCreate(BaseModel):
    state: str
    rule_type: str
    salary_from: Decimal = Decimal("0")
    salary_to: Optional[Decimal] = None
    employee_amount: Decimal = Decimal("0")
    employer_amount: Decimal = Decimal("0")
    effective_from: date_type
    effective_to: Optional[date_type] = None


class PayrollComplianceRuleSchema(PayrollComplianceRuleCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class BankAdviceFormatCreate(BaseModel):
    name: str
    bank_name: str
    file_format: str = "CSV"
    delimiter: str = ","
    include_header: bool = True
    column_order: str = "employee_id,employee_name,account_number,ifsc,net_salary"


class BankAdviceFormatSchema(BankAdviceFormatCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class EmployeeSalaryCreate(BaseModel):
    employee_id: int
    structure_id: Optional[int] = None
    ctc: Decimal
    basic: Optional[Decimal] = None
    hra: Optional[Decimal] = None
    effective_from: date_type
    effective_date: Optional[date_type] = None
    effective_to: Optional[date_type] = None


class EmployeeSalarySchema(BaseModel):
    id: int
    employee_id: int
    structure_id: Optional[int] = None
    ctc: Decimal
    basic: Optional[Decimal] = None
    hra: Optional[Decimal] = None
    effective_from: date_type
    effective_date: Optional[date_type] = None
    effective_to: Optional[date_type] = None
    is_active: bool

    class Config:
        from_attributes = True


class SalaryRevisionRequestCreate(BaseModel):
    employee_id: int
    proposed_structure_id: Optional[int] = None
    proposed_ctc: Decimal
    effective_from: date_type
    reason: Optional[str] = None


class SalaryRevisionReview(BaseModel):
    action: str
    remarks: Optional[str] = None


class SalaryRevisionRequestSchema(BaseModel):
    id: int
    employee_id: int
    current_salary_id: Optional[int] = None
    proposed_structure_id: Optional[int] = None
    current_ctc: Decimal
    proposed_ctc: Decimal
    effective_from: date_type
    reason: Optional[str] = None
    status: str
    requested_by: Optional[int] = None
    checked_by: Optional[int] = None
    checked_at: Optional[datetime] = None
    checker_remarks: Optional[str] = None

    class Config:
        from_attributes = True


class SensitiveSalaryAuditLogSchema(BaseModel):
    id: int
    employee_id: int
    entity_type: str
    entity_id: Optional[int] = None
    action: str
    field_name: Optional[str] = None
    old_value_masked: Optional[str] = None
    new_value_masked: Optional[str] = None
    actor_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollRunCreate(BaseModel):
    month: int
    year: int
    company_id: Optional[int] = None
    pay_period_start: Optional[date_type] = None
    pay_period_end: Optional[date_type] = None
    force_run: bool = False


class PayrollRunApproval(BaseModel):
    action: str  # approve, lock, paid/mark_paid
    remarks: Optional[str] = None
    force_approve: bool = False


class PayrollRunSchema(BaseModel):
    id: int
    month: int
    year: int
    company_id: Optional[int] = None
    pay_period_start: Optional[date_type] = None
    pay_period_end: Optional[date_type] = None
    run_date: Optional[date_type] = None
    status: str
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal
    remarks: Optional[str] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None

    class Config:
        from_attributes = True


class PayrollRecordSchema(BaseModel):
    id: int
    payroll_run_id: int
    employee_id: int
    working_days: Optional[int] = None
    present_days: Optional[Decimal] = None
    lop_days: Decimal = Decimal("0")
    paid_days: Optional[Decimal] = None
    basic: Decimal
    hra: Decimal
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    salary_currency: Optional[str] = "INR"
    exchange_rate: Optional[Decimal] = None
    converted_currency: Optional[str] = "INR"
    is_anomaly: bool
    anomaly_reason: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class PayrollVarianceItemSchema(BaseModel):
    id: int
    payroll_run_id: int
    employee_id: int
    previous_payroll_record_id: Optional[int] = None
    current_gross: Decimal
    previous_gross: Decimal
    gross_delta: Decimal
    gross_delta_percent: Decimal
    current_net: Decimal
    previous_net: Decimal
    net_delta: Decimal
    net_delta_percent: Decimal
    severity: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class PayrollExportBatchSchema(BaseModel):
    id: int
    payroll_run_id: int
    export_type: str
    status: str
    output_file_url: Optional[str] = None
    total_records: int
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


class PayrollBankAdviceGenerateRequest(BaseModel):
    export_type: str = "pdf"
    bank_name: Optional[str] = None
    bank_format_id: Optional[int] = None
    payment_mode: str = "NEFT"


class PayrollBankAdviceRowSchema(BaseModel):
    payroll_record_id: int
    employee_id: int
    employee_code: Optional[str] = None
    employee_name: str
    account_holder_name: str
    bank_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    ifsc: Optional[str] = None
    net_payable: Decimal
    narration: str
    validation_errors: List[str] = []


class PayrollBankAdvicePreviewSchema(BaseModel):
    payroll_run_id: int
    payroll_month: str
    status: str
    company_name: str
    bank_name: Optional[str] = None
    total_employees: int
    total_amount: Decimal
    validation_errors: List[str] = []
    bank_file_validation: Optional[dict[str, Any]] = None
    rows: List[PayrollBankAdviceRowSchema]


class PayrollBankExportSchema(BaseModel):
    id: int
    organization_id: Optional[int] = None
    payroll_run_id: int
    export_type: str
    bank_name: Optional[str] = None
    total_employees: int
    total_amount: Decimal
    file_path: str
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None
    downloaded_at: Optional[datetime] = None
    download_count: int = 0

    class Config:
        from_attributes = True


class StatutoryExportGenerateRequest(BaseModel):
    payroll_run_id: int


class StatutoryExportSchema(BaseModel):
    id: int
    organization_id: Optional[int] = None
    payroll_run_id: int
    export_type: str
    file_path: str
    total_employees: int
    total_amount: Decimal
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None
    downloaded_at: Optional[datetime] = None
    download_count: int = 0

    class Config:
        from_attributes = True


class PayrollRunAuditLogSchema(BaseModel):
    id: int
    payroll_run_id: Optional[int] = None
    action: str
    actor_user_id: Optional[int] = None
    details: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollPreRunCheckCreate(BaseModel):
    check_type: str
    status: str = "Passed"
    severity: str = "Info"
    message: Optional[str] = None
    affected_employee_id: Optional[int] = None


class PayrollPreRunCheckSchema(PayrollPreRunCheckCreate):
    id: int
    payroll_run_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollManualInputCreate(BaseModel):
    employee_id: int
    input_type: str
    component_name: str
    amount: Decimal
    remarks: Optional[str] = None


class PayrollManualInputReview(BaseModel):
    action: str
    remarks: Optional[str] = None


class PayrollManualInputSchema(PayrollManualInputCreate):
    id: int
    payroll_run_id: int
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollUnlockRequestCreate(BaseModel):
    reason: str


class PayrollUnlockReview(BaseModel):
    action: str
    remarks: Optional[str] = None


class PayrollUnlockRequestSchema(BaseModel):
    id: int
    payroll_run_id: int
    reason: str
    status: str
    requested_by: Optional[int] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_remarks: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayslipPublishBatchCreate(BaseModel):
    output_file_url: Optional[str] = None
    email_dispatch_status: str = "Queued"


class PayslipPublishBatchSchema(BaseModel):
    id: int
    payroll_run_id: int
    status: str
    total_payslips: int
    published_count: int
    email_dispatch_status: str
    output_file_url: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReimbursementCreate(BaseModel):
    category: Optional[str] = None
    amount: Decimal
    date: Optional[date_type] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None


class ReimbursementSchema(BaseModel):
    id: int
    employee_id: int
    category: Optional[str] = None
    amount: Decimal
    date: Optional[date_type] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ReimbursementReview(BaseModel):
    action: str
    remarks: Optional[str] = None


class ReimbursementLedgerSchema(BaseModel):
    id: int
    reimbursement_id: int
    employee_id: int
    action: str
    amount: Decimal
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    payroll_record_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    remarks: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeLoanCreate(BaseModel):
    employee_id: int
    loan_type: str = "Salary Advance"
    principal_amount: Decimal
    interest_rate: Decimal = Decimal("0")
    emi_amount: Decimal
    start_month: int
    start_year: int
    tenure_months: int


class EmployeeLoanSchema(BaseModel):
    id: int
    employee_id: int
    loan_type: str
    principal_amount: Decimal
    interest_rate: Decimal
    total_payable: Decimal
    emi_amount: Decimal
    start_month: int
    start_year: int
    tenure_months: int
    balance_amount: Decimal
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class EmployeeLoanInstallmentSchema(BaseModel):
    id: int
    loan_id: int
    installment_number: int
    due_month: int
    due_year: int
    due_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    status: str
    payroll_record_id: Optional[int] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeLoanLedgerSchema(BaseModel):
    id: int
    loan_id: int
    employee_id: int
    action: str
    amount: Decimal
    balance_after: Decimal
    payroll_record_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    remarks: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FullFinalSettlementLineCreate(BaseModel):
    line_type: str
    component_name: str
    amount: Decimal
    source: Optional[str] = None
    remarks: Optional[str] = None


class FullFinalSettlementCreate(BaseModel):
    employee_id: int
    exit_record_id: Optional[int] = None
    settlement_date: date_type
    leave_encashment_amount: Decimal = Decimal("0")
    notice_recovery_amount: Decimal = Decimal("0")
    gratuity_amount: Decimal = Decimal("0")
    loan_recovery_amount: Decimal = Decimal("0")
    other_payables: Decimal = Decimal("0")
    other_recoveries: Decimal = Decimal("0")
    settlement_letter_url: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[FullFinalSettlementLineCreate] = []


class FullFinalSettlementLineSchema(FullFinalSettlementLineCreate):
    id: int
    settlement_id: int

    class Config:
        from_attributes = True


class FullFinalSettlementSchema(BaseModel):
    id: int
    employee_id: int
    exit_record_id: Optional[int] = None
    settlement_date: date_type
    status: str
    leave_encashment_amount: Decimal
    notice_recovery_amount: Decimal
    gratuity_amount: Decimal
    loan_recovery_amount: Decimal
    other_payables: Decimal
    other_recoveries: Decimal
    net_payable: Decimal
    settlement_letter_url: Optional[str] = None
    prepared_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    remarks: Optional[str] = None
    lines: List[FullFinalSettlementLineSchema] = []

    class Config:
        from_attributes = True


class TaxRegimeCreate(BaseModel):
    country: str = "India"
    financial_year: str
    regime_code: str
    name: str
    is_default: bool = False
    rebate_rules_json: Optional[Any] = None
    surcharge_rules_json: Optional[Any] = None
    cess_percent: Decimal = Decimal("4")
    standard_deduction_amount: Decimal = Decimal("0")


class TaxRegimeSchema(TaxRegimeCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class TaxSlabCreate(BaseModel):
    tax_regime_id: int
    min_income: Decimal = Decimal("0")
    max_income: Optional[Decimal] = None
    rate_percent: Decimal = Decimal("0")
    fixed_amount: Decimal = Decimal("0")
    sequence: int = 1


class TaxSlabSchema(TaxSlabCreate):
    id: int

    class Config:
        from_attributes = True


class TaxSectionCreate(BaseModel):
    section_code: str
    name: str
    description: Optional[str] = None
    proof_required: bool = True


class TaxSectionSchema(TaxSectionCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class TaxSectionLimitCreate(BaseModel):
    tax_section_id: int
    tax_regime_id: Optional[int] = None
    financial_year: str
    limit_amount: Decimal
    effective_from: Optional[date_type] = None
    effective_to: Optional[date_type] = None


class TaxSectionLimitSchema(TaxSectionLimitCreate):
    id: int

    class Config:
        from_attributes = True


class EmployeeTaxRegimeElectionCreate(BaseModel):
    employee_id: int
    financial_year: str
    tax_regime_id: int
    lock: bool = False


class EmployeeTaxRegimeElectionSchema(BaseModel):
    id: int
    employee_id: int
    financial_year: str
    tax_regime_id: int
    selected_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[int] = None

    class Config:
        from_attributes = True


class PreviousEmploymentTaxDetailCreate(BaseModel):
    employee_id: int
    financial_year: str
    employer_name: str
    taxable_income: Decimal = Decimal("0")
    pf: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    tds_deducted: Decimal = Decimal("0")
    proof_url: Optional[str] = None


class PreviousEmploymentTaxDetailSchema(PreviousEmploymentTaxDetailCreate):
    id: int
    verified_status: str
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaxWorksheetProjectRequest(BaseModel):
    employee_id: int
    financial_year: str
    tax_regime_id: Optional[int] = None
    gross_taxable_income: Decimal
    exemptions: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")
    paid_tds: Decimal = Decimal("0")
    remaining_months: int = 12


class EmployeeTaxWorksheetLineSchema(BaseModel):
    id: int
    worksheet_id: int
    line_type: str
    section_code: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal
    taxable_amount: Decimal
    tax_saving_amount: Decimal

    class Config:
        from_attributes = True


class EmployeeTaxWorksheetSchema(BaseModel):
    id: int
    employee_id: int
    financial_year: str
    tax_regime_id: Optional[int] = None
    gross_taxable_income: Decimal
    exemptions: Decimal
    deductions: Decimal
    previous_employment_income: Decimal
    previous_tds: Decimal
    projected_tax: Decimal
    monthly_tds: Decimal
    paid_tds: Decimal
    balance_tax: Decimal
    status: str
    generated_at: Optional[datetime] = None
    lines: List[EmployeeTaxWorksheetLineSchema] = []

    class Config:
        from_attributes = True


class PFRuleCreate(BaseModel):
    name: str
    wage_ceiling: Decimal = Decimal("15000")
    employee_rate: Decimal = Decimal("12")
    employer_rate: Decimal = Decimal("12")
    eps_rate: Decimal = Decimal("8.33")
    edli_rate: Decimal = Decimal("0.5")
    admin_charge_rate: Decimal = Decimal("0.5")
    effective_from: date_type
    effective_to: Optional[date_type] = None
    rounding_rule: str = "Nearest Rupee"


class PFRuleSchema(PFRuleCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class ESIRuleCreate(BaseModel):
    name: str
    wage_threshold: Decimal = Decimal("21000")
    employee_rate: Decimal = Decimal("0.75")
    employer_rate: Decimal = Decimal("3.25")
    effective_from: date_type
    effective_to: Optional[date_type] = None
    rounding_rule: str = "Nearest Rupee"


class ESIRuleSchema(ESIRuleCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class ProfessionalTaxSlabCreate(BaseModel):
    state: str
    salary_from: Decimal = Decimal("0")
    salary_to: Optional[Decimal] = None
    employee_amount: Decimal = Decimal("0")
    month: Optional[int] = None
    effective_from: date_type
    effective_to: Optional[date_type] = None


class ProfessionalTaxSlabSchema(ProfessionalTaxSlabCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class LWFSlabCreate(BaseModel):
    state: str
    salary_from: Decimal = Decimal("0")
    salary_to: Optional[Decimal] = None
    employee_amount: Decimal = Decimal("0")
    employer_amount: Decimal = Decimal("0")
    deduction_month: Optional[int] = None
    effective_from: date_type
    effective_to: Optional[date_type] = None


class LWFSlabSchema(LWFSlabCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class GratuityRuleCreate(BaseModel):
    name: str
    days_per_year: Decimal = Decimal("15")
    wage_days_divisor: Decimal = Decimal("26")
    min_service_years: Decimal = Decimal("5")
    effective_from: date_type
    effective_to: Optional[date_type] = None
    rounding_rule: str = "Nearest Rupee"


class GratuityRuleSchema(GratuityRuleCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class EmployeeStatutoryProfileCreate(BaseModel):
    employee_id: int
    uan: Optional[str] = None
    pf_join_date: Optional[date_type] = None
    pf_exit_date: Optional[date_type] = None
    pf_applicable: bool = True
    pension_applicable: bool = True
    esi_ip_number: Optional[str] = None
    esi_applicable: bool = False
    pt_state: Optional[str] = None
    lwf_applicable: bool = False
    nominee_json: Optional[dict] = None


class EmployeeStatutoryProfileSchema(EmployeeStatutoryProfileCreate):
    id: int

    class Config:
        from_attributes = True


class StatutoryCalculationRequest(BaseModel):
    employee_id: int
    month: int
    year: int
    state: Optional[str] = None
    gross_salary: Decimal
    pf_wage: Optional[Decimal] = None
    esi_wage: Optional[Decimal] = None
    gratuity_wage: Optional[Decimal] = None
    service_years: Decimal = Decimal("0")
    payroll_record_id: Optional[int] = None


class PayrollStatutoryContributionLineSchema(BaseModel):
    id: int
    payroll_record_id: Optional[int] = None
    employee_id: int
    component: str
    wage_base: Decimal
    employee_amount: Decimal
    employer_amount: Decimal
    admin_charge: Decimal
    edli_amount: Decimal
    rule_id: Optional[int] = None
    rule_type: Optional[str] = None

    class Config:
        from_attributes = True


class StatutoryCalculationSchema(BaseModel):
    employee_id: int
    month: int
    year: int
    total_employee_amount: Decimal
    total_employer_amount: Decimal
    lines: List[PayrollStatutoryContributionLineSchema]


class PayrollAttendanceInputCreate(BaseModel):
    period_id: int
    employee_id: int
    working_days: Decimal = Decimal("0")
    payable_days: Decimal = Decimal("0")
    present_days: Decimal = Decimal("0")
    paid_leave_days: Decimal = Decimal("0")
    unpaid_leave_days: Decimal = Decimal("0")
    lop_days: Decimal = Decimal("0")
    holiday_days: Decimal = Decimal("0")
    weekly_off_days: Decimal = Decimal("0")
    ot_hours: Decimal = Decimal("0")
    source_status: str = "Draft"


class PayrollAttendanceInputSchema(PayrollAttendanceInputCreate):
    id: int
    locked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LOPAdjustmentCreate(BaseModel):
    period_id: int
    employee_id: int
    adjustment_days: Decimal
    reason: Optional[str] = None
    source: str = "Manual"
    status: str = "Pending"


class LOPAdjustmentReview(BaseModel):
    action: str
    remarks: Optional[str] = None


class LOPAdjustmentSchema(LOPAdjustmentCreate):
    id: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OvertimePolicyCreate(BaseModel):
    name: str
    pay_group_id: Optional[int] = None
    wage_base: str = "Basic"
    regular_multiplier: Decimal = Decimal("1.5")
    weekend_multiplier: Decimal = Decimal("2")
    holiday_multiplier: Decimal = Decimal("2")
    min_hours: Decimal = Decimal("0")
    max_hours_per_month: Optional[Decimal] = None
    component_id: Optional[int] = None
    approval_required: bool = True
    effective_from: date_type
    effective_to: Optional[date_type] = None


class OvertimePolicySchema(OvertimePolicyCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class OvertimePayLineCreate(BaseModel):
    period_id: int
    employee_id: int
    policy_id: Optional[int] = None
    approved_overtime_request_id: Optional[int] = None
    ot_date: Optional[date_type] = None
    hours: Decimal
    multiplier: Decimal = Decimal("1")
    hourly_rate: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    source: str = "Manual"
    status: str = "Pending"


class OvertimePayLineSchema(OvertimePayLineCreate):
    id: int
    payroll_record_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LeaveEncashmentPolicyCreate(BaseModel):
    name: str
    leave_type_id: int
    pay_group_id: Optional[int] = None
    formula: str = "basic_per_day * days"
    max_days: Optional[Decimal] = None
    tax_treatment: str = "Taxable"
    component_id: Optional[int] = None
    effective_from: date_type
    effective_to: Optional[date_type] = None


class LeaveEncashmentPolicySchema(LeaveEncashmentPolicyCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class LeaveEncashmentLineCreate(BaseModel):
    period_id: int
    employee_id: int
    policy_id: Optional[int] = None
    leave_type_id: Optional[int] = None
    days: Decimal
    rate_per_day: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    tax_treatment: str = "Taxable"
    status: str = "Pending"


class LeaveEncashmentLineSchema(LeaveEncashmentLineCreate):
    id: int
    payroll_record_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollAttendanceReconcileRequest(BaseModel):
    period_id: int
    employee_ids: List[int] = []
    approve_inputs: bool = False


class PayrollInputExceptionSchema(BaseModel):
    employee_id: int
    issue: str


class PayrollAttendanceReconcileSchema(BaseModel):
    period_id: int
    inputs_created: int
    overtime_lines_created: int
    exceptions: List[PayrollInputExceptionSchema] = []


class PayrollRunEmployeeSchema(BaseModel):
    id: int
    payroll_run_id: int
    employee_id: int
    payroll_record_id: Optional[int] = None
    status: str
    hold_reason: Optional[str] = None
    skip_reason: Optional[str] = None
    input_status: str
    calculation_status: str
    approval_status: str
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    variance_status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollRunEmployeeAction(BaseModel):
    action: str
    reason: Optional[str] = None


class PayrollCalculationSnapshotSchema(BaseModel):
    id: int
    payroll_run_id: int
    run_employee_id: Optional[int] = None
    employee_id: int
    snapshot_type: str
    salary_template_json: Optional[dict] = None
    tax_worksheet_json: Optional[dict] = None
    attendance_input_json: Optional[dict] = None
    statutory_profile_json: Optional[dict] = None
    formula_version_json: Optional[dict] = None
    result_json: Optional[dict] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollWorksheetProcessSchema(BaseModel):
    payroll_run_id: int
    employees_processed: int
    snapshots_created: int
    blocked: List[str] = []


class PayrollArrearLineCreate(BaseModel):
    employee_id: int
    component_id: Optional[int] = None
    component_name: str
    arrear_type: str = "Earning"
    from_date: Optional[date_type] = None
    to_date: Optional[date_type] = None
    amount: Decimal
    reason: Optional[str] = None
    status: str = "Pending"


class PayrollArrearRunCreate(BaseModel):
    payroll_run_id: Optional[int] = None
    period_id: Optional[int] = None
    name: str
    reason: Optional[str] = None
    lines: List[PayrollArrearLineCreate] = []


class PayrollArrearLineSchema(PayrollArrearLineCreate):
    id: int
    arrear_run_id: int
    payroll_record_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollArrearRunSchema(BaseModel):
    id: int
    payroll_run_id: Optional[int] = None
    period_id: Optional[int] = None
    name: str
    reason: Optional[str] = None
    status: str
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    lines: List[PayrollArrearLineSchema] = []

    class Config:
        from_attributes = True


class OffCyclePayrollRunCreate(BaseModel):
    month: int
    year: int
    run_type: str = "Correction"
    pay_group_id: Optional[int] = None
    period_id: Optional[int] = None
    reason: Optional[str] = None
    total_amount: Decimal = Decimal("0")
    scheduled_payment_date: Optional[date_type] = None


class OffCyclePayrollRunSchema(OffCyclePayrollRunCreate):
    id: int
    status: str
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollPaymentBatchCreate(BaseModel):
    payroll_run_id: int
    bank_format_id: Optional[int] = None
    debit_account: Optional[str] = None


class PayrollPaymentLineSchema(BaseModel):
    id: int
    batch_id: int
    payroll_record_id: Optional[int] = None
    employee_id: int
    net_amount: Decimal
    bank_account: Optional[str] = None
    ifsc: Optional[str] = None
    payment_status: str
    utr_number: Optional[str] = None
    failure_reason: Optional[str] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayrollPaymentBatchSchema(BaseModel):
    id: int
    payroll_run_id: int
    bank_format_id: Optional[int] = None
    debit_account: Optional[str] = None
    total_amount: Decimal
    status: str
    generated_file_url: Optional[str] = None
    approved_by: Optional[int] = None
    released_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    lines: List[PayrollPaymentLineSchema] = []

    class Config:
        from_attributes = True


class PayrollPaymentStatusImportLine(BaseModel):
    employee_id: Optional[int] = None
    payroll_record_id: Optional[int] = None
    utr_number: Optional[str] = None
    payment_status: str
    failure_reason: Optional[str] = None


class PayrollPaymentStatusImportRequest(BaseModel):
    lines: List[PayrollPaymentStatusImportLine]


class PayrollPaymentStatusImportSchema(BaseModel):
    batch_id: int
    updated: int
    failed: int


class AccountingLedgerCreate(BaseModel):
    name: str
    code: str
    ledger_type: str
    description: Optional[str] = None


class AccountingLedgerSchema(AccountingLedgerCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class PayrollGLMappingCreate(BaseModel):
    component_name: str
    component_type: str
    debit_ledger_id: Optional[int] = None
    credit_ledger_id: Optional[int] = None
    legal_entity_id: Optional[int] = None
    branch_id: Optional[int] = None
    department_id: Optional[int] = None
    cost_center: Optional[str] = None


class PayrollGLMappingSchema(PayrollGLMappingCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class PayrollJournalLineSchema(BaseModel):
    id: int
    journal_entry_id: int
    ledger_id: Optional[int] = None
    ledger_code: Optional[str] = None
    ledger_name: Optional[str] = None
    employee_id: Optional[int] = None
    component_name: Optional[str] = None
    debit: Decimal
    credit: Decimal
    memo: Optional[str] = None

    class Config:
        from_attributes = True


class PayrollJournalEntrySchema(BaseModel):
    id: int
    payroll_run_id: int
    legal_entity_id: Optional[int] = None
    branch_id: Optional[int] = None
    department_id: Optional[int] = None
    cost_center: Optional[str] = None
    status: str
    total_debit: Decimal
    total_credit: Decimal
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    lines: List[PayrollJournalLineSchema] = []

    class Config:
        from_attributes = True


class StatutoryFileValidationRequest(BaseModel):
    payroll_run_id: Optional[int] = None
    period_id: Optional[int] = None
    file_type: str


class StatutoryFileValidationSchema(BaseModel):
    id: int
    payroll_run_id: Optional[int] = None
    period_id: Optional[int] = None
    file_type: str
    status: str
    total_rows: int
    error_count: int
    warning_count: int
    output_file_url: Optional[str] = None
    validation_errors_json: Optional[list] = None
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatutoryTemplateFileSchema(BaseModel):
    id: int
    template_type: str
    format_version: str
    file_url: str
    status: str
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatutoryChallanCreate(BaseModel):
    legal_entity_id: Optional[int] = None
    pay_group_id: Optional[int] = None
    period_id: Optional[int] = None
    challan_type: str
    due_date: date_type
    amount: Decimal = Decimal("0")
    file_url: Optional[str] = None


class StatutoryChallanGenerateRequest(BaseModel):
    legal_entity_id: Optional[int] = None
    pay_group_id: Optional[int] = None
    period_id: Optional[int] = None
    challan_type: str
    due_date: date_type


class StatutoryChallanSchema(StatutoryChallanCreate):
    id: int
    status: str
    payment_reference: Optional[str] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatutoryReturnFileCreate(BaseModel):
    challan_id: int
    return_type: str
    format_version: str = "v1"
    file_url: Optional[str] = None


class StatutoryReturnFileSchema(StatutoryReturnFileCreate):
    id: int
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None
    validation_status: str
    validation_errors_json: Optional[list] = None

    class Config:
        from_attributes = True


class TaxDeclarationCycleCreate(BaseModel):
    name: str
    financial_year: str
    start_date: date_type
    end_date: date_type
    proof_due_date: Optional[date_type] = None
    status: str = "Open"


class TaxDeclarationCycleSchema(TaxDeclarationCycleCreate):
    id: int

    class Config:
        from_attributes = True


class TaxDeclarationCreate(BaseModel):
    cycle_id: int
    employee_id: Optional[int] = None
    section: str
    declared_amount: Decimal
    description: Optional[str] = None


class TaxDeclarationReview(BaseModel):
    status: str
    approved_amount: Optional[Decimal] = None
    review_remarks: Optional[str] = None


class TaxDeclarationProofCreate(BaseModel):
    declaration_id: int
    file_url: str
    original_filename: Optional[str] = None


class TaxDeclarationProofReview(BaseModel):
    status: str
    verification_remarks: Optional[str] = None


class TaxDeclarationProofSchema(TaxDeclarationProofCreate):
    id: int
    status: str
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    verification_remarks: Optional[str] = None

    class Config:
        from_attributes = True


class TaxDeclarationSchema(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    section: str
    declared_amount: Decimal
    approved_amount: Decimal
    description: Optional[str] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_remarks: Optional[str] = None
    proofs: List[TaxDeclarationProofSchema] = []

    class Config:
        from_attributes = True
