from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.employee import Employee
from app.models.payroll import (
    EmployeeTaxDeclaration,
    EmployeeTaxDeclarationItem,
    EmployeeTaxProof,
    TaxDeclarationCategory,
)
from app.models.user import User

router = APIRouter(tags=["HRMS Tax Declaration"])


class TaxCategoryPayload(BaseModel):
    financialYear: str
    code: str = Field(..., min_length=1, max_length=50)
    name: str
    section: str
    maxLimit: Decimal = Field(default=Decimal("0"), ge=0)
    requiresProof: bool = True
    isActive: bool = True


class TaxDeclarationItemPayload(BaseModel):
    categoryId: int
    declaredAmount: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None


class TaxDeclarationPayload(BaseModel):
    employeeId: int | None = None
    financialYear: str
    items: list[TaxDeclarationItemPayload] = []


class TaxDeclarationPatch(BaseModel):
    items: list[TaxDeclarationItemPayload] | None = None


class TaxDeclarationReviewItem(BaseModel):
    itemId: int
    status: str
    approvedAmount: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None


class TaxDeclarationReviewPayload(BaseModel):
    items: list[TaxDeclarationReviewItem]


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _org_id(user: User) -> int | None:
    return getattr(user, "organization_id", None) or getattr(user, "company_id", None)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (user.role.permissions if user.role else [])}


def _employee_id_for_user(current_user: User) -> int:
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    return current_user.employee.id


def _can_manage_tax(current_user: User) -> bool:
    return _has_permission(current_user, "payroll_run") or _has_permission(current_user, "payroll_view")


def _load_declaration(db: Session, declaration_id: int) -> EmployeeTaxDeclaration:
    declaration = (
        db.query(EmployeeTaxDeclaration)
        .options(
            joinedload(EmployeeTaxDeclaration.employee),
            joinedload(EmployeeTaxDeclaration.items).joinedload(EmployeeTaxDeclarationItem.category),
            joinedload(EmployeeTaxDeclaration.items).joinedload(EmployeeTaxDeclarationItem.proofs),
        )
        .filter(EmployeeTaxDeclaration.id == declaration_id)
        .first()
    )
    if not declaration:
        raise HTTPException(status_code=404, detail="Tax declaration not found")
    return declaration


def _enforce_declaration_access(declaration: EmployeeTaxDeclaration, current_user: User) -> None:
    if _can_manage_tax(current_user):
        return
    if declaration.employee_id != _employee_id_for_user(current_user):
        raise HTTPException(status_code=403, detail="Employees can access only their own declaration")


def _serialize_category(category: TaxDeclarationCategory) -> dict[str, Any]:
    return {
        "id": category.id,
        "organizationId": category.organization_id,
        "financialYear": category.financial_year,
        "code": category.code,
        "name": category.name,
        "section": category.section,
        "maxLimit": float(_money(category.max_limit)),
        "requiresProof": bool(category.requires_proof),
        "isActive": bool(category.is_active),
    }


def _serialize_declaration(declaration: EmployeeTaxDeclaration) -> dict[str, Any]:
    employee = declaration.employee
    return {
        "id": declaration.id,
        "organizationId": declaration.organization_id,
        "employeeId": declaration.employee_id,
        "employeeName": " ".join(part for part in [employee.first_name if employee else "", employee.last_name if employee else ""] if part).strip(),
        "employeeCode": employee.employee_id if employee else None,
        "financialYear": declaration.financial_year,
        "status": declaration.status,
        "submittedAt": declaration.submitted_at,
        "reviewedBy": declaration.reviewed_by,
        "reviewedAt": declaration.reviewed_at,
        "declaredTotal": float(sum(_money(item.declared_amount) for item in declaration.items)),
        "approvedTotal": float(sum(_money(item.approved_amount) for item in declaration.items)),
        "items": [
            {
                "id": item.id,
                "categoryId": item.category_id,
                "categoryCode": item.category.code if item.category else None,
                "categoryName": item.category.name if item.category else None,
                "section": item.category.section if item.category else None,
                "maxLimit": float(_money(item.category.max_limit)) if item.category else 0,
                "requiresProof": bool(item.category.requires_proof) if item.category else False,
                "declaredAmount": float(_money(item.declared_amount)),
                "approvedAmount": float(_money(item.approved_amount)),
                "remarks": item.remarks,
                "status": item.status,
                "proofs": [
                    {
                        "id": proof.id,
                        "fileName": proof.file_name,
                        "filePath": proof.file_path,
                        "fileType": proof.file_type,
                        "uploadedAt": proof.uploaded_at,
                    }
                    for proof in item.proofs
                ],
            }
            for item in declaration.items
        ],
    }


def _form12bb_section(code: str | None, section: str | None) -> str:
    key = (code or section or "").upper()
    if key == "HRA":
        return "House Rent Allowance"
    if key in {"80C", "80D", "NPS", "HOME_LOAN_INTEREST"} or "80" in key or "24" in key:
        return "Deductions under Chapter VI-A"
    if "LTA" in key:
        return "Leave Travel Allowance"
    return "Other declarations"


def _seed_default_categories(db: Session, financial_year: str, organization_id: int | None = None) -> None:
    existing_count = (
        db.query(func.count(TaxDeclarationCategory.id))
        .filter(TaxDeclarationCategory.financial_year == financial_year, TaxDeclarationCategory.organization_id == organization_id)
        .scalar()
    )
    if existing_count:
        return
    defaults = [
        ("80C", "Section 80C", "80C", Decimal("150000"), True),
        ("80D", "Medical Insurance", "80D", Decimal("100000"), True),
        ("HRA", "HRA Exemption", "HRA", Decimal("0"), True),
        ("HOME_LOAN_INTEREST", "Home Loan Interest", "Section 24", Decimal("200000"), True),
        ("EDUCATION_LOAN", "Education Loan Interest", "80E", Decimal("0"), True),
        ("NPS", "National Pension System", "80CCD(1B)", Decimal("50000"), True),
        ("LTA", "Leave Travel Allowance", "LTA", Decimal("0"), True),
    ]
    for code, name, section, limit, requires_proof in defaults:
        db.add(
            TaxDeclarationCategory(
                organization_id=organization_id,
                financial_year=financial_year,
                code=code,
                name=name,
                section=section,
                max_limit=limit,
                requires_proof=requires_proof,
                is_active=True,
            )
        )
    db.flush()


@router.get("/hrms/tax-declaration/categories")
def list_tax_declaration_categories(
    financialYear: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _org_id(current_user)
    _seed_default_categories(db, financialYear, org_id)
    db.commit()
    categories = (
        db.query(TaxDeclarationCategory)
        .filter(TaxDeclarationCategory.financial_year == financialYear, TaxDeclarationCategory.organization_id == org_id)
        .order_by(TaxDeclarationCategory.section, TaxDeclarationCategory.name)
        .all()
    )
    return [_serialize_category(category) for category in categories]


@router.post("/hrms/tax-declaration/categories", dependencies=[Depends(RequirePermission("payroll_run"))])
def create_tax_declaration_category(
    payload: TaxCategoryPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = TaxDeclarationCategory(
        organization_id=_org_id(current_user),
        financial_year=payload.financialYear,
        code=payload.code.strip().upper(),
        name=payload.name,
        section=payload.section,
        max_limit=payload.maxLimit,
        requires_proof=payload.requiresProof,
        is_active=payload.isActive,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _serialize_category(category)


@router.get("/hrms/employees/{employee_id}/tax-declarations")
def get_employee_tax_declarations(
    employee_id: int,
    financialYear: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_tax(current_user) and employee_id != _employee_id_for_user(current_user):
        raise HTTPException(status_code=403, detail="Employees can access only their own declaration")
    declarations = (
        db.query(EmployeeTaxDeclaration)
        .options(
            joinedload(EmployeeTaxDeclaration.employee),
            joinedload(EmployeeTaxDeclaration.items).joinedload(EmployeeTaxDeclarationItem.category),
            joinedload(EmployeeTaxDeclaration.items).joinedload(EmployeeTaxDeclarationItem.proofs),
        )
        .filter(EmployeeTaxDeclaration.employee_id == employee_id, EmployeeTaxDeclaration.financial_year == financialYear)
        .order_by(EmployeeTaxDeclaration.id.desc())
        .all()
    )
    return [_serialize_declaration(item) for item in declarations]


@router.get("/hrms/tax-declarations", dependencies=[Depends(RequirePermission("payroll_view", "payroll_run"))])
def list_tax_declarations_for_review(
    financialYear: str | None = Query(default=None),
    status: str | None = Query(default=None),
    employeeId: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EmployeeTaxDeclaration).options(
        joinedload(EmployeeTaxDeclaration.employee),
        joinedload(EmployeeTaxDeclaration.items).joinedload(EmployeeTaxDeclarationItem.category),
        joinedload(EmployeeTaxDeclaration.items).joinedload(EmployeeTaxDeclarationItem.proofs),
    )
    if financialYear:
        query = query.filter(EmployeeTaxDeclaration.financial_year == financialYear)
    org_id = _org_id(current_user)
    if org_id is not None:
        query = query.filter(EmployeeTaxDeclaration.organization_id == org_id)
    if status:
        query = query.filter(EmployeeTaxDeclaration.status == status)
    if employeeId:
        query = query.filter(EmployeeTaxDeclaration.employee_id == employeeId)
    return [_serialize_declaration(item) for item in query.order_by(EmployeeTaxDeclaration.id.desc()).all()]


@router.post("/hrms/tax-declarations")
def create_tax_declaration(
    payload: TaxDeclarationPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = payload.employeeId or _employee_id_for_user(current_user)
    current_employee_id = current_user.employee.id if current_user.employee else None
    if employee_id != current_employee_id and not _can_manage_tax(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to create declaration for another employee")
    if not db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first():
        raise HTTPException(status_code=404, detail="Employee not found")
    _seed_default_categories(db, payload.financialYear, _org_id(current_user))
    declaration = EmployeeTaxDeclaration(
        organization_id=_org_id(current_user),
        employee_id=employee_id,
        financial_year=payload.financialYear,
        status="draft",
    )
    db.add(declaration)
    db.flush()
    for item in payload.items:
        category = db.query(TaxDeclarationCategory).filter(TaxDeclarationCategory.id == item.categoryId).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Tax category {item.categoryId} not found")
        amount = min(_money(item.declaredAmount), _money(category.max_limit)) if category.max_limit else _money(item.declaredAmount)
        declaration.items.append(
            EmployeeTaxDeclarationItem(
                category_id=item.categoryId,
                declared_amount=amount,
                approved_amount=Decimal("0"),
                remarks=item.remarks,
                status="draft",
            )
        )
    db.commit()
    db.refresh(declaration)
    return _serialize_declaration(_load_declaration(db, declaration.id))


@router.get("/hrms/tax-declarations/{declaration_id}/form12bb")
def get_form12bb(
    declaration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    declaration = _load_declaration(db, declaration_id)
    _enforce_declaration_access(declaration, current_user)
    employee = declaration.employee
    sections: dict[str, list[dict[str, Any]]] = {}
    for item in declaration.items:
        category = item.category
        section = _form12bb_section(category.code if category else None, category.section if category else None)
        sections.setdefault(section, []).append({
            "particular": category.name if category else "Declaration",
            "section": category.section if category else None,
            "declared_amount": float(_money(item.declared_amount)),
            "approved_amount": float(_money(item.approved_amount)),
            "proof_count": len(item.proofs),
            "status": item.status,
        })
    return {
        "form": "12BB",
        "financial_year": declaration.financial_year,
        "employee": {
            "id": employee.id if employee else declaration.employee_id,
            "employee_code": employee.employee_id if employee else None,
            "name": " ".join(part for part in [employee.first_name if employee else "", employee.last_name if employee else ""] if part).strip(),
            "pan": employee.pan_number if employee else None,
        },
        "status": declaration.status,
        "sections": [{"name": name, "items": items, "total": sum(item["declared_amount"] for item in items)} for name, items in sections.items()],
        "declared_total": float(sum(_money(item.declared_amount) for item in declaration.items)),
        "approved_total": float(sum(_money(item.approved_amount) for item in declaration.items)),
    }


@router.patch("/hrms/tax-declarations/{declaration_id}")
def update_tax_declaration(
    declaration_id: int,
    payload: TaxDeclarationPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    declaration = _load_declaration(db, declaration_id)
    _enforce_declaration_access(declaration, current_user)
    if declaration.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected declarations can be edited")
    if payload.items is not None:
        declaration.items.clear()
        db.flush()
        for item in payload.items:
            category = db.query(TaxDeclarationCategory).filter(TaxDeclarationCategory.id == item.categoryId).first()
            if not category:
                raise HTTPException(status_code=404, detail=f"Tax category {item.categoryId} not found")
            amount = min(_money(item.declaredAmount), _money(category.max_limit)) if category.max_limit else _money(item.declaredAmount)
            declaration.items.append(
                EmployeeTaxDeclarationItem(
                    category_id=item.categoryId,
                    declared_amount=amount,
                    approved_amount=Decimal("0"),
                    remarks=item.remarks,
                    status="draft",
                )
            )
    db.commit()
    return _serialize_declaration(_load_declaration(db, declaration_id))


@router.post("/hrms/tax-declarations/{declaration_id}/submit")
def submit_tax_declaration(
    declaration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    declaration = _load_declaration(db, declaration_id)
    _enforce_declaration_access(declaration, current_user)
    if not declaration.items:
        raise HTTPException(status_code=400, detail="Add at least one declaration item before submission")
    declaration.status = "submitted"
    declaration.submitted_at = datetime.now(timezone.utc)
    for item in declaration.items:
        item.status = "submitted"
    db.commit()
    return _serialize_declaration(_load_declaration(db, declaration_id))


@router.post("/hrms/tax-declarations/{declaration_id}/review", dependencies=[Depends(RequirePermission("payroll_run"))])
def review_tax_declaration(
    declaration_id: int,
    payload: TaxDeclarationReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    declaration = _load_declaration(db, declaration_id)
    item_by_id = {item.id: item for item in declaration.items}
    for review in payload.items:
        item = item_by_id.get(review.itemId)
        if not item:
            raise HTTPException(status_code=404, detail=f"Declaration item {review.itemId} not found")
        if review.status not in {"approved", "rejected"}:
            raise HTTPException(status_code=400, detail="Item status must be approved or rejected")
        limit = _money(item.category.max_limit) if item.category else Decimal("0")
        item.approved_amount = min(_money(review.approvedAmount), limit) if limit else _money(review.approvedAmount)
        if review.status == "rejected":
            item.approved_amount = Decimal("0")
        item.status = review.status
        item.remarks = review.remarks
    statuses = {item.status for item in declaration.items}
    if statuses == {"approved"}:
        declaration.status = "approved"
    elif statuses == {"rejected"}:
        declaration.status = "rejected"
    else:
        declaration.status = "partially_approved"
    declaration.reviewed_by = current_user.id
    declaration.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize_declaration(_load_declaration(db, declaration_id))


@router.post("/hrms/tax-declarations/{declaration_id}/upload-proof")
async def upload_tax_proof(
    declaration_id: int,
    declarationItemId: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    declaration = _load_declaration(db, declaration_id)
    _enforce_declaration_access(declaration, current_user)
    item = next((entry for entry in declaration.items if entry.id == declarationItemId), None)
    if not item:
        raise HTTPException(status_code=404, detail="Declaration item not found")
    original_name = file.filename or "proof"
    extension = os.path.splitext(original_name)[1].lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    if extension not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF and image proofs are allowed")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Proof file must be 5 MB or smaller")
    upload_dir = os.path.join(settings.UPLOAD_DIR, "tax_proofs", str(declaration.employee_id), declaration.financial_year)
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    disk_path = os.path.join(upload_dir, stored_name)
    with open(disk_path, "wb") as handle:
        handle.write(content)
    proof = EmployeeTaxProof(
        declaration_item_id=item.id,
        file_name=original_name,
        file_path=f"/uploads/tax_proofs/{declaration.employee_id}/{declaration.financial_year}/{stored_name}",
        file_type=file.content_type,
    )
    item.status = "submitted"
    db.add(proof)
    db.commit()
    return _serialize_declaration(_load_declaration(db, declaration_id))


@router.get("/hrms/tax-proofs/{proof_id}/download")
def download_tax_proof(
    proof_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proof = db.query(EmployeeTaxProof).filter(EmployeeTaxProof.id == proof_id).first()
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    declaration = proof.declaration_item.declaration
    _enforce_declaration_access(declaration, current_user)
    file_path = os.path.join(settings.UPLOAD_DIR, proof.file_path.replace("/uploads/", "").replace("/", os.sep))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Proof file missing from storage")
    return FileResponse(file_path, media_type=proof.file_type or "application/octet-stream", filename=proof.file_name)
