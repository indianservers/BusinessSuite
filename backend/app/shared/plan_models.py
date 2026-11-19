"""Purchased plan snapshots and append-only usage/lifecycle records."""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Numeric, Date, DateTime, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.sql import func
from app.db.base_class import Base


class CustomerPlan(Base):
    __tablename__ = "catalog_customer_plans"
    __table_args__ = (
        UniqueConstraint("organization_id", "source_key", name="uq_customer_plan_source"),
        CheckConstraint("kind IN ('membership','subscription')", name="ck_customer_plan_kind"),
        CheckConstraint("end_date IS NULL OR end_date > start_date", name="ck_customer_plan_dates"),
        Index("ix_customer_plan_renewal", "organization_id", "status", "end_date"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    offering_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    number = Column(String(80), nullable=False)
    source_key = Column(String(180), nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    configuration = Column(JSON, nullable=False)
    beneficiaries = Column(JSON, nullable=False, default=list)
    price_snapshot = Column(JSON, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CustomerEntitlement(Base):
    __tablename__ = "catalog_customer_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_id", "benefit_key", name="uq_plan_benefit"),
        CheckConstraint("remaining IS NULL OR remaining >= 0", name="ck_entitlement_remaining"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("catalog_customer_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    benefit_key = Column(String(80), nullable=False)
    definition = Column(JSON, nullable=False)
    remaining = Column(Numeric(18, 4))
    revision = Column(Integer, nullable=False, default=1)


class UsageLedger(Base):
    __tablename__ = "catalog_usage_ledger"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_usage_request"),
        UniqueConstraint("reverses_id", name="uq_usage_reversal"),
        CheckConstraint("quantity != 0", name="ck_usage_nonzero"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    entitlement_id = Column(Integer, ForeignKey("catalog_customer_entitlements.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_key = Column(String(180), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    reference = Column(String(180), nullable=False)
    reverses_id = Column(Integer, ForeignKey("catalog_usage_ledger.id", ondelete="RESTRICT"))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PlanLifecycleEvent(Base):
    __tablename__ = "catalog_plan_events"
    __table_args__ = (UniqueConstraint("organization_id", "request_key", name="uq_plan_event_request"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("catalog_customer_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_key = Column(String(180), nullable=False)
    action = Column(String(30), nullable=False)
    before = Column(JSON, nullable=False)
    after = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _immutable_history(mapper, connection, target):
    raise ValueError("Plan audit history is append-only; use a compensating event")


from sqlalchemy import event
for _history_model in (UsageLedger, PlanLifecycleEvent):
    event.listen(_history_model, "before_update", _immutable_history)
    event.listen(_history_model, "before_delete", _immutable_history)


@event.listens_for(CustomerPlan, "before_update")
def _purchase_snapshot_is_immutable(mapper, connection, target):
    from sqlalchemy import inspect
    state = inspect(target)
    if any(state.attrs[name].history.has_changes() for name in (
        "offering_id", "kind", "source_key", "number", "configuration", "price_snapshot", "created_by", "created_at"
    )):
        raise ValueError("Purchased plan configuration and pricing are immutable")
