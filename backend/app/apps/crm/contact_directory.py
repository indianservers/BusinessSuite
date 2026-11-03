"""Permission-scoped directory over existing CRM contacts, not a second store."""
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, and_, exists, select, inspect
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.audit import AuditLog
from app.apps.crm.models import CRMContact, CRMLead, CRMCompany, CRMLeadConversionLog
from app.apps.crm.financial_data import FinancialData, save_profile
from app.apps.crm.financial_models import ContactFinancialProfile
from app.apps.crm.contact_identity import ContactIdentityLink, tags, add_tags, link_source

router = APIRouter(prefix="/contact-directory", tags=["Universal contacts"])
CLASSIFICATIONS = ["Lead", "Prospect", "Customer", "Vendor", "Supplier", "Partner", "Friend", "Consultant", "Dealer", "Distributor", "Investor", "Other"]
IDENTITY_TAGS = {"employee", "user", "admin", "manager", "staff", "intern", "super admin"}


def core():
    from app.apps.crm.api import router as crm
    return crm


def allowed(actor, action="view"):
    core()._assert_entity_permission("contacts", actor, action)


def base(db, actor, deleted=False):
    crm = core()
    allowed(actor)
    q = crm._apply_record_visibility(crm._base_query(db, crm._get_resource("contacts"), crm._organization_id(db, actor), include_deleted=True), crm._get_resource("contacts"), actor, db)
    return q.filter(CRMContact.deleted_at.is_not(None) if deleted else CRMContact.deleted_at.is_(None))


def get_contact(db, actor, ident, deleted=False, lock=False):
    q = base(db, actor, deleted).filter(CRMContact.id == ident)
    item = (q.with_for_update() if lock else q).first()
    if not item:
        raise HTTPException(404, "Contact is unavailable in your scope")
    return item


def version(row):
    return (row.updated_at or row.created_at).isoformat() if row.updated_at or row.created_at else "0"


def labels(row):
    values = set(tags(row))
    if row.lifecycle_stage in {"Lead", "Prospect", "Customer"}:
        values.add(row.lifecycle_stage)
    # Access roles are never inferred from descriptive tags or returned as tags.
    return sorted(x for x in values if x.casefold() not in IDENTITY_TAGS)


def serialize(row):
    return {"id": row.id, "name": row.full_name, "email": row.email, "phone": row.phone,
        "phoneCountryCode": row.phone_country_code, "organization": row.company_name, "companyId": row.company_id,
        "ownerId": row.owner_user_id, "status": row.status, "tags": labels(row),
        "lastInteraction": row.last_contacted_at, "nextFollowUp": row.next_follow_up_at,
        "createdAt": row.created_at, "updatedAt": row.updated_at, "version": version(row),
        "deletedAt": row.deleted_at, "notes": row.notes,
        "roles": [x for x in labels(row) if x in CLASSIFICATIONS], "lifecycleStage": row.lifecycle_stage}


def tagged(label):
    clean = label.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    normalized = func.replace(func.coalesce(CRMContact.tags_text, ""), ", ", ",")
    exact = func.lower("," + normalized + ",").like(f"%,{clean},%", escape="\\")
    return or_(exact, CRMContact.lifecycle_stage == label)


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["name", "email", "phone", "organization", "status", "tag", "owner"]
    operator: Literal["contains", "equals", "empty"] = "contains"
    value: str = Field("", max_length=180)


def filtered(q, search="", relationship="", status="", filters="", match="and"):
    if search:
        term = "%" + search.replace("%", "\\%").replace("_", "\\_") + "%"
        q = q.filter(or_(*(column.ilike(term, escape="\\") for column in [CRMContact.full_name, CRMContact.email, CRMContact.phone, CRMContact.company_name])))
    if relationship:
        if relationship.casefold() in IDENTITY_TAGS:
            # HR/account directories retain their own authorization and data.
            return q.filter(False)
        q = q.filter(tagged(relationship))
    if status:
        q = q.filter(CRMContact.status == status)
    if filters:
        try:
            raw = json.loads(filters)
            if not isinstance(raw, list) or len(raw) > 12:
                raise ValueError()
            conditions = [Condition.model_validate(x) for x in raw]
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid contact filters")
        clauses = []
        columns = {"name": CRMContact.full_name, "email": CRMContact.email, "phone": CRMContact.phone, "organization": CRMContact.company_name, "status": CRMContact.status, "owner": CRMContact.owner_user_id}
        for condition in conditions:
            if condition.field == "tag":
                clauses.append(tagged(condition.value) if condition.value.casefold() not in IDENTITY_TAGS else CRMContact.id < 0)
                continue
            column = columns[condition.field]
            if condition.operator == "empty":
                clauses.append(or_(column.is_(None), column == "") if condition.field != "owner" else column.is_(None))
            elif condition.field == "owner":
                if not condition.value.isdigit():
                    raise HTTPException(422, "Owner must be a user ID")
                clauses.append(column == int(condition.value))
            elif condition.operator == "equals":
                clauses.append(func.lower(column) == condition.value.lower())
            else:
                value = condition.value.replace("%", "\\%").replace("_", "\\_")
                clauses.append(column.ilike(f"%{value}%", escape="\\"))
        if clauses:
            q = q.filter((or_ if match == "or" else and_)(*clauses))
    return q


def audit(db, actor, row, action, before=None, after=None):
    db.add(AuditLog(organization_id=row.organization_id, user_id=actor.id, method="POST", endpoint="/crm/contact-directory", entity_type="contact", entity_id=row.id,
        action=action, old_values=json.dumps(before, default=str) if before else None,
        new_values=json.dumps(after, default=str) if after else None, module="crm", status_code=200))


@router.get("")
def directory(search: str = Query("", max_length=180), relationship: str = Query("", max_length=50), status: str = Query("", max_length=40),
    deleted: bool = False, page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100),
    sort: Literal["name", "updated", "created", "organization", "status", "followup", "gstNumber", "bankAccounts", "upi"] = "updated", direction: Literal["asc", "desc"] = "desc",
    filters: str = Query("", max_length=5000), match: Literal["and", "or"] = "and", recent: bool = False, created_recent: bool = False, ids: str = Query("", max_length=2000),
    db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    all_rows = base(db, actor, deleted)
    q = filtered(all_rows, search, relationship, status, filters, match)
    if ids:
        try:
            selected_ids = [int(x) for x in ids.split(",")]
            if len(selected_ids) > 200:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "Invalid contact selection")
        q = q.filter(CRMContact.id.in_(selected_ids))
    if recent:
        q = q.filter(func.coalesce(CRMContact.updated_at, CRMContact.created_at) >= datetime.now(timezone.utc) - timedelta(days=7))
    if created_recent:
        q = q.filter(CRMContact.created_at >= datetime.now(timezone.utc) - timedelta(days=7))
    columns = {"name": CRMContact.full_name, "updated": func.coalesce(CRMContact.updated_at, CRMContact.created_at), "created": CRMContact.created_at, "organization": CRMContact.company_name, "status": CRMContact.status, "followup": CRMContact.next_follow_up_at}
    if sort in {"gstNumber", "bankAccounts", "upi"}:
        q = q.outerjoin(ContactFinancialProfile, ContactFinancialProfile.contact_id == CRMContact.id)
        columns.update({"gstNumber": func.coalesce(ContactFinancialProfile.gst_number, ""), "bankAccounts": func.coalesce(func.json_array_length(ContactFinancialProfile.bank_accounts), 0), "upi": func.coalesce(func.json_array_length(ContactFinancialProfile.upi_ids), 0)})
    column = columns[sort]
    total = q.count()
    rows = q.order_by(column.asc() if direction == "asc" else column.desc(), CRMContact.id).offset((page - 1) * per_page).limit(per_page).all()
    stats = {"total": all_rows.count()}
    for label in ["Lead", "Prospect", "Customer", "Vendor", "Partner"]:
        stats[label] = all_rows.filter(tagged(label)).count()
    stats["recent"] = all_rows.filter(CRMContact.created_at >= datetime.now(timezone.utc) - timedelta(days=7)).count()
    try:
        allowed(actor, "manage")
        manage = True
    except HTTPException:
        manage = False
    can_convert = False
    lead_ids = {}
    try:
        crm = core()
        crm._assert_entity_permission("leads", actor, "view")
        resource = crm._get_resource("leads")
        lead_query = crm._apply_record_visibility(crm._base_query(db, resource, crm._organization_id(db, actor)), resource, actor, db)
        links = db.query(ContactIdentityLink).filter(ContactIdentityLink.contact_id.in_([x.id for x in rows]), ContactIdentityLink.lead_id.is_not(None)).all()
        visible = {x.id for x in lead_query.filter(CRMLead.id.in_([x.lead_id for x in links]), CRMLead.is_converted.is_(False)).all()}
        for link in links:
            if link.lead_id in visible:
                lead_ids.setdefault(link.contact_id, []).append(link.lead_id)
        crm._assert_entity_permission("leads", actor, "manage")
        can_convert = manage
    except HTTPException:
        pass
    grant = (getattr(actor, "_suite_grants", None) or {}).get("crm")
    can_export = manage and (actor.is_superuser or grant is None or "export" in grant.get("actions", []))
    profiles = {x.contact_id: x for x in db.query(ContactFinancialProfile).filter(ContactFinancialProfile.contact_id.in_([x.id for x in rows])).all()}
    def financial_summary(ident):
        profile = profiles.get(ident)
        return {"gstNumber": profile.gst_number or "", "bankAccountCount": len(profile.bank_accounts), "upiCount": len(profile.upi_ids)} if profile else {"gstNumber": "", "bankAccountCount": 0, "upiCount": 0}
    return {"items": [{**serialize(x), **financial_summary(x.id), "unconvertedLeadIds": lead_ids.get(x.id, [])} for x in rows], "total": total, "page": page, "stats": stats, "canManage": manage, "canConvert": can_convert, "canExport": can_export, "canPermanentlyDelete": actor.is_superuser, "classifications": CLASSIFICATIONS}


@router.get("/export")
def export_contacts(search: str = "", relationship: str = "", filters: str = Query("", max_length=5000), match: Literal["and", "or"] = "and", ids: str = Query("", max_length=2000), status: str = "", recent: bool = False, created_recent: bool = False, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed(actor, "manage")
    q = filtered(base(db, actor), search, relationship, status=status, filters=filters, match=match)
    if ids:
        try:
            selection = [int(x) for x in ids.split(",")]
            if len(selection) > 200:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "Invalid contact selection")
        q = q.filter(CRMContact.id.in_(selection))
    if recent:
        q = q.filter(func.coalesce(CRMContact.updated_at, CRMContact.created_at) >= datetime.now(timezone.utc) - timedelta(days=7))
    if created_recent:
        q = q.filter(CRMContact.created_at >= datetime.now(timezone.utc) - timedelta(days=7))
    if q.count() > 10000:
        raise HTTPException(422, "Narrow the export to 10,000 contacts")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Organization", "Email", "Phone", "Relationships", "Status", "Company GST number", "Bank accounts", "UPI IDs"])
    def safe(value):
        text = str(value or "")
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
    for row, financial in q.outerjoin(ContactFinancialProfile, ContactFinancialProfile.contact_id == CRMContact.id).add_entity(ContactFinancialProfile).order_by(CRMContact.id).yield_per(200):
        writer.writerow([safe(v) for v in [row.full_name, row.company_name, row.email, row.phone, ", ".join(labels(row)), row.status, financial.gst_number if financial else "", len(financial.bank_accounts) if financial else 0, len(financial.upi_ids) if financial else 0]])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="contacts.csv"', "Cache-Control": "no-store"})


class ContactEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=180)
    email: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=40)
    phoneCountryCode: str | None = Field(None, max_length=5)
    organization: str | None = Field(None, max_length=180)
    status: Literal["Active", "Inactive"] = "Active"
    tags: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(None, max_length=10000)
    nextFollowUp: datetime | None = None
    version: str | None = None
    companyId: int | None = None
    confirmShared: bool = False
    sharedReason: str | None = Field(None, max_length=250)
    communication_channels: list[dict] | None = Field(None, max_length=100)
    communication_version: str | None = None
    roles: list[str] | None = Field(None, max_length=20)
    lifecycleStage: Literal["Lead", "Prospect", "Subscriber", "Customer", "Evangelist", "Inactive", "Other"] | None = None
    financialData: FinancialData | None = None


def apply_edit(db, actor, row, data):
    from app.core.input_validation import email_address, national_phone, calling_code
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Contact name is required")
    known = {x.casefold(): x for x in CLASSIFICATIONS}
    clean_tags = sorted({known.get(x.strip().casefold(), x.strip()) for x in data.tags if x.strip()}, key=str.casefold)
    if any(len(x) > 40 or "," in x or x.casefold() in IDENTITY_TAGS for x in clean_tags) or len(",".join(clean_tags)) > 500:
        raise HTTPException(422, "Use business relationship tags of up to 40 characters. Employee and account roles stay in their authorized modules.")
    try:
        if data.email:
            email_address(data.email)
        if data.phone:
            national_phone(data.phone)
            calling_code(data.phoneCountryCode)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    row.full_name = name
    if "companyId" in data.model_fields_set:
        if data.companyId:
            core()._assert_entity_permission("companies", actor, "view")
            core()._assert_record_visible(db, core()._get_resource("companies"), data.companyId, actor.organization_id, actor)
        row.company_id = data.companyId
    parts = name.split(" ", 1)
    row.first_name, row.last_name = parts[0][:100], parts[1][:100] if len(parts) > 1 else None
    row.email, row.phone, row.phone_country_code = data.email or None, data.phone or None, data.phoneCountryCode if data.phone else None
    row.company_name, row.status = data.organization, data.status
    if row.company_id:
        row.company_name = db.get(CRMCompany, row.company_id).name
    if data.roles is None:
        row.lifecycle_stage = next((x for x in ["Customer", "Lead", "Prospect"] if x in clean_tags), "Other")
    else:
        if set(data.roles) - set(CLASSIFICATIONS):
            raise HTTPException(422, "Choose business relationships; HR and account privileges remain separately controlled")
        clean_tags = sorted(set(clean_tags) | set(data.roles))
        row.lifecycle_stage = data.lifecycleStage or row.lifecycle_stage or "Prospect"
    row.tags_text, row.notes, row.next_follow_up_at = ",".join(clean_tags), data.notes, data.nextFollowUp
    row.updated_by_user_id, row.updated_at = actor.id, datetime.now(timezone.utc)
    if data.financialData is not None:
        db.add(row)
        db.flush()
        save_profile(db, actor, row, data.financialData)


@router.post("")
def create_contact(data: ContactEdit, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed(actor, "manage")
    crm = core()
    from app.shared.master_data import duplicate_guard
    duplicate_guard(db, actor, "crm", data.phone, data.phoneCountryCode, data.email, data.confirmShared, data.sharedReason)
    row = CRMContact(organization_id=crm._organization_id(db, actor), owner_user_id=actor.id, created_by_user_id=actor.id, lifecycle_stage="Prospect")
    apply_edit(db, actor, row, data)
    db.add(row)
    db.flush()
    audit(db, actor, row, "CONTACT_CREATE", after=serialize(row))
    save_directory_channels(db, actor, row, data)
    db.commit()
    return serialize(row)


@router.patch("/{ident}")
def edit_contact(ident: int, data: ContactEdit, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed(actor, "manage")
    row = get_contact(db, actor, ident, lock=True)
    if not data.version or data.version != version(row):
        raise HTTPException(409, "Contact changed. Reload it before saving your edits.")
    before = serialize(row)
    from app.shared.master_data import duplicate_guard
    if (row.phone, row.phone_country_code, row.email) != (data.phone or None, data.phoneCountryCode if data.phone else None, data.email or None):
        duplicate_guard(db, actor, "crm", data.phone, data.phoneCountryCode, data.email, data.confirmShared, data.sharedReason, "contact", ident)
    apply_edit(db, actor, row, data)
    identity_changed = any(before.get(key) != serialize(row).get(key) for key in ["name", "email", "phone", "phoneCountryCode", "organization"])
    if identity_changed:
        crm = core()
        links = db.query(ContactIdentityLink).filter(ContactIdentityLink.contact_id == ident).all()
        for link in links:
            entity = "companies" if link.account_id else "leads" if link.lead_id else None
            source_id = link.account_id or link.lead_id
            if not entity:
                continue
            # Historical converted lead values remain reporting evidence.
            source = link.account if link.account_id else link.lead
            if link.lead_id and source.is_converted:
                continue
            crm._assert_entity_permission(entity, actor, "manage")
            crm._assert_record_visible(db, crm._get_resource(entity), source_id, row.organization_id, actor)
            source.email, source.phone, source.phone_country_code = row.email, row.phone, row.phone_country_code
            if link.account_id:
                source.name = row.full_name
            else:
                source.full_name, source.first_name, source.last_name = row.full_name, row.first_name, row.last_name
                source.company_name = row.company_name
            source.updated_at, source.updated_by_user_id = row.updated_at, actor.id
    audit(db, actor, row, "CONTACT_EDIT", before, serialize(row))
    save_directory_channels(db, actor, row, data, data.version)
    db.commit()
    return serialize(row)


def save_directory_channels(db, actor, row, data, initial_version=None):
    from app.shared.master_data import capture_options, persist_capture_channels, save_roles
    if data.roles is not None:
        save_roles(db, actor, row, "contact", data.roles)
    options = capture_options({"communication_channels": data.communication_channels, "communication_version": data.communication_version, "confirmShared": data.confirmShared, "sharedReason": data.sharedReason})
    persist_capture_channels(db, actor, row, options, initial_version)


class Bulk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[int] = Field(min_length=1, max_length=100)
    action: Literal["trash", "restore", "tag", "status"]
    tag: str = Field("", max_length=40)
    status: Literal["Active", "Inactive"] = "Active"


@router.post("/bulk")
def bulk(data: Bulk, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed(actor, "manage")
    ids = sorted(set(data.ids))
    rows = [get_contact(db, actor, ident, deleted=data.action == "restore", lock=True) for ident in ids]
    if data.action == "tag" and (not data.tag.strip() or "," in data.tag or data.tag.strip().casefold() in IDENTITY_TAGS):
        raise HTTPException(422, "Choose a business relationship tag")
    for row in rows:
        before = serialize(row)
        if data.action == "restore":
            from app.apps.crm.models import CRMActivity
            merged = db.query(CRMActivity).filter(CRMActivity.organization_id == row.organization_id, CRMActivity.entity_type == "contact", CRMActivity.entity_id == row.id, CRMActivity.activity_type == "duplicate_merge").all()
            if any((x.metadata_json or {}).get("loserId") == row.id for x in merged):
                raise HTTPException(409, "Merged contacts cannot be restored; use the surviving contact")
            if row.company_id:
                core()._assert_record_visible(db, core()._get_resource("companies"), row.company_id, row.organization_id, actor)
            row.deleted_at = None
        elif data.action == "trash":
            # This archives only the directory card. Source leads, transactions,
            # employees and login accounts remain intact.
            row.deleted_at = datetime.now(timezone.utc)
        elif data.action == "tag":
            if len(",".join(set(tags(row)) | {data.tag.strip()})) > 500:
                raise HTTPException(422, "Contact has too many tags")
            add_tags(row, data.tag.strip())
        else:
            row.status = data.status
        row.updated_at = datetime.now(timezone.utc)
        audit(db, actor, row, "CONTACT_" + data.action.upper(), before, serialize(row))
    db.commit()
    return {"updated": len(rows)}


@router.get("/{ident}")
def detail(ident: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = get_contact(db, actor, ident)
    crm = core()
    # Do not reuse legacy unfiltered relationship expansion: each related
    # resource needs both its own permission and its own record visibility.
    related = {"related": {}, "timeline": []}
    for entity in ["deals", "quotations", "activities", "notes", "tasks", "calls", "emails", "meetings"]:
        try:
            crm._assert_entity_permission(entity, actor, "view")
            resource = crm._get_resource(entity)
            model = resource.model
            field = getattr(model, "contact_id", None)
            if field is None:
                continue
            q = crm._apply_record_visibility(crm._base_query(db, resource, row.organization_id), resource, actor, db)
            related["related"][entity] = [crm._serialize(x) for x in q.filter(field == ident).order_by(model.id.desc()).limit(50)]
        except HTTPException:
            continue
    from app.apps.crm.models import CRMTimelineEvent
    related["timeline"] = [{"id": x.id, "title": x.title, "occurredAt": x.occurred_at, "type": x.event_type} for x in db.query(CRMTimelineEvent).filter(CRMTimelineEvent.organization_id == row.organization_id, CRMTimelineEvent.record_type.in_(["contact", "contacts"]), CRMTimelineEvent.record_id == ident).order_by(CRMTimelineEvent.occurred_at.desc()).limit(50)]
    from app.module_registry import is_app_enabled
    from app.access.catalog import permission_names
    permissions = permission_names(actor)
    if is_app_enabled("srm"):
        from app.apps.srm.models import SRMSalesOrder, SRMInvoice
        from app.apps.srm.access import sales_order_query, SRM_VIEW_PERMISSIONS, SRM_INVOICE_PERMISSIONS
        from app.apps.srm.services.commercial import invoice_query
        if actor.is_superuser or permissions.intersection(SRM_VIEW_PERMISSIONS):
            orders = sales_order_query(db, actor).filter(or_(SRMSalesOrder.crm_contact_id == ident, SRMSalesOrder.customer_id == row.company_id if row.company_id else False)).order_by(SRMSalesOrder.id.desc()).limit(30).all()
            related["related"]["sales orders"] = [{"id": x.id, "name": x.title, "status": x.status, "url": f"/srm/sales-orders/{x.id}"} for x in orders]
        if row.company_id and (actor.is_superuser or permissions.intersection(SRM_INVOICE_PERMISSIONS)):
            invoices = invoice_query(db, actor).filter(SRMInvoice.customer_id == row.company_id).order_by(SRMInvoice.id.desc()).limit(30).all()
            related["related"]["invoices"] = [{"id": x.id, "name": x.invoice_number, "status": x.status, "url": f"/srm/invoices/{x.id}"} for x in invoices]
    if is_app_enabled("project_management") and is_app_enabled("srm"):
        from app.apps.project_management.models import PMSProject
        from app.apps.project_management.access import accessible_project_query
        from app.apps.srm.commercial_models import ProjectCommercial
        grant = (getattr(actor, "_suite_grants", None) or {}).get("project_management")
        if actor.is_superuser or any(x.startswith("pms_") for x in permissions) or grant and grant.get("enabled"):
            projects = accessible_project_query(db, actor).filter(PMSProject.id.in_(select(ProjectCommercial.project_id).where(or_(ProjectCommercial.contact_id == ident, ProjectCommercial.customer_id == row.company_id if row.company_id else False)))).order_by(PMSProject.id.desc()).limit(30).all()
            related["related"]["projects"] = [{"id": x.id, "name": x.name, "status": x.status, "url": f"/pms/projects/{x.id}"} for x in projects]
    # Only accessible business source records are shown. Never expand linked
    # employees, login identities, role assignments or private CommonProfile.
    lead_resource = crm._get_resource("leads")
    try:
        crm._assert_entity_permission("leads", actor, "view")
        leads = crm._apply_record_visibility(crm._base_query(db, lead_resource, row.organization_id), lead_resource, actor, db).filter(
            CRMLead.id.in_(select(ContactIdentityLink.lead_id).where(ContactIdentityLink.contact_id == ident))).all()
    except HTTPException:
        leads = []
    return {**serialize(row), "leads": [{"id": x.id, "name": x.full_name, "status": x.status, "converted": x.is_converted} for x in leads], "related": related}


@router.get("/{ident}/duplicates")
def duplicates(ident: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    row = get_contact(db, actor, ident)
    clauses = []
    if row.email:
        clauses.append(func.lower(func.trim(CRMContact.email)) == row.email.strip().lower())
    if row.phone:
        normalized = CRMContact.phone
        for token in [" ", "-", "(", ")", "+"]:
            normalized = func.replace(normalized, token, "")
        phone = "".join(x for x in row.phone if x.isdigit())
        clauses.append(and_(normalized == phone, CRMContact.phone_country_code == row.phone_country_code))
    return {"items": [serialize(x) for x in base(db, actor).filter(CRMContact.id != ident, or_(*clauses)).limit(30)] if clauses else []}


class Convert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leadId: int
    existingContactId: int | None = None
    customerType: Literal["Individual", "Business"] = "Individual"


@router.post("/convert")
def convert(data: Convert, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed(actor, "manage")
    crm = core()
    crm._assert_entity_permission("leads", actor, "manage")
    crm._assert_record_visible(db, crm._get_resource("leads"), data.leadId, crm._organization_id(db, actor), actor)
    lead = crm._get_record(db, crm._get_resource("leads"), data.leadId, crm._organization_id(db, actor))
    if lead.is_converted:
        raise HTTPException(409, "Lead is already converted")
    link = db.query(ContactIdentityLink).filter(ContactIdentityLink.lead_id == lead.id).first()
    if link and data.existingContactId and data.existingContactId != link.contact_id:
        raise HTTPException(409, "Merge the duplicate contact identities before converting this lead")
    contact_id = data.existingContactId or (link.contact_id if link else None)
    if contact_id:
        get_contact(db, actor, contact_id)
    # Existing core checks qualification, scope, locking and audit. No history is moved/deleted.
    if data.customerType == "Business" and not lead.company_name:
        raise HTTPException(422, "Add the business name to the lead before converting it as a business customer")
    result = crm.convert_lead(lead.id, crm.CRMLeadConvertPayload(customerType=data.customerType, createContact=True, createCompany=True, companyName=lead.company_name if data.customerType == "Business" else lead.full_name, createDeal=False, existingContactId=contact_id), db, actor)
    return result


class Correction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/leads/{ident}/correct-conversion")
def correct_conversion(ident: int, data: Correction, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    allowed(actor, "manage")
    crm = core()
    crm._assert_entity_permission("leads", actor, "manage")
    from app.module_registry import is_app_enabled
    if is_app_enabled("srm"):
        from app.apps.srm.services.commercial import lock_tenant
        lock_tenant(db, actor)
    company_id = crm._organization_id(db, actor)
    crm._assert_record_visible(db, crm._get_resource("leads"), ident, company_id, actor)
    lead = db.query(CRMLead).filter(CRMLead.id == ident, CRMLead.organization_id == company_id).with_for_update().one()
    if not lead.is_converted:
        raise HTTPException(409, "This lead is not currently converted")
    contact = get_contact(db, actor, lead.converted_contact_id, lock=True) if lead.converted_contact_id else None
    # A correction never rewrites completed sales, payroll, invoices or projects.
    # All real FKs are examined through the existing tenant/branch guards.
    from app.db.base_class import Base
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if not (table.name.startswith(("srm_", "fam_", "business_", "pms_")) or table.name in {"crm_deals", "crm_quotations"}):
            continue
        model = mapper.class_
        for column in table.c:
            legacy_key = contact.id if contact and column.name == "crm_contact_id" else lead.converted_company_id if column.name in {"crm_company_id", "customer_id"} else None
            if legacy_key is not None and db.connection().execute(select(column).where(column == legacy_key).limit(1)).first():
                raise HTTPException(409, "Conversion is referenced by business transactions. Correct it through the authorized transaction workflow.")
            for fk in column.foreign_keys:
                key = contact.id if contact and fk.target_fullname == "crm_contacts.id" else lead.converted_company_id if fk.target_fullname == "crm_companies.id" else None
                # Integrity checks must see references in other branches too.
                # Fetch existence only, never any transaction fields.
                if key is not None and db.connection().execute(select(column).where(column == key).limit(1)).first():
                    raise HTTPException(409, "Conversion is referenced by business transactions. Correct it through the authorized transaction workflow.")
    log = db.query(CRMLeadConversionLog).filter(CRMLeadConversionLog.organization_id == company_id, CRMLeadConversionLog.lead_id == ident, CRMLeadConversionLog.conversion_status == "completed").order_by(CRMLeadConversionLog.id.desc()).with_for_update().first()
    if not log:
        raise HTTPException(409, "Conversion audit evidence is required before correction")
    before = {"isConverted": True, "contactId": lead.converted_contact_id, "companyId": lead.converted_company_id}
    lead.is_converted, lead.status = False, "Qualified"
    lead.updated_by_user_id, lead.updated_at = actor.id, datetime.now(timezone.utc)
    # Keep original conversion IDs/timestamps as provenance. No record is deleted.
    log.conversion_status = "corrected"
    log.metadata_json = {**(log.metadata_json or {}), "correctionReason": data.reason, "correctedBy": actor.id, "correctedAt": datetime.now(timezone.utc).isoformat()}
    if contact and not db.query(CRMLead).filter(CRMLead.converted_contact_id == contact.id, CRMLead.id != ident, CRMLead.is_converted.is_(True)).first():
        metadata = log.metadata_json or {}
        contact.lifecycle_stage = metadata.get("contactPreviousLifecycle") or "Lead"
        previous = set((metadata.get("contactPreviousTags") or "").split(","))
        contact.tags_text = ",".join(sorted(x for x in (set(tags(contact)) - {"Customer"}) | previous if x))
        contact.updated_at = datetime.now(timezone.utc)
    if lead.converted_company_id and not db.query(CRMLead).filter(CRMLead.converted_company_id == lead.converted_company_id, CRMLead.id != ident, CRMLead.is_converted.is_(True)).first():
        account = db.get(CRMCompany, lead.converted_company_id)
        if account:
            account.account_type = (log.metadata_json or {}).get("companyPreviousType") or "Prospect"
    audit(db, actor, contact or lead, "CONTACT_CONVERSION_CORRECTED", before, {"reason": data.reason, "leadId": ident})
    db.commit()
    return {"leadId": ident, "status": "Qualified", "historyPreserved": True}


@router.delete("/{ident}/permanent")
def permanently_delete(ident: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    if not actor.is_superuser:
        raise HTTPException(403, "Permanent deletion requires a Super Admin")
    from app.module_registry import is_app_enabled
    if is_app_enabled("srm"):
        from app.apps.srm.services.commercial import lock_tenant
        lock_tenant(db, actor)
    row = get_contact(db, actor, ident, deleted=True, lock=True)
    from app.db.base_class import Base
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if mapper.local_table.name in {"suite_contact_channels", "suite_business_relationships", "suite_contact_birthdays", "crm_contact_financial_profiles"}:
            # Owned profile fields are deleted with an unused identity. They are
            # not transaction/history references that require retention.
            continue
        for column in mapper.local_table.c:
            if column.name == "crm_contact_id" or any(fk.target_fullname == "crm_contacts.id" for fk in column.foreign_keys):
                # A shared contact can be referenced outside the selected branch.
                # Do not let scoped ORM reads conceal a cascading-delete hazard.
                if db.connection().execute(select(column).where(column == ident).limit(1)).first():
                    raise HTTPException(409, "This contact has linked business records and must be retained")
        table = mapper.local_table
        if "audit" not in table.name:
            for type_column, id_column in [("entity_type", "entity_id"), ("record_type", "record_id"), ("related_type", "related_id"), ("entity", "record_id")]:
                if type_column in table.c and id_column in table.c:
                    if db.connection().execute(select(table.c[id_column]).where(table.c[type_column].in_(["contact", "contacts"]), table.c[id_column] == ident).limit(1)).first():
                        raise HTTPException(409, "Contacts with linked business history must be retained")
    # CRM polymorphic histories do not all have a direct FK.
    from app.apps.crm.models import CRMTimelineEvent, CRMActivity
    if db.connection().execute(select(CRMTimelineEvent.id).where(CRMTimelineEvent.record_type.in_(["contact", "contacts"]), CRMTimelineEvent.record_id == ident).limit(1)).first() or db.connection().execute(select(CRMActivity.id).where(CRMActivity.entity_type.in_(["contact", "contacts"]), CRMActivity.entity_id == ident).limit(1)).first():
        raise HTTPException(409, "Contacts with history must be retained in trash")
    audit(db, actor, row, "CONTACT_PERMANENT_DELETE", serialize(row))
    from app.shared.master_data_models import ContactChannel, BusinessRelationship, ContactBirthday
    from app.shared.master_data_models import GreetingReservation
    birthday_ids = select(ContactBirthday.id).where(ContactBirthday.contact_id == ident)
    if db.query(GreetingReservation.id).filter(GreetingReservation.birthday_id.in_(birthday_ids)).first():
        raise HTTPException(409, "Contacts with greeting history must be retained in trash")
    for extension in (ContactChannel, BusinessRelationship, ContactBirthday, ContactFinancialProfile):
        for owned in db.query(extension).filter(extension.contact_id == ident).all():
            db.delete(owned)
    db.flush()
    db.delete(row)
    db.commit()
    return {"deleted": ident}


@router.post("/backfill")
def backfill(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    # Bounded, resumable and scoped. HR/users explicitly excluded by policy.
    allowed(actor, "manage")
    crm = core()
    count = 0
    for kind, entity, model, field in [("lead", "leads", CRMLead, ContactIdentityLink.lead_id), ("account", "companies", CRMCompany, ContactIdentityLink.account_id)]:
        try:
            crm._assert_entity_permission(entity, actor, "view")
        except HTTPException:
            continue
        resource = crm._get_resource(entity)
        q = crm._apply_record_visibility(crm._base_query(db, resource, crm._organization_id(db, actor)), resource, actor, db)
        sources = q.filter(~exists(select(1).where(field == model.id))).order_by(model.id).limit(100).all()
        for source in sources:
            link_source(db, source, kind)
            count += 1
    db.commit()
    return {"linked": count, "hasMore": count >= 100}

from app.apps.crm.financial_data import router as financial_router
router.include_router(financial_router)
