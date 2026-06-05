from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class SRMSalesOrder(Base):
    __tablename__ = "srm_sales_orders"
    __table_args__ = (UniqueConstraint("organization_id", "order_number", name="uq_srm_sales_order_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    order_number = Column(String(80), nullable=False, index=True)
    status = Column(String(40), default="draft", index=True)
    crm_deal_id = Column(Integer, nullable=True, index=True)
    crm_quote_id = Column(Integer, nullable=True, index=True)
    crm_company_id = Column(Integer, nullable=True, index=True)
    crm_contact_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approval_request_id = Column(Integer, nullable=True, index=True)
    title = Column(String(220), nullable=False)
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    expected_start_date = Column(Date, nullable=True)
    expected_end_date = Column(Date, nullable=True)
    terms = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    lines = relationship("SRMSalesOrderLine", back_populates="sales_order", cascade="all, delete-orphan")


class SRMSalesOrderLine(Base):
    __tablename__ = "srm_sales_order_lines"

    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    source_quote_line_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    item_code = Column(String(80), nullable=True, index=True)
    description = Column(Text)
    service_type = Column(String(80), default="service", index=True)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)
    pms_template_key = Column(String(80), nullable=True)
    metadata_json = Column(JSON)

    sales_order = relationship("SRMSalesOrder", back_populates="lines")


class SRMContract(Base):
    __tablename__ = "srm_contracts"
    __table_args__ = (UniqueConstraint("organization_id", "contract_number", name="uq_srm_contract_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    contract_number = Column(String(80), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    title = Column(String(220), nullable=False)
    status = Column(String(40), default="draft", index=True)
    contract_type = Column(String(80), default="services")
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    contract_value = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="INR")
    signed_by_customer_at = Column(DateTime(timezone=True))
    signed_by_company_at = Column(DateTime(timezone=True))
    terms = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class SRMEngagement(Base):
    __tablename__ = "srm_engagements"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_number = Column(String(80), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    contract_id = Column(Integer, ForeignKey("srm_contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    crm_deal_id = Column(Integer, nullable=True, index=True)
    crm_quote_id = Column(Integer, nullable=True, index=True)
    pms_project_id = Column(Integer, nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(220), nullable=False)
    status = Column(String(40), default="created", index=True)
    billing_type = Column(String(40), default="fixed_fee", index=True)
    budget_amount = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="INR")
    planned_start_date = Column(Date)
    planned_end_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class SRMEngagementLink(Base):
    __tablename__ = "srm_engagement_links"
    __table_args__ = (UniqueConstraint("engagement_id", "linked_module", "linked_entity_type", "linked_entity_id", name="uq_srm_engagement_link"),)

    id = Column(Integer, primary_key=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    linked_module = Column(String(80), nullable=False, index=True)
    linked_entity_type = Column(String(80), nullable=False, index=True)
    linked_entity_id = Column(Integer, nullable=False, index=True)
    label = Column(String(180))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SRMBillingPlan(Base):
    __tablename__ = "srm_billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    billing_type = Column(String(40), default="fixed_fee", index=True)
    status = Column(String(40), default="draft", index=True)
    currency = Column(String(10), default="INR")
    total_amount = Column(Numeric(14, 2), default=0)
    recurrence_rule = Column(String(120))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMBillingMilestone(Base):
    __tablename__ = "srm_billing_milestones"

    id = Column(Integer, primary_key=True, index=True)
    billing_plan_id = Column(Integer, ForeignKey("srm_billing_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    status = Column(String(40), default="pending", index=True)
    due_date = Column(Date, nullable=True, index=True)
    amount = Column(Numeric(14, 2), default=0)
    invoice_draft_id = Column(Integer, nullable=True, index=True)
    metadata_json = Column(JSON)


class SRMInvoiceDraft(Base):
    __tablename__ = "srm_invoice_drafts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    billing_plan_id = Column(Integer, ForeignKey("srm_billing_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    source_type = Column(String(60), nullable=False, index=True)
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMInvoice(Base):
    __tablename__ = "srm_invoices"
    __table_args__ = (UniqueConstraint("organization_id", "invoice_number", name="uq_srm_invoice_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    invoice_number = Column(String(80), nullable=False, index=True)
    invoice_draft_id = Column(Integer, ForeignKey("srm_invoice_drafts.id", ondelete="SET NULL"), nullable=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    issue_date = Column(Date, nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True))
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    paid_amount = Column(Numeric(14, 2), default=0)
    balance_amount = Column(Numeric(14, 2), default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    lines = relationship("SRMInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class SRMInvoiceLine(Base):
    __tablename__ = "srm_invoice_lines"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_srm_invoice_line_source"),)

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(60), nullable=True, index=True)
    source_id = Column(Integer, nullable=True, index=True)
    description = Column(Text, nullable=False)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)

    invoice = relationship("SRMInvoice", back_populates="lines")


class SRMInvoiceHistory(Base):
    __tablename__ = "srm_invoice_history"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(40))
    to_status = Column(String(40), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMReceipt(Base):
    __tablename__ = "srm_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "receipt_number", name="uq_srm_receipt_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    receipt_number = Column(String(80), nullable=False, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    receipt_date = Column(Date, nullable=True, index=True)
    payment_method = Column(String(60), default="bank_transfer")
    reference_number = Column(String(120), nullable=True)
    currency = Column(String(10), default="INR")
    amount = Column(Numeric(14, 2), default=0)
    unallocated_amount = Column(Numeric(14, 2), default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMReceiptAllocation(Base):
    __tablename__ = "srm_receipt_allocations"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("srm_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), default=0)
    allocated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    allocated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SRMCollectionReminder(Base):
    __tablename__ = "srm_collection_reminders"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(40), default="queued", index=True)
    reminder_type = Column(String(60), default="email")
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMCustomerAging(Base):
    __tablename__ = "srm_customer_aging"
    __table_args__ = (UniqueConstraint("organization_id", "customer_id", name="uq_srm_customer_aging_org_customer"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    current_amount = Column(Numeric(14, 2), default=0)
    days_1_30 = Column(Numeric(14, 2), default=0)
    days_31_60 = Column(Numeric(14, 2), default=0)
    days_61_90 = Column(Numeric(14, 2), default=0)
    days_90_plus = Column(Numeric(14, 2), default=0)
    total_outstanding = Column(Numeric(14, 2), default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SRMProfitabilitySnapshot(Base):
    __tablename__ = "srm_profitability_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    quoted_amount = Column(Numeric(14, 2), default=0)
    order_amount = Column(Numeric(14, 2), default=0)
    contract_amount = Column(Numeric(14, 2), default=0)
    billing_amount = Column(Numeric(14, 2), default=0)
    invoiced_amount = Column(Numeric(14, 2), default=0)
    collected_amount = Column(Numeric(14, 2), default=0)
    outstanding_amount = Column(Numeric(14, 2), default=0)
    overdue_amount = Column(Numeric(14, 2), default=0)
    cost_amount = Column(Numeric(14, 2), default=0)
    gross_margin_amount = Column(Numeric(14, 2), default=0)
    gross_margin_percent = Column(Numeric(6, 2), default=0)
    cash_margin_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(40), default="healthy", index=True)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMRevenueEvent(Base):
    __tablename__ = "srm_revenue_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    amount = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="INR")
    recognized_on = Column(Date, nullable=True, index=True)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMAuditLog(Base):
    __tablename__ = "srm_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    before_json = Column(JSON)
    after_json = Column(JSON)
    ip_address = Column(String(80))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMSetting(Base):
    __tablename__ = "srm_settings"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_srm_setting_org_key"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    key = Column(String(120), nullable=False, index=True)
    value_json = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
