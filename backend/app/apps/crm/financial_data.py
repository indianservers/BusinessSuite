"""Validated optional financial data under the contact's existing access scope."""
import re
from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .financial_models import ContactFinancialProfile, ContactFinancialTransaction

router = APIRouter()


class BankAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    holderName: str = Field("", max_length=180)
    bankName: str = Field("", max_length=120)
    accountNumber: str = Field(min_length=1, max_length=34, pattern=r"^[A-Za-z0-9]+$")
    ifsc: str = Field("", max_length=11)
    micr: str = Field("", max_length=9)
    branch: str = Field("", max_length=120)
    primary: bool = False
    country: str = Field("IN", pattern=r"^[A-Z]{2}$")
    currency: str = Field("INR", pattern=r"^[A-Z]{3}$")
    iban: str = Field("", max_length=40)
    bic: str = Field("", max_length=11)

    @model_validator(mode="after")
    def validate_codes(self):
        from app.core.business_validation import bank_code
        self.iban = bank_code("IBAN", self.iban, self.country)
        self.bic = bank_code("BIC", self.bic)
        self.ifsc = bank_code("IFSC", self.ifsc, self.country)
        self.ifsc = self.ifsc.upper()
        if self.ifsc and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", self.ifsc):
            raise ValueError("IFSC must contain 11 characters, with zero in position 5")
        if self.micr and not re.fullmatch(r"[0-9]{9}", self.micr):
            raise ValueError("MICR must contain 9 digits")
        return self


class UpiAddress(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    upiId: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+$")
    label: str = Field("", max_length=80)
    mobile: str = Field("", max_length=16, pattern=r"^(\+?[0-9]{10,15})?$")
    primary: bool = False


class FinancialData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    gstNumber: str = Field("", max_length=15)
    bankAccounts: list[BankAccount] = Field(default_factory=list, max_length=20)
    upiIds: list[UpiAddress] = Field(default_factory=list, max_length=20)
    version: int = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_details(self):
        from app.core.business_validation import registration
        self.gstNumber = registration("GSTIN", self.gstNumber, "IN")
        self.gstNumber = self.gstNumber.upper()
        if self.gstNumber and not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", self.gstNumber):
            raise ValueError("Enter a 15-character company GST number")
        for rows, key in [(self.bankAccounts, "accountNumber"), (self.upiIds, "upiId")]:
            if sum(x.primary for x in rows) > 1:
                raise ValueError("Choose one primary bank account and one primary UPI ID")
            values = [(x.ifsc.casefold(), x.bankName.casefold(), x.accountNumber.casefold()) if isinstance(x, BankAccount) else x.upiId.casefold() for x in rows]
            if len(values) != len(set(values)):
                raise ValueError("Remove duplicate bank accounts or UPI IDs")
        return self


def profile_data(row):
    return {"gstNumber": row.gst_number or "", "bankAccounts": row.bank_accounts, "upiIds": row.upi_ids, "version": row.version} if row else FinancialData().model_dump()


def save_profile(db, actor, contact, data):
    row = db.query(ContactFinancialProfile).filter_by(contact_id=contact.id).with_for_update().first()
    if data.version != (row.version if row else 0):
        raise HTTPException(409, "Financial data changed. Reload the contact before saving.")
    if row is None:
        row = ContactFinancialProfile(contact_id=contact.id, organization_id=contact.organization_id, version=0)
        db.add(row)
    row.gst_number = data.gstNumber or None
    row.bank_accounts = [x.model_dump() for x in data.bankAccounts]
    row.upi_ids = [x.model_dump() for x in data.upiIds]
    row.version += 1
    from .contact_directory import audit
    # Audit changes without copying full bank details into general audit logs.
    audit(db, actor, contact, "CONTACT_FINANCIAL_DATA_EDIT", after={"version": row.version, "bankAccounts": len(row.bank_accounts), "upiIds": len(row.upi_ids)})
    return row


@router.get("/{ident}/financial-data")
def get_financial_data(ident: int, response: Response, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    from .contact_directory import get_contact, allowed
    get_contact(db, actor, ident)
    try:
        allowed(actor, "manage")
        manage = True
    except HTTPException:
        manage = False
    grant = (getattr(actor, "_suite_grants", None) or {}).get("crm")
    can_void = manage and (actor.is_superuser or grant is None or "delete" in grant.get("actions", []))
    return {**profile_data(db.get(ContactFinancialProfile, ident)), "canManage": manage, "canVoid": can_void}


@router.put("/{ident}/financial-data")
def put_financial_data(ident: int, data: FinancialData, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .contact_directory import allowed, get_contact
    allowed(actor, "manage")
    contact = get_contact(db, actor, ident, lock=True)
    row = save_profile(db, actor, contact, data)
    db.commit()
    return profile_data(row)


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    requestId: UUID | None = None
    direction: Literal["received", "paid"]
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    currency: str = Field("INR", pattern=r"^[A-Z]{3}$")
    transactionDate: date
    method: Literal["UPI", "Bank transfer", "Cash", "Cheque", "Card", "Other"]
    reference: str = Field("", max_length=120)
    notes: str = Field("", max_length=2000)


def transaction_data(row):
    return {"id": row.id, "version": row.version, "status": row.status, "voidReason": row.void_reason, "direction": row.direction, "amount": str(row.amount), "currency": row.currency, "transactionDate": row.transaction_date, "method": row.method, "reference": row.reference, "notes": row.notes, "createdAt": row.created_at}


@router.get("/{ident}/financial-transactions")
def list_transactions(ident: int, response: Response, page: int = Query(1, ge=1), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    from .contact_directory import get_contact
    contact = get_contact(db, actor, ident)
    q = db.query(ContactFinancialTransaction).filter_by(contact_id=ident, organization_id=contact.organization_id)
    return {"items": [transaction_data(x) for x in q.order_by(ContactFinancialTransaction.transaction_date.desc(), ContactFinancialTransaction.id.desc()).offset((page-1)*30).limit(30)], "total": q.count()}


@router.post("/{ident}/financial-transactions")
def record_transaction(ident: int, data: TransactionInput, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .contact_directory import allowed, get_contact, audit
    allowed(actor, "manage")
    contact = get_contact(db, actor, ident, lock=True)
    if data.requestId:
        previous = db.query(ContactFinancialTransaction).filter_by(organization_id=contact.organization_id, request_id=str(data.requestId)).first()
        if previous:
            if previous.contact_id != ident or any(getattr(previous, key) != value for key, value in {"amount": data.amount, "currency": data.currency, "direction": data.direction, "transaction_date": data.transactionDate, "method": data.method, "reference": data.reference, "notes": data.notes}.items()):
                raise HTTPException(409, "This transaction request was already used. Reload before recording a different payment.")
            return transaction_data(previous)
    row = ContactFinancialTransaction(request_id=str(data.requestId) if data.requestId else None, contact_id=ident, organization_id=contact.organization_id, direction=data.direction, amount=data.amount, currency=data.currency, transaction_date=data.transactionDate, method=data.method, reference=data.reference, notes=data.notes, created_by_user_id=actor.id)
    db.add(row)
    db.flush()
    audit(db, actor, contact, "CONTACT_TRANSACTION_RECORDED", after={"transactionId": row.id, "amount": str(row.amount), "direction": row.direction})
    db.commit()
    return transaction_data(row)


def parse_and_save_profile(db, actor, contact, value):
    try:
        data = FinancialData.model_validate(value)
    except ValueError as exc:
        raise HTTPException(422, "Check GST, bank account, IFSC, MICR and UPI details") from exc
    return save_profile(db, actor, contact, data)


class TransactionEdit(TransactionInput):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


@router.get("/{ident}/financial-transactions/{transaction_id}")
def get_transaction(ident: int, transaction_id: int, response: Response, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .contact_directory import get_contact
    contact = get_contact(db, actor, ident)
    row = db.query(ContactFinancialTransaction).filter_by(contact_id=ident, organization_id=contact.organization_id, id=transaction_id).first()
    if row is None:
        raise HTTPException(404, "Transaction is unavailable in your scope")
    response.headers["Cache-Control"] = "private, no-store"
    return transaction_data(row)


class TransactionVoid(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


def editable_transaction(db, actor, ident, transaction_id, expected):
    from .contact_directory import allowed, get_contact
    allowed(actor, "manage")
    contact = get_contact(db, actor, ident, lock=True)
    row = db.query(ContactFinancialTransaction).filter_by(contact_id=ident, organization_id=contact.organization_id, id=transaction_id).with_for_update().first()
    if row is None:
        raise HTTPException(404, "Transaction is unavailable in your scope")
    if row.version != expected:
        raise HTTPException(409, "Transaction changed. Reload before making another change.")
    if row.status == "void":
        raise HTTPException(409, "A void transaction cannot be changed")
    return contact, row


@router.patch("/{ident}/financial-transactions/{transaction_id}")
def update_transaction(ident: int, transaction_id: int, data: TransactionEdit, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    contact, row = editable_transaction(db, actor, ident, transaction_id, data.version)
    before = transaction_data(row)
    for key, value in {"direction": data.direction, "amount": data.amount, "currency": data.currency, "transaction_date": data.transactionDate, "method": data.method, "reference": data.reference, "notes": data.notes}.items():
        setattr(row, key, value)
    row.version += 1
    from .contact_directory import audit
    audit(db, actor, contact, "CONTACT_TRANSACTION_CORRECTED", before, {**transaction_data(row), "reason": data.reason})
    db.commit()
    return transaction_data(row)


@router.delete("/{ident}/financial-transactions/{transaction_id}")
def void_transaction(ident: int, transaction_id: int, data: TransactionVoid, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    contact, row = editable_transaction(db, actor, ident, transaction_id, data.version)
    before = transaction_data(row)
    row.status, row.void_reason, row.version = "void", data.reason, row.version + 1
    from .contact_directory import audit
    audit(db, actor, contact, "CONTACT_TRANSACTION_VOIDED", before, transaction_data(row))
    db.commit()
    return transaction_data(row)


@router.delete("/{ident}/financial-data")
def clear_financial_data(ident: int, version: int = Query(..., ge=0), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .contact_directory import allowed, get_contact
    allowed(actor, "manage")
    contact = get_contact(db, actor, ident, lock=True)
    row = save_profile(db, actor, contact, FinancialData(version=version))
    db.commit()
    return profile_data(row)
