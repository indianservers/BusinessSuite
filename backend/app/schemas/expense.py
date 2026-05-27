from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExpenseClaimCreate(BaseModel):
    employee_id: Optional[int] = None
    claim_type: str
    expense_date: date
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    description: Optional[str] = None
    receipt_url: Optional[str] = None


class ExpenseClaimReview(BaseModel):
    status: str
    approved_amount: Optional[Decimal] = None
    remarks: Optional[str] = None


class ExpenseReimbursementUpdate(BaseModel):
    reimbursement_reference: Optional[str] = None
    remarks: Optional[str] = None


class ExpenseClaimSchema(ExpenseClaimCreate):
    id: int
    employee_id: int
    claim_number: str
    approved_amount: Decimal = Decimal("0")
    status: str
    manager_approved_by: Optional[int] = None
    manager_approved_at: Optional[datetime] = None
    finance_approved_by: Optional[int] = None
    finance_approved_at: Optional[datetime] = None
    payroll_reimbursement_id: Optional[int] = None
    payroll_run_id: Optional[int] = None
    reimbursed_at: Optional[datetime] = None
    reimbursement_reference: Optional[str] = None
    remarks: Optional[str] = None
    submitted_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
