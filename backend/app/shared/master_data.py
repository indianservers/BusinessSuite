"""Scoped master data over CRMContact/CRMCompany and protected HR identities."""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.core.input_validation import calling_code, email_address, national_phone
from app.models.user import User
from app.models.audit import AuditLog
from app.apps.crm.models import CRMCompany, CRMContact, CRMLead
from app.shared.master_data_models import ContactChannel, BusinessRelationship, CompanyMasterDetails, CompanyContactLink, ContactBirthday, GreetingReservation

router = APIRouter(prefix="/master-data", tags=["Shared contacts and companies"])
Source = Literal["crm", "srm", "project_management", "hrms"]
ROLES = {"Lead", "Prospect", "Customer", "Vendor", "Supplier", "Partner", "Friend", "Consultant", "Dealer", "Distributor", "Investor", "Other"}


def crm():
    from app.apps.crm.api import router as module
    return module


def authorize(actor, source, write=False, entity="companies", action=None):
    from app.access.catalog import permission_names
    names = permission_names(actor)
    read = {"crm": {"crm_view", "crm_manage", "crm_admin", f"crm_{entity}_view", f"crm_{entity}_manage"}, "srm": {"srm_view", "srm_manage", "srm_admin", "srm_invoice_view", "srm_invoice_create"}, "project_management": {"pms_view", "pms_manage_projects", "pms_admin"}, "hrms": {"employee_view", "employee_update", "employee_create"}}
    edit = {"crm": {"crm_manage", "crm_admin", f"crm_{entity}_manage"}, "srm": {"srm_manage", "srm_admin"}, "project_management": {"pms_manage_projects", "pms_admin"}, "hrms": {"employee_update", "employee_create"}}
    if not actor.is_superuser and not names.intersection((edit if write else read)[source]):
        raise HTTPException(403, "This module does not grant access to the requested master data")
    grants = getattr(actor, "_suite_grants", None)
    if grants is not None and not actor.is_superuser:
        grant = grants.get(source, {})
        if not grant.get("enabled") or (action or ("edit" if write else "view")) not in grant.get("actions", []):
            raise HTTPException(403, "The effective module policy denies this action")


def companies(db, actor, source="crm", deleted=False):
    authorize(actor, source)
    q = db.query(CRMCompany).filter(CRMCompany.organization_id == actor.organization_id, CRMCompany.deleted_at.is_not(None) if deleted else CRMCompany.deleted_at.is_(None))
    if source == "crm":
        q = crm()._apply_record_visibility(q, crm()._get_resource("companies"), actor, db)
    elif source == "srm":
        from app.apps.srm.access import can_view_all_srm, sales_order_query
        from app.apps.srm.models import SRMSalesOrder
        if not can_view_all_srm(actor):
            q = q.filter(or_(CRMCompany.created_by_user_id == actor.id, CRMCompany.id.in_(sales_order_query(db, actor).with_entities(SRMSalesOrder.customer_id))))
    elif source == "project_management":
        from app.apps.project_management.access import accessible_project_query, user_permission_names, PMS_GLOBAL_MANAGE_PROJECTS
        from app.apps.project_management.models import PMSProject
        from app.apps.srm.commercial_models import ProjectCommercial
        if not actor.is_superuser and not user_permission_names(actor).intersection(PMS_GLOBAL_MANAGE_PROJECTS):
            q = q.filter(or_(CRMCompany.created_by_user_id == actor.id, CRMCompany.id.in_(select(ProjectCommercial.customer_id).where(ProjectCommercial.project_id.in_(accessible_project_query(db, actor).with_entities(PMSProject.id))))))
    else:
        # Employment/legal employer selectors use app.models.company.Company;
        # business company association requires independent CRM authorization.
        crm()._assert_entity_permission("companies", actor, "view")
        q = crm()._apply_record_visibility(q, crm()._get_resource("companies"), actor, db)
    return q


def owner(db, actor, kind, ident, source="crm", write=False):
    authorize(actor, source, write, "contacts" if kind == "contact" else "companies")
    if kind == "company":
        row = companies(db, actor, source).filter(CRMCompany.id == ident).with_for_update().first() if write else companies(db, actor, source).filter(CRMCompany.id == ident).first()
    elif kind == "contact":
        if source == "hrms":
            crm()._assert_entity_permission("contacts", actor, "manage" if write else "view")
        q = db.query(CRMContact).filter(CRMContact.organization_id == actor.organization_id, CRMContact.deleted_at.is_(None), CRMContact.id == ident)
        if source == "crm":
            q = crm()._apply_record_visibility(q, crm()._get_resource("contacts"), actor, db)
        else:
            q = q.filter(or_(CRMContact.created_by_user_id == actor.id, CRMContact.company_id.in_(companies(db, actor, source).with_entities(CRMCompany.id))))
        row = (q.with_for_update() if write else q).first()
    elif kind == "person":
        # Never expose CommonProfile, employee or credential data through CRM.
        if source != "hrms":
            raise HTTPException(403, "HR identity access is required")
        from app.common.models import CommonPerson
        from app.common.services.profiles import authorized_user
        person = db.query(CommonPerson).filter(CommonPerson.id == ident, CommonPerson.organization_id == actor.organization_id).first()
        if not person or not person.user_id:
            raise HTTPException(404, "Identity unavailable")
        authorized_user(db, actor, person.user_id, write=write)
        row = person
    else:
        raise HTTPException(422, "Choose a supported master record")
    if not row:
        raise HTTPException(404, "Record is unavailable in your scope")
    return row


def owner_filter(model, kind, ident):
    return getattr(model, {"contact": "contact_id", "company": "account_id", "person": "person_id", "employee": "employee_id"}[kind]) == ident


def audit(db, actor, action, kind, ident, values):
    db.add(AuditLog(organization_id=actor.organization_id, user_id=actor.id, method="POST", endpoint="/master-data", entity_type=kind, entity_id=ident, action=action, new_values=json.dumps(values, default=str), status_code=200))


def lock_matches(db, actor, keys):
    # Every capture path uses the same transaction lock. Numbers are deliberately
    # NOT unique: a second concurrent request sees a warning and may confirm sharing.
    if db.bind.dialect.name == "postgresql":
        for key in sorted(set(keys)):
            token = int.from_bytes(hashlib.sha256(f"contacts:{actor.organization_id}:{key}".encode()).digest()[:8], "big") & ((1 << 63) - 1)
            db.connection().execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": token})


def normalized_phone(value, code):
    calling_code(code)
    value = value.strip()
    if value.startswith("+"):
        if not value.startswith(code):
            raise ValueError("The phone number does not match the selected country code")
        value = value[len(code):]
    if re.search(r"[^0-9 ()-]", value):
        raise ValueError("Enter a valid phone number")
    number = re.sub(r"[ ()-]", "", value)
    national_phone(number)
    return number, code + number


class ChannelInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["phone", "email"]
    label: str = Field("Work", min_length=1, max_length=50)
    value: str = Field(min_length=1, max_length=254)
    countryCode: str | None = Field(None, max_length=5)
    primary: bool = False
    whatsapp: bool = False
    notes: str | None = Field(None, max_length=500)


def channel_values(item):
    try:
        if item.kind == "phone":
            value, normalized = normalized_phone(item.value, item.countryCode)
        else:
            value = email_address(item.value)
            normalized = value.casefold()
        return dict(kind=item.kind, label=item.label, value=value, normalized_value=normalized, country_code=item.countryCode if item.kind == "phone" else None, is_primary=item.primary, whatsapp=item.whatsapp if item.kind == "phone" else False, notes=item.notes)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


def channel_output(row):
    return {"id": row.id, "kind": row.kind, "label": row.label, "value": row.value, "countryCode": row.country_code, "primary": row.is_primary, "whatsapp": row.whatsapp, "verificationStatus": row.verification_status, "notes": row.notes}


def version(row):
    return (getattr(row, "updated_at", None) or getattr(row, "created_at", None)).isoformat() if getattr(row, "updated_at", None) or getattr(row, "created_at", None) else "0"


def effective_channels(db, row, kind):
    rows = [channel_output(x) for x in db.query(ContactChannel).filter(owner_filter(ContactChannel, kind, row.id)).order_by(ContactChannel.id)]
    for channel_kind, field in [("phone", "phone_number" if kind == "person" else "phone"), ("email", "primary_email" if kind == "person" else "email")]:
        value = getattr(row, field, None)
        if value and not any(x["kind"] == channel_kind for x in rows):
            rows.append({"kind": channel_kind, "label": "Primary", "value": value, "countryCode": getattr(row, field + "_country_code", None), "primary": True, "whatsapp": False, "verificationStatus": "unverified"})
    return rows


@router.get("/{kind}/{ident}/channels")
def get_channels(kind: Literal["contact", "company", "person"], ident: int, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = owner(db, actor, kind, ident, source)
    return {"items": effective_channels(db, row, kind), "version": version(row)}


class ChannelsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ChannelInput] = Field(max_length=100)
    version: str
    confirmShared: bool = False
    sharedReason: str | None = Field(None, max_length=250)


def permitted_matches(db, actor, source, phone=None, country_code=None, email=None, exclude_kind=None, exclude_id=None):
    matches = []
    normalized = None
    if phone:
        try:
            _, normalized = normalized_phone(phone, country_code)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    for kind, model, entity in [("contact", CRMContact, "contacts"), ("company", CRMCompany, "companies")]:
        try:
            if kind == "company":
                q = companies(db, actor, source)
            else:
                authorize(actor, source, entity="contacts")
                q = db.query(model).filter(model.organization_id == actor.organization_id, model.deleted_at.is_(None))
                if source == "crm":
                    q = crm()._apply_record_visibility(q, crm()._get_resource(entity), actor, db)
                else:
                    q = q.filter(or_(model.created_by_user_id == actor.id, model.company_id.in_(companies(db, actor, source).with_entities(CRMCompany.id))))
        except HTTPException as exc:
            if exc.status_code == 403:
                continue
            raise
        clauses = []
        if normalized:
            number, _ = normalized_phone(phone, country_code)
            primary = model.phone
            for char in [" ", "-", "(", ")"]:
                primary = func.replace(primary, char, "")
            channel_ids = select(getattr(ContactChannel, "contact_id" if kind == "contact" else "account_id")).where(ContactChannel.organization_id == actor.organization_id, ContactChannel.kind == "phone", ContactChannel.normalized_value == normalized)
            clauses.append(or_(and_(primary == number, model.phone_country_code == country_code), model.id.in_(channel_ids)))
        if email:
            clean_email = email.strip().casefold()
            channel_ids = select(getattr(ContactChannel, "contact_id" if kind == "contact" else "account_id")).where(ContactChannel.organization_id == actor.organization_id, ContactChannel.kind == "email", ContactChannel.normalized_value == clean_email)
            clauses.append(or_(func.lower(func.trim(model.email)) == clean_email, model.id.in_(channel_ids)))
        if not clauses:
            continue
        q = q.filter(or_(*clauses))
        if kind == exclude_kind:
            q = q.filter(model.id != exclude_id)
        from app.apps.crm.contact_identity import ContactIdentityLink
        if kind == "contact" and exclude_kind == "company":
            q = q.filter(~model.id.in_(select(ContactIdentityLink.contact_id).where(ContactIdentityLink.account_id == exclude_id)))
        if kind == "company" and exclude_kind == "contact":
            q = q.filter(~model.id.in_(select(ContactIdentityLink.account_id).where(ContactIdentityLink.contact_id == exclude_id, ContactIdentityLink.account_id.is_not(None))))
        for row in q.limit(20):
            matches.append({"id": row.id, "kind": kind, "name": row.full_name if kind == "contact" else row.name, "phone": row.phone, "email": row.email, "url": f"/crm/{entity}/{row.id}"})
    return matches


def duplicate_guard(db, actor, source, phone=None, country_code=None, email=None, confirmed=False, reason=None, exclude_kind=None, exclude_id=None):
    keys = []
    if phone:
        try:
            keys.append(normalized_phone(phone, country_code)[1])
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    if email:
        keys.append(email.strip().casefold())
    lock_matches(db, actor, keys)
    matches = permitted_matches(db, actor, source, phone, country_code, email, exclude_kind, exclude_id)
    if matches and not confirmed:
        raise HTTPException(409, {"code": "duplicate_contact", "message": "This mobile number is already associated with another contact." if phone else "This email is already associated with another contact.", "matches": matches, "canCreateSeparate": True})
    if matches:
        audit(db, actor, "SHARED_CONTACT_CONFIRMED", exclude_kind or "contact", exclude_id, {"reason": reason or "Explicit shared-contact confirmation", "matches": [{"kind": x["kind"], "id": x["id"]} for x in matches]})
    return matches


@router.get("/duplicates/check")
def check_duplicates(source: Source = "crm", phone: str | None = None, country_code: str | None = None, email: str | None = None, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    try:
        authorize(actor, source, entity="contacts")
    except HTTPException:
        authorize(actor, source, entity="companies")
    return {"items": permitted_matches(db, actor, source, phone, country_code, email)}


@router.put("/{kind}/{ident}/channels")
def update_channels(kind: Literal["contact", "company", "person"], ident: int, data: ChannelsUpdate, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = owner(db, actor, kind, ident, source, True)
    if version(row) != data.version:
        raise HTTPException(409, "Contact changed. Reload communication details before saving")
    # Session autoflush is disabled in the application. A legacy source flush
    # can have queued a compatibility channel that must participate in this edit.
    db.flush()
    values = [channel_values(x) for x in data.items]
    lock_matches(db, actor, [x["normalized_value"] for x in values])
    if len({(x["kind"], x["normalized_value"]) for x in values}) != len(values):
        raise HTTPException(422, "Remove repeated entries from this contact")
    for channel_kind in ["phone", "email"]:
        subset = [x for x in values if x["kind"] == channel_kind]
        if sum(x["is_primary"] for x in subset) > 1:
            raise HTTPException(422, "Choose only one primary entry of each kind")
        if subset and not any(x["is_primary"] for x in subset):
            subset[0]["is_primary"] = True
    existing = db.query(ContactChannel).filter(owner_filter(ContactChannel, kind, ident)).all()
    # Explicit channel writes already maintain primary flags atomically. The
    # legacy projection listener must not create a second primary mid-flush.
    db.info.setdefault("master_channels_managed", set()).add(row)
    previous = {(x.kind, x.normalized_value): x for x in existing}
    if kind != "person":
        for value in values:
            if (value["kind"], value["normalized_value"]) not in previous:
                duplicate_guard(db, actor, source, value["value"] if value["kind"] == "phone" else None, value["country_code"], value["value"] if value["kind"] == "email" else None, data.confirmShared, data.sharedReason, kind, ident)
    retained = set()
    for value in values:
        saved = previous.get((value["kind"], value["normalized_value"]))
        if not saved:
            saved = ContactChannel(organization_id=actor.organization_id, **{{"contact": "contact_id", "company": "account_id", "person": "person_id"}[kind]: ident})
            db.add(saved)
        else:
            retained.add(saved.id)
        for key, content in value.items():
            setattr(saved, key, content)
    for saved in existing:
        if saved.id not in retained:
            db.delete(saved)
    for channel_kind, field in [("email", "primary_email" if kind == "person" else "email"), ("phone", "phone_number" if kind == "person" else "phone")]:
        primary = next((x for x in values if x["kind"] == channel_kind and x["is_primary"]), None)
        if kind == "person" and channel_kind == "email":
            # CommonPerson.primary_email is a unique login identity. Personal
            # communication addresses may be shared and never change credentials.
            continue
        setattr(row, field, primary["value"] if primary else None)
        if channel_kind == "phone":
            setattr(row, field + "_country_code", primary["country_code"] if primary else None)
    row.updated_at = datetime.now(timezone.utc)
    audit(db, actor, "CONTACT_CHANNELS_UPDATED", kind, ident, {"count": len(values)})
    if db.info.get("defer_master_commit"):
        db.flush()
    else:
        db.commit()
    return {"items": effective_channels(db, row, kind), "version": version(row)}


def relationships(db, row, kind):
    roles = {x.role for x in db.query(BusinessRelationship).filter(owner_filter(BusinessRelationship, kind, row.id))}
    roles |= {x.strip() for x in (row.tags_text or "").split(",") if x.strip() in ROLES}
    legacy = row.account_type if kind == "company" else row.lifecycle_stage
    if legacy in ROLES:
        roles.add(legacy)
    return sorted(roles)


def company_output(db, row):
    details = db.get(CompanyMasterDetails, row.id)
    return {"id": row.id, "name": row.name, "email": row.email, "phone": row.phone, "phone_country_code": row.phone_country_code, "website": row.website, "industry": row.industry, "status": row.status,
        "roles": relationships(db, row, "company"), "tags": [x.strip() for x in (row.tags_text or "").split(",") if x.strip() and x.strip() not in ROLES], "notes": row.notes,
        "entityKind": "Individual" if details and details.business_type == "Individual" else "Company",
        "legalName": details.legal_name if details else None, "tradeName": details.trade_name if details else None, "businessType": details.business_type if details else None,
        "addresses": details.addresses if details else [], "taxRegistrations": details.tax_registrations if details else [], "primaryContactId": details.primary_contact_id if details else None, "version": version(row)}


def filter_entity_kind(q, entity_kind):
    individuals = select(CompanyMasterDetails.account_id).where(CompanyMasterDetails.business_type == "Individual")
    if entity_kind == "companies":
        return q.filter(~CRMCompany.id.in_(individuals))
    if entity_kind == "individuals":
        return q.filter(CRMCompany.id.in_(individuals))
    return q


@router.get("/companies")
def list_companies(source: Source = "crm", search: str = Query("", max_length=180), role: str = Query("", max_length=30), page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), actor: User = Depends(get_current_user), entity_kind: Literal["all", "companies", "individuals"] = "all"):
    q = filter_entity_kind(companies(db, actor, source), entity_kind)
    if search:
        clean = search.replace("%", "\\%").replace("_", "\\_")
        q = q.filter(or_(CRMCompany.name.ilike(f"%{clean}%", escape="\\"), CRMCompany.email.ilike(f"%{clean}%", escape="\\"), CRMCompany.phone.contains(clean)))
    if role:
        roles = role.split(",")
        if set(roles) - ROLES:
            raise HTTPException(422, "Choose business relationship roles")
        linked = select(BusinessRelationship.account_id).where(BusinessRelationship.role.in_(roles))
        q = q.filter(or_(CRMCompany.account_type.in_(roles), CRMCompany.id.in_(linked)))
    total = q.count()
    rows = q.order_by(CRMCompany.name, CRMCompany.id).offset((page - 1) * per_page).limit(per_page).all()
    try:
        authorize(actor, source, True, action="create")
        can_create = True
    except HTTPException:
        can_create = False
    return {"items": [company_output(db, x) for x in rows], "total": total, "page": page, "canCreate": can_create}


@router.get("/contacts")
def list_contacts(source: Source = "crm", search: str = Query("", max_length=180), page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    authorize(actor, source, entity="contacts")
    if source == "hrms":
        crm()._assert_entity_permission("contacts", actor, "view")
    q = db.query(CRMContact).filter(CRMContact.organization_id == actor.organization_id, CRMContact.deleted_at.is_(None))
    if source == "crm":
        q = crm()._apply_record_visibility(q, crm()._get_resource("contacts"), actor, db)
    else:
        q = q.filter(or_(CRMContact.created_by_user_id == actor.id, CRMContact.company_id.in_(companies(db, actor, source).with_entities(CRMCompany.id))))
    if search:
        clean = search.replace("%", "\\%").replace("_", "\\_")
        q = q.filter(or_(CRMContact.full_name.ilike(f"%{clean}%", escape="\\"), CRMContact.email.ilike(f"%{clean}%", escape="\\"), CRMContact.phone.ilike(f"%{clean}%", escape="\\")))
    total = q.count()
    return {"items": [{"id": x.id, "name": x.full_name, "email": x.email, "phone": x.phone, "companyId": x.company_id} for x in q.order_by(CRMContact.full_name, CRMContact.id).offset((page - 1) * per_page).limit(per_page)], "total": total}


class PrimaryContact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=180)
    email: str | None = Field(None, max_length=150)
    phone: str | None = None
    phone_country_code: str | None = None


class CompanyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=180)
    email: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=40)
    phone_country_code: str | None = Field(None, max_length=5)
    website: str | None = Field(None, max_length=200)
    industry: str | None = Field(None, max_length=120)
    legalName: str | None = Field(None, max_length=180)
    tradeName: str | None = Field(None, max_length=180)
    entityKind: Literal["Individual", "Company"] | None = None
    businessType: str | None = Field(None, max_length=100)
    addresses: list[dict[str, str]] = Field(default_factory=list, max_length=30)
    taxRegistrations: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    primaryContactId: int | None = None
    newPrimaryContact: PrimaryContact | None = None
    roles: list[str] = Field(default_factory=lambda: ["Prospect"], max_length=15)
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["Active", "Inactive", "Blocked"] = "Active"
    notes: str | None = Field(None, max_length=10000)
    confirmShared: bool = False
    sharedReason: str | None = Field(None, max_length=250)
    version: str | None = None


def save_roles(db, actor, row, kind, roles):
    if set(roles) - ROLES:
        raise HTTPException(422, "Employee and application user roles remain permission-controlled in their own modules")
    existing = {x.role: x for x in db.query(BusinessRelationship).filter(owner_filter(BusinessRelationship, kind, row.id))}
    for role in set(roles):
        if role not in existing:
            db.add(BusinessRelationship(organization_id=actor.organization_id, **{{"company": "account_id", "contact": "contact_id"}[kind]: row.id}, role=role))
    for role, link in existing.items():
        if role not in roles:
            db.delete(link)
    if kind == "contact":
        current_tags = {x.strip() for x in (row.tags_text or "").split(",") if x.strip()}
        row.tags_text = ", ".join(sorted((current_tags - ROLES) | set(roles)))
    if kind == "company":
        row.account_type = next((x for x in ["Customer", "Vendor", "Supplier", "Partner", "Prospect"] if x in roles), "Other")
        from app.apps.crm.contact_identity import ContactIdentityLink, tags
        identity = db.query(ContactIdentityLink).filter(ContactIdentityLink.account_id == row.id).first()
        if identity:
            identity.contact.tags_text = ", ".join(sorted((set(tags(identity.contact)) - ROLES) | set(roles)))


def write_company(db, actor, source, data, row=None):
    authorize(actor, source, True, action="edit" if row else "create")
    if source == "hrms":
        crm()._assert_entity_permission("companies", actor, "manage")
    if data.website and not re.match(r"^https?://[^\s]+$", data.website):
        raise HTTPException(422, "Website must be an http or https URL")
    try:
        email = email_address(data.email) if data.email else None
        phone = normalized_phone(data.phone, data.phone_country_code)[0] if data.phone else None
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    keys = ["company-name:" + data.name.casefold()]
    if phone:
        keys.append(normalized_phone(phone, data.phone_country_code)[1])
    if email:
        keys.append(email.casefold())
    keys.extend("tax:" + str(x.get("number", "")).replace(" ", "").upper() for x in data.taxRegistrations if x.get("number"))
    if data.newPrimaryContact:
        if data.newPrimaryContact.phone:
            try:
                keys.append(normalized_phone(data.newPrimaryContact.phone, data.newPrimaryContact.phone_country_code)[1])
            except ValueError as exc:
                raise HTTPException(422, str(exc))
        if data.newPrimaryContact.email:
            keys.append(data.newPrimaryContact.email.casefold())
    lock_matches(db, actor, keys)
    duplicate_guard(db, actor, source, phone, data.phone_country_code, email, data.confirmShared, data.sharedReason, "company", row.id if row else None)
    if not row:
        lock_matches(db, actor, ["company-name:" + data.name.casefold()])
        matches = companies(db, actor, source).filter(func.lower(func.trim(CRMCompany.name)) == data.name.casefold()).limit(20).all()
        if matches and not data.confirmShared:
            raise HTTPException(409, {"code": "duplicate_company", "message": "A company with this name already exists. Review it before creating another.", "matches": [{"id": x.id, "kind": "company", "name": x.name, "url": f"/crm/companies/{x.id}"} for x in matches], "canCreateSeparate": True})
        row = CRMCompany(organization_id=actor.organization_id, name=data.name, owner_user_id=actor.id, created_by_user_id=actor.id)
        db.add(row); db.flush()
    elif data.version != version(row):
        raise HTTPException(409, "Company changed. Reload before saving")
    row.name, row.email, row.phone, row.phone_country_code = data.name, email, phone, data.phone_country_code if phone else None
    row.website, row.industry, row.status, row.notes = data.website, data.industry, data.status, data.notes
    if any("," in x or len(x) > 40 or x.strip().casefold() in {"employee", "user", "admin", "manager", "staff", "intern", "super admin"} for x in data.tags) or len(", ".join(data.tags)) > 500:
        raise HTTPException(422, "Use tags of up to 40 characters")
    row.tags_text = ", ".join(sorted(set(data.tags)))
    details = db.get(CompanyMasterDetails, row.id)
    if not details:
        details = CompanyMasterDetails(account_id=row.id, organization_id=actor.organization_id, addresses=[], tax_registrations=[])
        db.add(details)
    # Legal identifiers suggest matches; never join organizations by a name alone.
    if any(len(json.dumps(x)) > 2000 for x in data.addresses + data.taxRegistrations):
        raise HTTPException(422, "Address or tax registration exceeds the field limit")
    for registration in data.taxRegistrations:
        number = str(registration.get("number", "")).replace(" ", "").upper()
        if not number:
            continue
        for candidate in db.query(CompanyMasterDetails).filter(CompanyMasterDetails.organization_id == actor.organization_id, CompanyMasterDetails.account_id != row.id, CompanyMasterDetails.account_id.in_(companies(db, actor, source).with_entities(CRMCompany.id))):
            if any(str(x.get("number", "")).replace(" ", "").upper() == number for x in candidate.tax_registrations or []):
                if not data.confirmShared:
                    raise HTTPException(409, {"code": "duplicate_company", "message": "This legal identifier is already associated with a company.", "matches": [{"kind": "company", "id": candidate.account_id}], "canCreateSeparate": True})
    details.legal_name, details.trade_name = data.legalName, data.tradeName
    details.business_type = "Individual" if data.entityKind == "Individual" else (None if data.entityKind == "Company" and data.businessType == "Individual" else data.businessType)
    details.addresses, details.tax_registrations = data.addresses, data.taxRegistrations
    details.version = (details.version or 0) + 1
    primary = owner(db, actor, "contact", data.primaryContactId, source) if data.primaryContactId else None
    if data.newPrimaryContact:
        authorize(actor, source, True, "contacts")
        if source == "hrms":
            crm()._assert_entity_permission("contacts", actor, "manage")
        item = data.newPrimaryContact
        duplicate_guard(db, actor, source, item.phone, item.phone_country_code, item.email, data.confirmShared, data.sharedReason)
        try:
            contact_email = email_address(item.email) if item.email else None
            contact_phone = normalized_phone(item.phone, item.phone_country_code)[0] if item.phone else None
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        primary = CRMContact(organization_id=actor.organization_id, company_id=row.id, company_name=row.name, full_name=item.name, first_name=item.name.split(" ", 1)[0], email=contact_email, phone=contact_phone, phone_country_code=item.phone_country_code if contact_phone else None, owner_user_id=actor.id, created_by_user_id=actor.id, lifecycle_stage="Prospect")
        db.add(primary); db.flush()
    if primary:
        details.primary_contact_id = primary.id
        if not db.get(CompanyContactLink, (row.id, primary.id)):
            db.add(CompanyContactLink(account_id=row.id, contact_id=primary.id, organization_id=actor.organization_id))
    elif "primaryContactId" in data.model_fields_set:
        details.primary_contact_id = None
    save_roles(db, actor, row, "company", data.roles)
    row.updated_by_user_id, row.updated_at = actor.id, datetime.now(timezone.utc)
    audit(db, actor, "COMPANY_MASTER_SAVED", "company", row.id, {"roles": data.roles, "sharedReason": data.sharedReason})
    db.flush()
    return row


@router.post("/companies", status_code=201)
def create_company(data: CompanyInput, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = write_company(db, actor, source, data)
    db.commit()
    return company_output(db, row)


@router.patch("/companies/{ident}")
def edit_company(ident: int, data: CompanyInput, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = owner(db, actor, "company", ident, source, True)
    write_company(db, actor, source, data, row)
    db.commit()
    return company_output(db, row)


@router.get("/companies/{ident}")
def company_profile(ident: int, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = owner(db, actor, "company", ident, source)
    q = db.query(CRMContact).filter(CRMContact.organization_id == actor.organization_id, CRMContact.deleted_at.is_(None), or_(CRMContact.company_id == ident, CRMContact.id.in_(select(CompanyContactLink.contact_id).where(CompanyContactLink.account_id == ident))))
    if source == "crm":
        try:
            crm()._assert_entity_permission("contacts", actor, "view")
            q = crm()._apply_record_visibility(q, crm()._get_resource("contacts"), actor, db)
        except HTTPException:
            q = q.filter(False)
    result = company_output(db, row)
    result["contacts"] = [{"id": x.id, "name": x.full_name, "email": x.email, "phone": x.phone} for x in q.limit(100)]
    result["relationships"] = [{"role": x.role, "status": x.status, "category": x.category, "paymentTerms": x.payment_terms, "creditLimit": x.credit_limit, "nextFollowUp": x.follow_up_at, "notes": x.notes} for x in db.query(BusinessRelationship).filter(BusinessRelationship.account_id == ident)]
    result["channels"] = effective_channels(db, row, "company")
    # Financial records are never inferred by matching company names.
    result["purchases"] = []
    result["payables"] = None
    result["financialNote"] = "No verified accounting link is configured for this company."
    from app.access.catalog import permission_names
    from app.module_registry import is_app_enabled
    permissions = permission_names(actor)
    grant = (getattr(actor, "_suite_grants", None) or {}).get("fam", {})
    accounting_access = actor.is_superuser or (grant.get("enabled") and "view" in grant.get("actions", []) and grant.get("scope") in {"organization", "all"})
    if accounting_access and is_app_enabled("fam") and is_app_enabled("srm"):
        from app.apps.srm.commercial_models import CustomerLink
        from app.apps.fam.models import FAMParty, FAMPurchaseBill, FAMBillReference
        account_ids = select(CustomerLink.source_id).where(CustomerLink.organization_id == actor.organization_id, CustomerLink.customer_id == ident, CustomerLink.source_type == "crm_account")
        party_ids = select(FAMParty.id).where(FAMParty.company_id == actor.organization_id, FAMParty.crm_account_id.in_(account_ids))
        if db.query(FAMParty.id).filter(FAMParty.id.in_(party_ids)).first():
            result["financialNote"] = "Verified accounting records in your authorized branch."
            if actor.is_superuser or permissions.intersection({"fam_admin", "fam_purchase_view", "fam_purchase_manage"}):
                result["purchases"] = [{"id": x.id, "number": x.bill_number, "date": x.bill_date, "total": x.grand_total, "status": x.status} for x in db.query(FAMPurchaseBill).filter(FAMPurchaseBill.company_id == actor.organization_id, FAMPurchaseBill.vendor_id.in_(party_ids)).order_by(FAMPurchaseBill.bill_date.desc(), FAMPurchaseBill.id.desc()).limit(50)]
            if actor.is_superuser or permissions.intersection({"fam_admin", "fam_ap_view", "fam_ap_manage"}):
                result["payables"] = db.query(func.coalesce(func.sum(FAMBillReference.outstanding_amount), 0)).filter(FAMBillReference.company_id == actor.organization_id, FAMBillReference.party_id.in_(party_ids), FAMBillReference.bill_type.in_(["bill", "credit_note", "opening"]), FAMBillReference.outstanding_amount > 0).scalar()
    try:
        authorize(actor, source, True, action="edit")
        result["canEdit"] = True
    except HTTPException:
        result["canEdit"] = False
    return result


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1, max_length=60)
    role: str = Field(max_length=30)
    status: Literal["Active", "Inactive", "Blocked"] = "Active"
    category: str | None = Field(None, max_length=100)
    paymentTerms: str | None = Field(None, max_length=250)
    creditLimit: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    nextFollowUp: datetime | None = None
    notes: str | None = Field(None, max_length=10000)


@router.put("/{kind}/{ident}/relationship")
def put_relationship(kind: Literal["contact", "company"], ident: int, data: RoleUpdate, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = owner(db, actor, kind, ident, source, True)
    if data.version != version(row):
        raise HTTPException(409, "Relationship details changed. Reload the company before saving")
    if data.role not in ROLES:
        raise HTTPException(422, "Choose a business relationship; account privileges are managed separately")
    current = relationships(db, row, kind)
    save_roles(db, actor, row, kind, list(set(current) | {data.role}))
    db.flush()
    link = db.query(BusinessRelationship).filter(owner_filter(BusinessRelationship, kind, ident), BusinessRelationship.role == data.role).one()
    link.status, link.category, link.payment_terms, link.credit_limit = data.status, data.category, data.paymentTerms, data.creditLimit
    link.follow_up_at, link.notes = data.nextFollowUp, data.notes
    row.updated_at = datetime.now(timezone.utc)
    audit(db, actor, "BUSINESS_RELATIONSHIP_UPDATED", kind, ident, data.model_dump())
    db.commit()
    return {"roles": relationships(db, row, kind)}


class BirthdayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: int | None = Field(None, ge=1, le=31)
    month: int | None = Field(None, ge=1, le=12)
    year: int | None = Field(None, ge=1900, le=9999)
    emailOptIn: bool = False
    whatsappOptIn: bool = False
    smsOptIn: bool = False
    reminders: bool = False
    version: int = 0

    @model_validator(mode="after")
    def valid_date(self):
        if self.day is None and self.month is None and self.year is None:
            return self
        if self.day is None or self.month is None:
            raise ValueError("Enter both day and month; year is optional")
        date(self.year or 2000, self.month, self.day)  # Validation only, never stored as a fictitious year.
        if self.year and date(self.year, self.month, self.day) > date.today():
            raise ValueError("Birthday cannot be in the future")
        return self


def birthday_owner(db, actor, kind, ident, source, write=False):
    if kind == "employee":
        if source != "hrms":
            raise HTTPException(403, "HR birthday access is required")
        authorize(actor, "hrms", write)
        from app.models.employee import Employee
        from app.common.services.profiles import can_manage
        row = db.query(Employee).filter(Employee.id == ident, Employee.deleted_at.is_(None)).first()
        if not row or not (row.user_id == actor.id or can_manage(actor)):
            raise HTTPException(404, "Employee is unavailable in your HR scope")
        return row
    row = owner(db, actor, kind, ident, source, write)
    if kind == "contact":
        from app.apps.crm.contact_identity import ContactIdentityLink
        linked = db.query(ContactIdentityLink).filter(ContactIdentityLink.contact_id == ident, ContactIdentityLink.employee_id.is_not(None)).first()
        if linked:
            # Linked employee birthdays always resolve to the HR-owned master;
            # having CRM contact access does not expose private HR information.
            birthday_owner(db, actor, "employee", linked.employee_id, source, write)
            return db.get(__import__("app.models.employee", fromlist=["Employee"]).Employee, linked.employee_id)
    return row


def birthday_key(row, kind):
    return ("employee", row.id) if row.__table__.name == "employees" else (kind, row.id)


def birthday_output(saved, legacy=None):
    # Old full dates remain the legally maintained source until an explicit edit.
    day = saved.birth_day if saved else legacy.day if legacy else None
    month = saved.birth_month if saved else legacy.month if legacy else None
    year = saved.birth_year if saved else legacy.year if legacy else None
    result = {"id": saved.id if saved else None, "day": day, "month": month, "year": year,
        "version": saved.version if saved else 0, "emailOptIn": bool(saved and saved.email_opt_in), "whatsappOptIn": bool(saved and saved.whatsapp_opt_in), "smsOptIn": bool(saved and saved.sms_opt_in), "reminders": bool(saved and saved.reminders_enabled)}
    if year and day and month:
        today = date.today()
        result["age"] = today.year - year - ((today.month, today.day) < (month, day))
    return result


@router.get("/{kind}/{ident}/birthday")
def get_birthday(kind: Literal["contact", "person", "employee"], ident: int, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = birthday_owner(db, actor, kind, ident, source)
    effective_kind, effective_id = birthday_key(row, kind)
    saved = db.query(ContactBirthday).filter(owner_filter(ContactBirthday, effective_kind, effective_id)).first()
    return birthday_output(saved, getattr(row, "date_of_birth", None))


@router.put("/{kind}/{ident}/birthday")
def put_birthday(kind: Literal["contact", "person", "employee"], ident: int, data: BirthdayInput, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = birthday_owner(db, actor, kind, ident, source, True)
    effective_kind, effective_id = birthday_key(row, kind)
    saved = db.query(ContactBirthday).filter(owner_filter(ContactBirthday, effective_kind, effective_id)).with_for_update().first()
    if data.version != (saved.version if saved else 0):
        raise HTTPException(409, "Birthday preferences changed. Reload before saving")
    if not saved:
        saved = ContactBirthday(organization_id=actor.organization_id, **{{"contact": "contact_id", "person": "person_id", "employee": "employee_id"}[effective_kind]: effective_id}, version=0)
        db.add(saved)
    saved.birth_day, saved.birth_month, saved.birth_year = data.day, data.month, data.year
    saved.email_opt_in, saved.whatsapp_opt_in, saved.sms_opt_in, saved.reminders_enabled = data.emailOptIn, data.whatsappOptIn, data.smsOptIn, data.reminders
    saved.version += 1
    # Business contacts use the partial master and a full-date compatibility
    # projection only when a real year exists. Private HR compliance DOB is kept.
    if effective_kind == "contact":
        row.date_of_birth = date(data.year, data.month, data.day) if data.year and data.month and data.day else None
    row.updated_at = datetime.now(timezone.utc)
    audit(db, actor, "BIRTHDAY_PREFERENCES_UPDATED", effective_kind, effective_id, {"partial": data.year is None, "consentChanged": True})
    db.commit()
    return birthday_output(saved)


@router.get("/birthdays/upcoming")
def upcoming_birthdays(source: Source = "crm", days: int = Query(30, ge=0, le=366), page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    authorize(actor, source, entity="contacts")
    today = date.today()
    if source == "hrms":
        from app.common.services.profiles import can_manage
        from app.models.employee import Employee
        if not can_manage(actor):
            raise HTTPException(403, "HR profile management is required for the employee birthday directory")
        records = db.query(Employee).filter(Employee.deleted_at.is_(None))
        model, kind = Employee, "employee"
    else:
        records = db.query(CRMContact).filter(CRMContact.organization_id == actor.organization_id, CRMContact.deleted_at.is_(None))
        from app.apps.crm.contact_identity import ContactIdentityLink
        records = records.filter(~CRMContact.id.in_(select(ContactIdentityLink.contact_id).where(ContactIdentityLink.employee_id.is_not(None))))
        if source == "crm":
            records = crm()._apply_record_visibility(records, crm()._get_resource("contacts"), actor, db)
        else:
            records = records.filter(CRMContact.company_id.in_(companies(db, actor, source).with_entities(CRMCompany.id)))
        model, kind = CRMContact, "contact"
    # Restrict candidates by birthday-bearing source IDs; no HR rows enter CRM.
    records = records.filter(or_(model.date_of_birth.is_not(None), model.id.in_(select(getattr(ContactBirthday, "employee_id" if kind == "employee" else "contact_id")).where(ContactBirthday.birth_day.is_not(None)))))
    result = []
    birthday_field = getattr(ContactBirthday, "employee_id" if kind == "employee" else "contact_id")
    for row, saved in records.outerjoin(ContactBirthday, birthday_field == model.id).add_entity(ContactBirthday).yield_per(200):
        birthday = birthday_output(saved, row.date_of_birth)
        if not birthday["month"] or not birthday["day"]:
            continue
        try:
            next_date = date(today.year, birthday["month"], birthday["day"])
        except ValueError:
            next_date = date(today.year, 3, 1)  # Leap-day reminder policy; stored birthday is unchanged.
        if next_date < today:
            try:
                next_date = next_date.replace(year=today.year + 1)
            except ValueError:
                next_date = date(today.year + 1, 3, 1)
        remaining = (next_date - today).days
        if remaining <= days:
            name = row.full_name if kind == "contact" else " ".join(filter(None, [row.first_name, row.last_name]))
            result.append({"id": row.id, "kind": kind, "name": name, "birthday": birthday, "nextBirthday": next_date, "daysAway": remaining})
    result.sort(key=lambda x: (x["daysAway"], x["name"], x["id"]))
    return {"items": result[(page - 1) * per_page:page * per_page], "total": len(result), "leapDayPolicy": "March 1 in non-leap years", "templates": [{"id": "birthday-warm", "subject": "Happy birthday, {name}", "body": "Wishing you a wonderful birthday, {name}!"}]}


class GreetingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["email", "whatsapp", "sms"]
    year: int = Field(ge=2000, le=9999)


@router.post("/{kind}/{ident}/birthday/prepare-greeting")
def prepare_greeting(kind: Literal["contact", "employee"], ident: int, data: GreetingInput, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = birthday_owner(db, actor, kind, ident, source, True)
    effective_kind, effective_id = birthday_key(row, kind)
    birthday = db.query(ContactBirthday).filter(owner_filter(ContactBirthday, effective_kind, effective_id)).with_for_update().first()
    if not birthday or not birthday.birth_day or not getattr(birthday, data.channel + "_opt_in"):
        raise HTTPException(409, "Recipient opt-in and a saved birthday are required")
    if data.year != date.today().year:
        raise HTTPException(422, "Prepare greetings for the current year")
    from urllib.parse import quote
    from app.apps.communication.services.delivery import is_opted_out
    destination = getattr(row, "email", None)
    if data.channel != "email":
        try:
            destination = normalized_phone(getattr(row, "phone", None), getattr(row, "phone_country_code", None))[1]
        except ValueError:
            raise HTTPException(422, "A valid primary phone and country code are required")
    if not destination:
        raise HTTPException(422, "Add a primary email before preparing an email greeting")
    if is_opted_out(db, destination, data.channel) or str(getattr(row, "status", "")).casefold() == "do not contact":
        raise HTTPException(409, "This recipient has opted out of this channel")
    name = getattr(row, "full_name", None) or getattr(row, "first_name", "")
    subject, body = f"Happy birthday, {name}", f"Wishing you a wonderful birthday, {name}!"
    compose_url = f"mailto:{quote(destination)}?subject={quote(subject)}&body={quote(body)}" if data.channel == "email" else f"https://wa.me/{destination.lstrip('+')}?text={quote(body)}" if data.channel == "whatsapp" else f"sms:{destination}?body={quote(body)}"
    draft = {"subject": subject, "body": body, "composeUrl": compose_url, "message": "Greeting draft ready for review. No message has been sent."}
    existing = db.query(GreetingReservation).filter_by(birthday_id=birthday.id, year=data.year, channel=data.channel).first()
    if existing:
        return {"id": existing.id, "status": existing.status, "alreadyPrepared": True, **draft}
    reservation = GreetingReservation(organization_id=actor.organization_id, birthday_id=birthday.id, year=data.year, channel=data.channel, created_by_user_id=actor.id)
    db.add(reservation)
    audit(db, actor, "BIRTHDAY_GREETING_PREPARED", effective_kind, effective_id, {"channel": data.channel, "year": data.year})
    db.commit()
    return {"id": reservation.id, "status": "prepared", "alreadyPrepared": False, **draft}


def capture_options(payload):
    """Remove strictly validated transport metadata before legacy field validation."""
    items = payload.pop("communication_channels", None)
    expected = payload.pop("communication_version", None)
    confirmed = payload.pop("confirmShared", False)
    reason = payload.pop("sharedReason", None)
    if type(confirmed) is not bool or reason is not None and (not isinstance(reason, str) or len(reason) > 250):
        raise HTTPException(422, "Invalid shared-contact confirmation")
    if items is not None:
        if not isinstance(items, list) or len(items) > 100:
            raise HTTPException(422, "Use at most 100 communication entries")
        try:
            items = [ChannelInput.model_validate(x) for x in items]
        except ValueError as exc:
            raise HTTPException(422, "Check the communication entry fields") from exc
        for kind, field in [("email", "email"), ("phone", "phone")]:
            choices = [x for x in items if x.kind == kind]
            if sum(x.primary for x in choices) > 1:
                raise HTTPException(422, "Choose one primary entry per communication kind")
            primary = next((x for x in choices if x.primary), choices[0] if choices else None)
            payload[field] = channel_values(primary)["value"] if primary else None
            if kind == "phone":
                payload["phone_country_code"] = primary.countryCode if primary else None
    return {"items": items, "expected": expected, "confirmed": confirmed, "reason": reason}


def persist_capture_channels(db, actor, row, options, initial_version=None):
    if options["items"] is None:
        return
    if initial_version is not None and options["expected"] != initial_version:
        raise HTTPException(409, "Communication details changed. Reload before saving")
    previous = db.info.get("defer_master_commit")
    db.info["defer_master_commit"] = True
    try:
        update_channels("contact" if isinstance(row, CRMContact) else "company", row.id, ChannelsUpdate(items=options["items"], version=version(row), confirmShared=options["confirmed"], sharedReason=options["reason"]), "crm", db, actor)
    finally:
        if previous is None:
            db.info.pop("defer_master_commit", None)
        else:
            db.info["defer_master_commit"] = previous


@router.get("/company-directory/query")
def company_grid(state: str = Query("{}", max_length=16000), source: Source = "crm", role: str = "", deleted: bool = False, db: Session = Depends(get_db), actor: User = Depends(get_current_user), entity_kind: Literal["all", "companies", "individuals"] = "all"):
    from app.shared.data_grid import parse_query, GridField, apply_filters, apply_path, apply_sort, field_for
    parsed = parse_query(state)
    q = filter_entity_kind(companies(db, actor, source, deleted), entity_kind)
    if role:
        if role not in ROLES:
            raise HTTPException(422, "Unknown business role")
        q = q.filter(or_(CRMCompany.account_type == role, CRMCompany.id.in_(select(BusinessRelationship.account_id).where(BusinessRelationship.role == role))))
    fields = {name: GridField(getattr(CRMCompany, name), "id" if name == "id" else "datetime" if name in {"created_at", "updated_at"} else "text") for name in ["id", "name", "email", "phone", "industry", "status", "account_type", "tags_text", "created_at", "updated_at"]}
    q = apply_filters(q, parsed, fields)
    if parsed.search:
        value = "%" + parsed.search.replace("%", "\\%").replace("_", "\\_") + "%"
        q = q.filter(or_(CRMCompany.name.ilike(value, escape="\\"), CRMCompany.email.ilike(value, escape="\\"), CRMCompany.phone.ilike(value, escape="\\")))
    total = q.count()
    branch = apply_path(q, parsed, fields)
    def can(action):
        try:
            authorize(actor, source, action in {"edit", "delete", "create"}, action=action)
            return True
        except HTTPException:
            return False
    result = {"rows": [], "groups": [], "total": total, "pageTotal": branch.count(), "page": parsed.page, "pageSize": parsed.pageSize, "permissions": {"edit": can("edit"), "archive": can("delete"), "export": can("export")}, "context": {"canCreate": can("create")}}
    if len(parsed.path) < len(parsed.grouping):
        name = parsed.grouping[len(parsed.path)]
        column = field_for(fields, name).expression
        groups = branch.with_entities(column, func.count(CRMCompany.id)).group_by(column)
        result["pageTotal"] = groups.count()
        for key, count in groups.order_by(column).offset((parsed.page - 1) * parsed.pageSize).limit(parsed.pageSize):
            value = key.isoformat() if isinstance(key, datetime) else key
            result["groups"].append({"field": name, "value": value, "label": str(value or "Not set"), "count": count, "aggregates": [], "path": [x.model_dump() for x in parsed.path] + [{"field": name, "value": value}]})
    else:
        result["rows"] = [company_output(db, x) for x in apply_sort(branch, parsed, fields, CRMCompany.id).offset((parsed.page - 1) * parsed.pageSize).limit(parsed.pageSize)]
    return result


class CompanyBulk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[int] = Field(min_length=1, max_length=200)
    action: Literal["role", "tag", "trash", "restore"]
    value: str | None = Field(None, max_length=40)


@router.post("/company-directory/bulk")
def company_bulk(data: CompanyBulk, source: Source = "crm", db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    authorize(actor, source, True, action="delete" if data.action == "trash" else "edit")
    rows = companies(db, actor, source, deleted=data.action == "restore").filter(CRMCompany.id.in_(set(data.ids))).order_by(CRMCompany.id).with_for_update().all()
    if len(rows) != len(set(data.ids)):
        raise HTTPException(404, "One or more companies are unavailable in your scope")
    if data.action == "role" and data.value not in ROLES:
        raise HTTPException(422, "Choose a business role")
    if data.action == "tag" and (not data.value or "," in data.value):
        raise HTTPException(422, "Enter a tag without commas")
    for row in rows:
        if data.action == "role":
            save_roles(db, actor, row, "company", list(set(relationships(db, row, "company")) | {data.value}))
        elif data.action == "tag":
            tags = set(filter(None, (row.tags_text or "").split(","))) | {data.value}
            if len(", ".join(tags)) > 500:
                raise HTTPException(422, "Too many tags")
            row.tags_text = ", ".join(sorted(tags))
        else:
            row.deleted_at = datetime.now(timezone.utc) if data.action == "trash" else None
        row.updated_at = datetime.now(timezone.utc)
        audit(db, actor, "COMPANY_" + data.action.upper(), "company", row.id, {"value": data.value})
    db.commit()
    return {"updated": len(rows)}


class CompanyExport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str = Field("{}", max_length=16000)
    ids: list[int] | None = Field(None, max_length=10000)
    columns: list[str] = Field(default_factory=lambda: ["name", "email", "phone", "status", "roles"])


@router.post("/company-directory/export")
def export_companies(data: CompanyExport, source: Source = "crm", role: str = "", deleted: bool = False, db: Session = Depends(get_db), actor: User = Depends(get_current_user), entity_kind: Literal["all", "companies", "individuals"] = "all"):
    import csv
    import io
    from fastapi.responses import Response
    from app.shared.data_grid import parse_query, safe_cell
    authorize(actor, source, action="export")
    columns = data.columns
    if not columns or set(columns) - {"name", "email", "phone", "industry", "status", "roles", "tags", "account_type", "tags_text"}:
        raise HTTPException(422, "Unsupported export columns")
    parsed = parse_query(data.state)
    parsed.grouping, parsed.path, parsed.page, parsed.pageSize = [], [], 1, 200
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    first = company_grid(parsed.model_dump_json(), source, role, deleted, db, actor, entity_kind)
    if first["total"] > 10000:
        raise HTTPException(422, "Narrow the export to 10,000 companies")
    count = 0
    while True:
        result = first if parsed.page == 1 else company_grid(parsed.model_dump_json(), source, role, deleted, db, actor, entity_kind)
        for row in result["rows"]:
            if data.ids is not None and row["id"] not in data.ids:
                continue
            writer.writerow([safe_cell(", ".join(row.get({"account_type":"roles", "tags_text":"tags"}.get(column, column)) or []) if column in {"roles", "tags", "account_type", "tags_text"} else row.get(column)) for column in columns])
            count += 1
        if parsed.page * parsed.pageSize >= result["total"]:
            break
        parsed.page += 1
    audit(db, actor, "COMPANY_EXPORT", "company", None, {"count": count})
    db.commit()
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=companies.csv"})
