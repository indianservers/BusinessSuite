from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class FAMCompanyFinancialSettings(Base):
    __tablename__ = "fam_company_financial_settings"
    __table_args__ = (UniqueConstraint("company_id", name="uq_fam_company_settings"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    country_code = Column(String(2), default="IN", nullable=False)
    base_currency = Column(String(3), default="INR", nullable=False)
    gst_enabled = Column(Boolean, default=False)
    gstin = Column(String(20), nullable=True)
    legal_name = Column(String(220), nullable=True)
    trade_name = Column(String(220), nullable=True)
    pan = Column(String(20), nullable=True)
    tan = Column(String(20), nullable=True)
    cin = Column(String(30), nullable=True)
    registered_address = Column(Text, nullable=True)
    state_code = Column(String(4), nullable=True)
    financial_year_start_month = Column(Integer, default=4)
    books_start_date = Column(Date, nullable=True)
    decimal_places = Column(Integer, default=2)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMFinancialYear(Base):
    __tablename__ = "fam_financial_years"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_fam_financial_year_company_name"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    name = Column(String(80), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    status = Column(String(20), default="open", index=True)
    is_current = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMAccountingPeriod(Base):
    __tablename__ = "fam_accounting_periods"

    id = Column(Integer, primary_key=True, index=True)
    financial_year_id = Column(Integer, ForeignKey("fam_financial_years.id", ondelete="CASCADE"), nullable=False, index=True)
    period_name = Column(String(80), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default="open", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMLedgerGroup(Base):
    __tablename__ = "fam_ledger_groups"
    __table_args__ = (UniqueConstraint("company_id", "group_code", name="uq_fam_ledger_group_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    parent_group_id = Column(Integer, ForeignKey("fam_ledger_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    group_name = Column(String(160), nullable=False, index=True)
    group_code = Column(String(80), nullable=False, index=True)
    nature = Column(String(20), nullable=False, index=True)
    system_group = Column(Boolean, default=False, index=True)
    affects_gross_profit = Column(Boolean, default=False)
    sequence_order = Column(Integer, default=100)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMLedger(Base):
    __tablename__ = "fam_ledgers"
    __table_args__ = (
        UniqueConstraint("company_id", "ledger_code", name="uq_fam_ledger_company_code"),
        UniqueConstraint("company_id", "ledger_name", name="uq_fam_ledger_company_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    ledger_code = Column(String(80), nullable=False, index=True)
    ledger_name = Column(String(180), nullable=False, index=True)
    ledger_group_id = Column(Integer, ForeignKey("fam_ledger_groups.id", ondelete="RESTRICT"), nullable=False, index=True)
    nature = Column(String(20), nullable=False, index=True)
    ledger_type = Column(String(30), default="general", index=True)
    gst_applicable = Column(Boolean, default=False)
    pan = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)
    state_code = Column(String(4), nullable=True)
    billing_address = Column(Text, nullable=True)
    opening_balance_dr = Column(Numeric(14, 2), default=0)
    opening_balance_cr = Column(Numeric(14, 2), default=0)
    current_balance_dr = Column(Numeric(14, 2), default=0)
    current_balance_cr = Column(Numeric(14, 2), default=0)
    active = Column(Boolean, default=True, index=True)
    system_ledger = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMOpeningBalance(Base):
    __tablename__ = "fam_opening_balances"
    __table_args__ = (UniqueConstraint("company_id", "financial_year_id", "ledger_id", name="uq_fam_opening_balance"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    financial_year_id = Column(Integer, ForeignKey("fam_financial_years.id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    debit_amount = Column(Numeric(14, 2), default=0)
    credit_amount = Column(Numeric(14, 2), default=0)
    narration = Column(Text, nullable=True)
    posted = Column(Boolean, default=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMCostCenter(Base):
    __tablename__ = "fam_cost_centers"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_fam_cost_center_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    code = Column(String(80), nullable=False, index=True)
    name = Column(String(180), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("fam_cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMBranch(Base):
    __tablename__ = "fam_branches"
    __table_args__ = (UniqueConstraint("company_id", "branch_code", name="uq_fam_branch_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_code = Column(String(80), nullable=False, index=True)
    branch_name = Column(String(180), nullable=False, index=True)
    gstin = Column(String(20), nullable=True)
    state_code = Column(String(4), nullable=True)
    address = Column(Text, nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMAuditLog(Base):
    __tablename__ = "fam_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    module_name = Column(String(80), default="fam", index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String(80), nullable=True)
    user_agent = Column(Text, nullable=True)


class FAMVoucherType(Base):
    __tablename__ = "fam_voucher_types"
    __table_args__ = (UniqueConstraint("company_id", "voucher_type_code", name="uq_fam_voucher_type_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    voucher_type_code = Column(String(40), nullable=False, index=True)
    voucher_type_name = Column(String(120), nullable=False, index=True)
    category = Column(String(40), nullable=False, index=True)
    numbering_prefix = Column(String(30), nullable=False)
    numbering_sequence = Column(Integer, default=1, nullable=False)
    auto_numbering = Column(Boolean, default=True, nullable=False)
    active = Column(Boolean, default=True, index=True)
    system_type = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMVoucher(Base):
    __tablename__ = "fam_vouchers"
    __table_args__ = (UniqueConstraint("company_id", "voucher_number", name="uq_fam_voucher_company_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    financial_year_id = Column(Integer, ForeignKey("fam_financial_years.id", ondelete="RESTRICT"), nullable=False, index=True)
    accounting_period_id = Column(Integer, ForeignKey("fam_accounting_periods.id", ondelete="RESTRICT"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("fam_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    voucher_type_id = Column(Integer, ForeignKey("fam_voucher_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    voucher_number = Column(String(80), nullable=False, index=True)
    voucher_date = Column(Date, nullable=False, index=True)
    reference_number = Column(String(120), nullable=True, index=True)
    reference_date = Column(Date, nullable=True)
    narration = Column(Text, nullable=True)
    total_debit = Column(Numeric(14, 2), default=0)
    total_credit = Column(Numeric(14, 2), default=0)
    status = Column(String(20), default="draft", index=True)
    source_module = Column(String(40), default="fam", index=True)
    source_record_type = Column(String(80), nullable=True, index=True)
    source_record_id = Column(String(120), nullable=True, index=True)
    posted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    cancelled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    reversed_voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMVoucherLine(Base):
    __tablename__ = "fam_voucher_lines"

    id = Column(Integer, primary_key=True, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    debit_amount = Column(Numeric(14, 2), default=0)
    credit_amount = Column(Numeric(14, 2), default=0)
    narration = Column(Text, nullable=True)
    cost_center_id = Column(Integer, ForeignKey("fam_cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("fam_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    party_id = Column(Integer, nullable=True, index=True)
    tax_component_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMLedgerEntry(Base):
    __tablename__ = "fam_ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    financial_year_id = Column(Integer, ForeignKey("fam_financial_years.id", ondelete="RESTRICT"), nullable=False, index=True)
    accounting_period_id = Column(Integer, ForeignKey("fam_accounting_periods.id", ondelete="RESTRICT"), nullable=True, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="RESTRICT"), nullable=False, index=True)
    voucher_line_id = Column(Integer, ForeignKey("fam_voucher_lines.id", ondelete="RESTRICT"), nullable=False, index=True)
    voucher_number = Column(String(80), nullable=False, index=True)
    voucher_date = Column(Date, nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    debit_amount = Column(Numeric(14, 2), default=0)
    credit_amount = Column(Numeric(14, 2), default=0)
    running_balance = Column(Numeric(14, 2), default=0)
    narration = Column(Text, nullable=True)
    source_module = Column(String(40), default="fam", index=True)
    source_record_type = Column(String(80), nullable=True, index=True)
    source_record_id = Column(String(120), nullable=True, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FAMVoucherAuditLog(Base):
    __tablename__ = "fam_voucher_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(80), nullable=False, index=True)
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMParty(Base):
    __tablename__ = "fam_parties"
    __table_args__ = (
        UniqueConstraint("company_id", "party_code", name="uq_fam_party_company_code"),
        UniqueConstraint("company_id", "ledger_id", name="uq_fam_party_company_ledger"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    party_type = Column(String(20), nullable=False, index=True)
    crm_account_id = Column(Integer, nullable=True, index=True)
    crm_contact_id = Column(Integer, nullable=True, index=True)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    party_code = Column(String(80), nullable=False, index=True)
    legal_name = Column(String(220), nullable=False, index=True)
    trade_name = Column(String(220), nullable=True, index=True)
    pan = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)
    registration_type = Column(String(30), default="regular", index=True)
    state_code = Column(String(4), nullable=True)
    billing_address = Column(Text, nullable=True)
    shipping_address = Column(Text, nullable=True)
    email = Column(String(180), nullable=True)
    phone = Column(String(60), nullable=True)
    mobile = Column(String(60), nullable=True)
    payment_terms_days = Column(Integer, default=30)
    credit_limit = Column(Numeric(14, 2), default=0)
    opening_balance_dr = Column(Numeric(14, 2), default=0)
    opening_balance_cr = Column(Numeric(14, 2), default=0)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMPartyContact(Base):
    __tablename__ = "fam_party_contacts"

    id = Column(Integer, primary_key=True, index=True)
    party_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    email = Column(String(180), nullable=True)
    phone = Column(String(60), nullable=True)
    designation = Column(String(120), nullable=True)
    is_primary = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FAMBillReference(Base):
    __tablename__ = "fam_bill_references"
    __table_args__ = (UniqueConstraint("company_id", "party_id", "bill_number", name="uq_fam_bill_company_party_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    party_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    voucher_line_id = Column(Integer, ForeignKey("fam_voucher_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    bill_number = Column(String(120), nullable=False, index=True)
    bill_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)
    bill_type = Column(String(30), nullable=False, index=True)
    original_amount = Column(Numeric(14, 2), default=0)
    outstanding_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="open", index=True)
    source_module = Column(String(40), default="fam", index=True)
    source_record_type = Column(String(80), nullable=True, index=True)
    source_record_id = Column(String(120), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMBillAllocation(Base):
    __tablename__ = "fam_bill_allocations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    allocation_date = Column(Date, nullable=False, index=True)
    party_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False, index=True)
    from_bill_reference_id = Column(Integer, ForeignKey("fam_bill_references.id", ondelete="RESTRICT"), nullable=False, index=True)
    to_bill_reference_id = Column(Integer, ForeignKey("fam_bill_references.id", ondelete="RESTRICT"), nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    allocated_amount = Column(Numeric(14, 2), default=0)
    allocation_type = Column(String(30), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FAMPartyCreditTerm(Base):
    __tablename__ = "fam_party_credit_terms"

    id = Column(Integer, primary_key=True, index=True)
    party_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False, index=True)
    terms_name = Column(String(120), nullable=False)
    days = Column(Integer, default=30)
    discount_percentage = Column(Numeric(6, 2), default=0)
    active = Column(Boolean, default=True, index=True)


class FAMSRMMapping(Base):
    __tablename__ = "fam_srm_mapping"
    __table_args__ = (
        UniqueConstraint("company_id", "srm_record_type", "srm_record_id", "fam_record_type", name="uq_fam_srm_mapping_source_target"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    srm_record_type = Column(String(40), nullable=False, index=True)
    srm_record_id = Column(Integer, nullable=False, index=True)
    fam_record_type = Column(String(40), nullable=False, index=True)
    fam_record_id = Column(Integer, nullable=False, index=True)
    mapping_status = Column(String(40), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMPostingJob(Base):
    __tablename__ = "fam_posting_jobs"
    __table_args__ = (
        UniqueConstraint("company_id", "source_module", "source_record_type", "source_record_id", "posting_type", name="uq_fam_posting_job_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    source_module = Column(String(40), default="srm", nullable=False, index=True)
    source_record_type = Column(String(80), nullable=False, index=True)
    source_record_id = Column(Integer, nullable=False, index=True)
    posting_type = Column(String(40), nullable=False, index=True)
    status = Column(String(30), default="pending", index=True)
    error_message = Column(Text, nullable=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    retry_count = Column(Integer, default=0)
    posted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMPostingRule(Base):
    __tablename__ = "fam_posting_rules"
    __table_args__ = (UniqueConstraint("company_id", "source_module", "transaction_type", name="uq_fam_posting_rule"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    source_module = Column(String(40), default="srm", nullable=False, index=True)
    transaction_type = Column(String(80), nullable=False, index=True)
    debit_ledger_rule_json = Column(JSON, nullable=True)
    credit_ledger_rule_json = Column(JSON, nullable=True)
    tax_ledger_rule_json = Column(JSON, nullable=True)
    roundoff_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMBankAccount(Base):
    __tablename__ = "fam_bank_accounts"
    __table_args__ = (UniqueConstraint("company_id", "ledger_id", name="uq_fam_bank_account_company_ledger"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_name = Column(String(180), nullable=False, index=True)
    branch_name = Column(String(180), nullable=True)
    account_number_masked = Column(String(80), nullable=False, index=True)
    ifsc = Column(String(20), nullable=True, index=True)
    account_type = Column(String(40), default="current", index=True)
    opening_balance = Column(Numeric(14, 2), default=0)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMPaymentMode(Base):
    __tablename__ = "fam_payment_modes"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_fam_payment_mode_company_name"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    type = Column(String(30), nullable=False, index=True)
    default_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMBankStatement(Base):
    __tablename__ = "fam_bank_statements"
    __table_args__ = (UniqueConstraint("company_id", "bank_account_id", "imported_file_hash", name="uq_fam_bank_statement_file_hash"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    bank_account_id = Column(Integer, ForeignKey("fam_bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    statement_period_start = Column(Date, nullable=False, index=True)
    statement_period_end = Column(Date, nullable=False, index=True)
    imported_file_name = Column(String(220), nullable=False)
    imported_file_hash = Column(String(128), nullable=False, index=True)
    status = Column(String(30), default="imported", index=True)
    imported_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMBankStatementLine(Base):
    __tablename__ = "fam_bank_statement_lines"
    __table_args__ = (UniqueConstraint("statement_id", "line_hash", name="uq_fam_bank_statement_line_hash"),)

    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("fam_bank_statements.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_date = Column(Date, nullable=False, index=True)
    value_date = Column(Date, nullable=True, index=True)
    description = Column(Text, nullable=False)
    reference_number = Column(String(160), nullable=True, index=True)
    debit_amount = Column(Numeric(14, 2), default=0)
    credit_amount = Column(Numeric(14, 2), default=0)
    balance = Column(Numeric(14, 2), default=0)
    matched_status = Column(String(30), default="unmatched", index=True)
    matched_voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    line_hash = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMBankReconciliationMatch(Base):
    __tablename__ = "fam_bank_reconciliation_matches"
    __table_args__ = (UniqueConstraint("statement_line_id", "voucher_id", name="uq_fam_bank_recon_line_voucher"),)

    id = Column(Integer, primary_key=True, index=True)
    statement_line_id = Column(Integer, ForeignKey("fam_bank_statement_lines.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="RESTRICT"), nullable=False, index=True)
    ledger_entry_id = Column(Integer, ForeignKey("fam_ledger_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    match_type = Column(String(30), nullable=False, index=True)
    confidence_score = Column(Numeric(5, 2), default=0)
    matched_amount = Column(Numeric(14, 2), default=0)
    matched_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_at = Column(DateTime(timezone=True), nullable=True, index=True)


class FAMBankReconciliationSession(Base):
    __tablename__ = "fam_bank_reconciliation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    bank_account_id = Column(Integer, ForeignKey("fam_bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    statement_id = Column(Integer, ForeignKey("fam_bank_statements.id", ondelete="CASCADE"), nullable=False, index=True)
    book_balance = Column(Numeric(14, 2), default=0)
    bank_statement_balance = Column(Numeric(14, 2), default=0)
    unreconciled_count = Column(Integer, default=0)
    status = Column(String(30), default="open", index=True)
    reconciled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMCashRegister(Base):
    __tablename__ = "fam_cash_registers"
    __table_args__ = (UniqueConstraint("company_id", "ledger_id", name="uq_fam_cash_register_company_ledger"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    register_name = Column(String(160), nullable=False, index=True)
    location = Column(String(160), nullable=True)
    opening_balance = Column(Numeric(14, 2), default=0)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMPaymentReference(Base):
    __tablename__ = "fam_payment_references"
    __table_args__ = (UniqueConstraint("company_id", "reference_number", "payment_mode_id", name="uq_fam_payment_reference"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_line_id = Column(Integer, ForeignKey("fam_voucher_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_mode_id = Column(Integer, ForeignKey("fam_payment_modes.id", ondelete="SET NULL"), nullable=True, index=True)
    reference_number = Column(String(160), nullable=False, index=True)
    reference_date = Column(Date, nullable=True, index=True)
    bank_account_id = Column(Integer, ForeignKey("fam_bank_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="recorded", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMTaxRegistration(Base):
    __tablename__ = "fam_tax_registrations"
    __table_args__ = (UniqueConstraint("company_id", "gstin", name="uq_fam_tax_registration_gstin"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    gstin = Column(String(20), nullable=False, index=True)
    legal_name = Column(String(220), nullable=False, index=True)
    trade_name = Column(String(220), nullable=True)
    state_code = Column(String(4), nullable=False, index=True)
    registration_type = Column(String(40), default="regular", index=True)
    effective_from = Column(Date, nullable=False, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMGSTRate(Base):
    __tablename__ = "fam_gst_rates"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    rate_name = Column(String(120), nullable=False, index=True)
    tax_type = Column(String(30), nullable=False, index=True)
    cgst_rate = Column(Numeric(7, 3), default=0)
    sgst_rate = Column(Numeric(7, 3), default=0)
    igst_rate = Column(Numeric(7, 3), default=0)
    cess_rate = Column(Numeric(7, 3), default=0)
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMHSNSACCode(Base):
    __tablename__ = "fam_hsn_sac_codes"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_fam_hsn_sac_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    code = Column(String(30), nullable=False, index=True)
    description = Column(Text, nullable=False)
    type = Column(String(10), nullable=False, index=True)
    default_gst_rate_id = Column(Integer, ForeignKey("fam_gst_rates.id", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMGSTTransactionLine(Base):
    __tablename__ = "fam_gst_transaction_lines"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=True, index=True)
    voucher_line_id = Column(Integer, ForeignKey("fam_voucher_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_type = Column(String(30), nullable=False, index=True)
    party_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="SET NULL"), nullable=True, index=True)
    gstin = Column(String(20), nullable=True, index=True)
    place_of_supply_state = Column(String(4), nullable=True, index=True)
    supply_type = Column(String(30), nullable=False, index=True)
    hsn_sac_code = Column(String(30), nullable=True, index=True)
    taxable_value = Column(Numeric(14, 2), default=0)
    cgst_amount = Column(Numeric(14, 2), default=0)
    sgst_amount = Column(Numeric(14, 2), default=0)
    igst_amount = Column(Numeric(14, 2), default=0)
    cess_amount = Column(Numeric(14, 2), default=0)
    itc_eligible = Column(Boolean, default=False, index=True)
    reverse_charge = Column(Boolean, default=False, index=True)
    exempt_type = Column(String(30), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMGSTReturnPeriod(Base):
    __tablename__ = "fam_gst_return_periods"
    __table_args__ = (UniqueConstraint("company_id", "period_month", "period_year", "return_type", name="uq_fam_gst_return_period"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    period_month = Column(Integer, nullable=False, index=True)
    period_year = Column(Integer, nullable=False, index=True)
    return_type = Column(String(20), nullable=False, index=True)
    status = Column(String(30), default="draft", index=True)
    prepared_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    prepared_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMGSTR1Record(Base):
    __tablename__ = "fam_gstr1_records"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    return_period_id = Column(Integer, ForeignKey("fam_gst_return_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(30), nullable=False, index=True)
    taxable_value = Column(Numeric(14, 2), default=0)
    cgst_amount = Column(Numeric(14, 2), default=0)
    sgst_amount = Column(Numeric(14, 2), default=0)
    igst_amount = Column(Numeric(14, 2), default=0)
    cess_amount = Column(Numeric(14, 2), default=0)
    record_count = Column(Integer, default=0)
    source_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMGSTR3BRecord(Base):
    __tablename__ = "fam_gstr3b_records"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    return_period_id = Column(Integer, ForeignKey("fam_gst_return_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(30), nullable=False, index=True)
    taxable_value = Column(Numeric(14, 2), default=0)
    cgst_amount = Column(Numeric(14, 2), default=0)
    sgst_amount = Column(Numeric(14, 2), default=0)
    igst_amount = Column(Numeric(14, 2), default=0)
    cess_amount = Column(Numeric(14, 2), default=0)
    source_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMGSTReconciliationItem(Base):
    __tablename__ = "fam_gst_reconciliation_items"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    return_period_id = Column(Integer, ForeignKey("fam_gst_return_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type = Column(String(40), nullable=False, index=True)
    source_record_id = Column(Integer, nullable=True, index=True)
    mismatch_type = Column(String(80), nullable=False, index=True)
    expected_amount = Column(Numeric(14, 2), default=0)
    actual_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="open", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMEInvoiceSettings(Base):
    __tablename__ = "fam_einvoice_settings"
    __table_args__ = (UniqueConstraint("company_id", name="uq_fam_einvoice_settings_company"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    provider_name = Column(String(120), nullable=True)
    api_base_url = Column(String(300), nullable=True)
    credentials_configured = Column(Boolean, default=False, index=True)
    applicable_from = Column(Date, nullable=True)
    applicability_json = Column(JSON, nullable=True)
    active = Column(Boolean, default=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMEInvoiceJob(Base):
    __tablename__ = "fam_einvoice_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)
    status = Column(String(30), default="not_configured", index=True)
    irn = Column(String(120), nullable=True, index=True)
    ack_number = Column(String(120), nullable=True)
    ack_date = Column(DateTime(timezone=True), nullable=True)
    qr_code_payload = Column(Text, nullable=True)
    provider_response_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMEWayBillSettings(Base):
    __tablename__ = "fam_ewaybill_settings"
    __table_args__ = (UniqueConstraint("company_id", name="uq_fam_ewaybill_settings_company"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    provider_name = Column(String(120), nullable=True)
    api_base_url = Column(String(300), nullable=True)
    credentials_configured = Column(Boolean, default=False, index=True)
    threshold_amount = Column(Numeric(14, 2), default=50000)
    applicability_json = Column(JSON, nullable=True)
    active = Column(Boolean, default=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMEWayBillJob(Base):
    __tablename__ = "fam_ewaybill_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)
    status = Column(String(30), default="not_configured", index=True)
    transporter_details = Column(Text, nullable=True)
    vehicle_number = Column(String(40), nullable=True)
    distance_km = Column(Integer, nullable=True)
    supply_type = Column(String(30), nullable=True)
    document_type = Column(String(30), nullable=True)
    ewb_number = Column(String(120), nullable=True, index=True)
    ewb_date = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    provider_response_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMGSTAuditLog(Base):
    __tablename__ = "fam_gst_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMPurchaseBill(Base):
    __tablename__ = "fam_purchase_bills"
    __table_args__ = (UniqueConstraint("company_id", "vendor_id", "bill_number", name="uq_fam_purchase_bill_vendor_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="RESTRICT"), nullable=False, index=True)
    bill_number = Column(String(120), nullable=False, index=True)
    bill_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True, index=True)
    gstin = Column(String(20), nullable=True, index=True)
    place_of_supply = Column(String(4), nullable=True, index=True)
    subtotal = Column(Numeric(14, 2), default=0)
    discount_total = Column(Numeric(14, 2), default=0)
    gst_total = Column(Numeric(14, 2), default=0)
    tds_amount = Column(Numeric(14, 2), default=0)
    grand_total = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="draft", index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMPurchaseBillLine(Base):
    __tablename__ = "fam_purchase_bill_lines"

    id = Column(Integer, primary_key=True, index=True)
    purchase_bill_id = Column(Integer, ForeignKey("fam_purchase_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    expense_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id = Column(Integer, nullable=True, index=True)
    description = Column(Text, nullable=False)
    hsn_sac = Column(String(30), nullable=True, index=True)
    quantity = Column(Numeric(14, 3), default=1)
    rate = Column(Numeric(14, 2), default=0)
    taxable_value = Column(Numeric(14, 2), default=0)
    gst_rate_id = Column(Integer, ForeignKey("fam_gst_rates.id", ondelete="SET NULL"), nullable=True, index=True)
    gst_amount = Column(Numeric(14, 2), default=0)
    tds_section_id = Column(Integer, ForeignKey("fam_tds_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    tds_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)


class FAMExpenseClaim(Base):
    __tablename__ = "fam_expense_claims"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    claim_number = Column(String(120), nullable=False, index=True)
    claimant_name = Column(String(180), nullable=True, index=True)
    claim_date = Column(Date, nullable=False, index=True)
    payable_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    subtotal = Column(Numeric(14, 2), default=0)
    gst_total = Column(Numeric(14, 2), default=0)
    grand_total = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="draft", index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMExpenseLine(Base):
    __tablename__ = "fam_expense_lines"

    id = Column(Integer, primary_key=True, index=True)
    expense_claim_id = Column(Integer, ForeignKey("fam_expense_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    expense_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    hsn_sac = Column(String(30), nullable=True, index=True)
    taxable_value = Column(Numeric(14, 2), default=0)
    gst_rate_id = Column(Integer, ForeignKey("fam_gst_rates.id", ondelete="SET NULL"), nullable=True, index=True)
    gst_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)


class FAMTDSSection(Base):
    __tablename__ = "fam_tds_sections"
    __table_args__ = (UniqueConstraint("company_id", "section_code", name="uq_fam_tds_section_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    section_code = Column(String(40), nullable=False, index=True)
    description = Column(Text, nullable=False)
    default_rate = Column(Numeric(7, 3), default=0)
    threshold_amount = Column(Numeric(14, 2), default=0)
    effective_from = Column(Date, nullable=False, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMTDSRate(Base):
    __tablename__ = "fam_tds_rates"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("fam_tds_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    rate = Column(Numeric(7, 3), default=0)
    threshold_amount = Column(Numeric(14, 2), default=0)
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    active = Column(Boolean, default=True, index=True)


class FAMTDSTransaction(Base):
    __tablename__ = "fam_tds_transactions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="SET NULL"), nullable=True, index=True)
    section_id = Column(Integer, ForeignKey("fam_tds_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    taxable_amount = Column(Numeric(14, 2), default=0)
    tds_rate = Column(Numeric(7, 3), default=0)
    tds_amount = Column(Numeric(14, 2), default=0)
    deduction_date = Column(Date, nullable=False, index=True)
    status = Column(String(30), default="deducted", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMVendorPaymentRun(Base):
    __tablename__ = "fam_vendor_payment_runs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    run_number = Column(String(120), nullable=False, index=True)
    payment_date = Column(Date, nullable=False, index=True)
    bank_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False, index=True)
    total_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="prepared", index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMVendorPaymentItem(Base):
    __tablename__ = "fam_vendor_payment_items"

    id = Column(Integer, primary_key=True, index=True)
    payment_run_id = Column(Integer, ForeignKey("fam_vendor_payment_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("fam_parties.id", ondelete="RESTRICT"), nullable=False, index=True)
    purchase_bill_id = Column(Integer, ForeignKey("fam_purchase_bills.id", ondelete="SET NULL"), nullable=True, index=True)
    bill_reference_id = Column(Integer, ForeignKey("fam_bill_references.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Numeric(14, 2), default=0)
    status = Column(String(30), default="prepared", index=True)


class FAMPurchaseAuditLog(Base):
    __tablename__ = "fam_purchase_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMStockGroup(Base):
    __tablename__ = "fam_stock_groups"
    __table_args__ = (UniqueConstraint("company_id", "group_code", name="uq_fam_stock_group_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    parent_group_id = Column(Integer, ForeignKey("fam_stock_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    group_code = Column(String(80), nullable=False, index=True)
    group_name = Column(String(180), nullable=False, index=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMUnitOfMeasure(Base):
    __tablename__ = "fam_units_of_measure"
    __table_args__ = (UniqueConstraint("company_id", "unit_code", name="uq_fam_uom_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    unit_code = Column(String(40), nullable=False, index=True)
    unit_name = Column(String(120), nullable=False, index=True)
    symbol = Column(String(20), nullable=True)
    decimal_allowed = Column(Boolean, default=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMWarehouse(Base):
    __tablename__ = "fam_warehouses"
    __table_args__ = (UniqueConstraint("company_id", "warehouse_code", name="uq_fam_warehouse_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    warehouse_code = Column(String(80), nullable=False, index=True)
    warehouse_name = Column(String(180), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("fam_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    address = Column(Text, nullable=True)
    contact_person = Column(String(180), nullable=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(180), nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMStockItem(Base):
    __tablename__ = "fam_stock_items"
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_fam_stock_item_company_sku"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    stock_group_id = Column(Integer, ForeignKey("fam_stock_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_id = Column(Integer, ForeignKey("fam_units_of_measure.id", ondelete="SET NULL"), nullable=True, index=True)
    default_warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    inventory_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    sales_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    cogs_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    adjustment_gain_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    adjustment_loss_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    grni_ledger_id = Column(Integer, ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_center_id = Column(Integer, ForeignKey("fam_cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("fam_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    valuation_method = Column(String(40), default="weighted_average", index=True)
    sku = Column(String(80), nullable=False, index=True)
    item_name = Column(String(220), nullable=False, index=True)
    barcode = Column(String(120), nullable=True, index=True)
    description = Column(Text, nullable=True)
    hsn_code = Column(String(30), nullable=True, index=True)
    gst_rate_id = Column(Integer, ForeignKey("fam_gst_rates.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_rate = Column(Numeric(14, 2), default=0)
    sales_rate = Column(Numeric(14, 2), default=0)
    current_quantity = Column(Numeric(14, 3), default=0)
    average_cost = Column(Numeric(14, 4), default=0)
    reorder_level = Column(Numeric(14, 3), default=0)
    min_stock = Column(Numeric(14, 3), default=0)
    max_stock = Column(Numeric(14, 3), default=0)
    track_inventory = Column(Boolean, default=True, index=True)
    batch_tracking = Column(Boolean, default=False)
    serial_tracking = Column(Boolean, default=False)
    expiry_tracking = Column(Boolean, default=False)
    active = Column(Boolean, default=True, index=True)
    source_app_reference = Column(String(120), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMStockOpeningBalance(Base):
    __tablename__ = "fam_stock_opening_balances"
    __table_args__ = (UniqueConstraint("company_id", "stock_item_id", "warehouse_id", "opening_date", name="uq_fam_stock_opening_item_warehouse_date"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    opening_number = Column(String(120), nullable=False, index=True)
    opening_date = Column(Date, nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("fam_stock_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Numeric(14, 3), nullable=False)
    rate = Column(Numeric(14, 4), default=0)
    value = Column(Numeric(14, 2), default=0)
    notes = Column(Text, nullable=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMStockMovement(Base):
    __tablename__ = "fam_stock_movements"
    __table_args__ = (UniqueConstraint("company_id", "movement_number", name="uq_fam_stock_movement_company_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    movement_number = Column(String(120), nullable=False, index=True)
    movement_date = Column(Date, nullable=False, index=True)
    movement_type = Column(String(40), nullable=False, index=True)
    status = Column(String(30), default="draft", index=True)
    source_module = Column(String(40), default="fam", index=True)
    source_record_type = Column(String(80), nullable=True, index=True)
    source_record_id = Column(String(120), nullable=True, index=True)
    reference_number = Column(String(120), nullable=True, index=True)
    narration = Column(Text, nullable=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FAMStockMovementLine(Base):
    __tablename__ = "fam_stock_movement_lines"

    id = Column(Integer, primary_key=True, index=True)
    movement_id = Column(Integer, ForeignKey("fam_stock_movements.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("fam_stock_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_in = Column(Numeric(14, 3), default=0)
    quantity_out = Column(Numeric(14, 3), default=0)
    rate = Column(Numeric(14, 4), default=0)
    value = Column(Numeric(14, 2), default=0)
    balance_quantity = Column(Numeric(14, 3), default=0)
    balance_value = Column(Numeric(14, 2), default=0)
    line_number = Column(Integer, default=1)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMInventoryValuationLayer(Base):
    __tablename__ = "fam_inventory_valuation_layers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("fam_stock_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="RESTRICT"), nullable=True, index=True)
    movement_id = Column(Integer, ForeignKey("fam_stock_movements.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_line_id = Column(Integer, ForeignKey("fam_stock_movement_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    valuation_method = Column(String(40), default="weighted_average", index=True)
    quantity = Column(Numeric(14, 3), default=0)
    unit_cost = Column(Numeric(14, 4), default=0)
    layer_value = Column(Numeric(14, 2), default=0)
    remaining_quantity = Column(Numeric(14, 3), default=0)
    remaining_value = Column(Numeric(14, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMStockTransfer(Base):
    __tablename__ = "fam_stock_transfers"
    __table_args__ = (UniqueConstraint("company_id", "transfer_number", name="uq_fam_stock_transfer_company_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    transfer_number = Column(String(120), nullable=False, index=True)
    transfer_date = Column(Date, nullable=False, index=True)
    from_warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    to_warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(30), default="draft", index=True)
    notes = Column(Text, nullable=True)
    movement_id = Column(Integer, ForeignKey("fam_stock_movements.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    lines_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMStockAdjustment(Base):
    __tablename__ = "fam_stock_adjustments"
    __table_args__ = (UniqueConstraint("company_id", "adjustment_number", name="uq_fam_stock_adjustment_company_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    adjustment_number = Column(String(120), nullable=False, index=True)
    adjustment_date = Column(Date, nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    adjustment_type = Column(String(40), default="other", index=True)
    reason = Column(String(220), nullable=True)
    status = Column(String(30), default="draft", index=True)
    voucher_id = Column(Integer, ForeignKey("fam_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_id = Column(Integer, ForeignKey("fam_stock_movements.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    lines_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMInventoryAILog(Base):
    __tablename__ = "fam_inventory_ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    context_json = Column(JSON, nullable=True)
    response_json = Column(JSON, nullable=True)
    confidence = Column(Numeric(7, 3), default=0)
    evidence_json = Column(JSON, nullable=True)
    provider = Column(String(80), nullable=True)
    status = Column(String(30), default="not_configured", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMInventoryReport(Base):
    __tablename__ = "fam_inventory_reports"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    report_type = Column(String(80), nullable=False, index=True)
    filters_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMInventoryReservation(Base):
    __tablename__ = "fam_inventory_reservations"
    __table_args__ = (UniqueConstraint("company_id", "source_module", "source_record_type", "source_record_id", "stock_item_id", name="uq_fam_inventory_reservation_source_item"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    reservation_number = Column(String(120), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("fam_stock_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("fam_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity = Column(Numeric(14, 3), nullable=False)
    reserved_quantity = Column(Numeric(14, 3), nullable=False)
    source_module = Column(String(40), nullable=False, index=True)
    source_record_type = Column(String(80), nullable=False, index=True)
    source_record_id = Column(String(120), nullable=False, index=True)
    status = Column(String(30), default="active", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    released_at = Column(DateTime(timezone=True), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMInventoryIntegrationLink(Base):
    __tablename__ = "fam_inventory_integration_links"
    __table_args__ = (UniqueConstraint("company_id", "stock_item_id", "target_module", "target_record_type", "target_record_id", name="uq_fam_inventory_link_target"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("fam_stock_items.id", ondelete="CASCADE"), nullable=False, index=True)
    target_module = Column(String(40), nullable=False, index=True)
    target_record_type = Column(String(80), nullable=False, index=True)
    target_record_id = Column(String(120), nullable=False, index=True)
    link_type = Column(String(60), default="catalog", index=True)
    metadata_json = Column(JSON, nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMInventoryControlSetting(Base):
    __tablename__ = "fam_inventory_control_settings"
    __table_args__ = (UniqueConstraint("company_id", "setting_key", name="uq_fam_inventory_control_setting"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    setting_key = Column(String(120), nullable=False, index=True)
    setting_value_json = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class FAMImportJob(Base):
    __tablename__ = "fam_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    import_type = Column(String(80), nullable=False, index=True)
    file_name = Column(String(220), nullable=False)
    file_content = Column(Text, nullable=True)
    status = Column(String(30), default="uploaded", index=True)
    mapping_json = Column(JSON, nullable=True)
    validation_result_json = Column(JSON, nullable=True)
    error_json = Column(JSON, nullable=True)
    row_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    posted_at = Column(DateTime(timezone=True), nullable=True, index=True)


class FAMExportJob(Base):
    __tablename__ = "fam_export_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    export_type = Column(String(80), nullable=False, index=True)
    export_format = Column(String(20), default="csv", index=True)
    status = Column(String(30), default="ready", index=True)
    file_name = Column(String(220), nullable=True)
    file_content = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True)
    error_json = Column(JSON, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMIntegrityRun(Base):
    __tablename__ = "fam_integrity_runs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    status = Column(String(30), default="completed", index=True)
    result_json = Column(JSON, nullable=True)
    run_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    run_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FAMPeriodCloseRun(Base):
    __tablename__ = "fam_period_close_runs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    financial_year_id = Column(Integer, ForeignKey("fam_financial_years.id", ondelete="SET NULL"), nullable=True, index=True)
    accounting_period_id = Column(Integer, ForeignKey("fam_accounting_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="checked", index=True)
    checklist_json = Column(JSON, nullable=True)
    locked_period_id = Column(Integer, ForeignKey("fam_accounting_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    approval_note = Column(Text, nullable=True)
    run_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    run_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True, index=True)


class FAMAIAccountingLog(Base):
    __tablename__ = "fam_ai_accounting_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    request_type = Column(String(80), nullable=False, index=True)
    prompt = Column(Text, nullable=True)
    context_json = Column(JSON, nullable=True)
    response_json = Column(JSON, nullable=True)
    confidence = Column(Numeric(7, 3), default=0)
    evidence_json = Column(JSON, nullable=True)
    provider = Column(String(80), nullable=True)
    status = Column(String(30), default="not_configured", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
