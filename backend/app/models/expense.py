from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_number = Column(String(50), unique=True, nullable=False, index=True)
    claim_type = Column(String(60), nullable=False, index=True)
    expense_date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    approved_amount = Column(Numeric(12, 2), default=0)
    currency = Column(String(10), default="INR")
    description = Column(Text)
    receipt_url = Column(String(500))
    status = Column(String(30), default="submitted", index=True)
    manager_approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    manager_approved_at = Column(DateTime(timezone=True))
    finance_approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    finance_approved_at = Column(DateTime(timezone=True))
    payroll_reimbursement_id = Column(Integer, ForeignKey("reimbursements.id", ondelete="SET NULL"), nullable=True, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    reimbursed_at = Column(DateTime(timezone=True))
    reimbursement_reference = Column(String(120))
    remarks = Column(Text)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee")
    payroll_reimbursement = relationship("Reimbursement")
