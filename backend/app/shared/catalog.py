"""Shared catalog views over the existing Sales/POS product master."""
import csv
import io
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator
from sqlalchemy import func, or_, literal, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.access.catalog import permission_names
from app.models.user import User
from app.apps.crm.models import CRMProduct, CRMService
from app.apps.srm.models import SRMProduct
from app.apps.srm.services.commercial import tenant
from app.shared.catalog_models import CatalogDetails, CatalogLink

router = APIRouter(prefix="/catalog", tags=["Shared products & services"])
Kind = Literal["product", "service"]
Source = Literal["pms", "crm", "srm"]
Target = Literal["project", "lead", "contact", "customer", "account", "deal"]
CENT = Decimal("0.01")


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(ge=0, le=9999999999, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    interval: Literal["once", "day", "week", "month", "year"] = "once"


from app.shared.follow_ups import Schedule

class ItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    follow_up: Schedule | None = None
    kind: Kind
    name: str = Field(min_length=1, max_length=180)
    code: str = Field(min_length=1, max_length=80)
    category: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=50000)
    price: Decimal = Field(default=0, ge=0, le=9999999999, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    tax: Decimal = Field(default=0, ge=0, le=100, decimal_places=2)
    unit: str = Field(default="unit", min_length=1, max_length=40)
    barcode: str | None = Field(default=None, max_length=120)
    hsn_code: str | None = Field(default=None, max_length=30)
    cost: Decimal | None = Field(default=None, ge=0, le=9999999999, decimal_places=2)
    mrp: Decimal | None = Field(default=None, ge=0, le=9999999999, decimal_places=2)
    reorder_level: Decimal | None = Field(default=None, ge=0, le=9999999999, decimal_places=3)
    track_inventory: bool | None = None
    status: Literal["Active", "Archived"] = "Active"
    workspace_id: int | None = Field(default=None, gt=0)
    images: list[str] = Field(default_factory=list, max_length=20)
    custom_fields: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=100)
    pricing_options: list[Price] = Field(default_factory=list, max_length=30)
    version: int | None = Field(default=None, ge=0)

    @field_validator("images")
    @classmethod
    def image_urls(cls, values):
        if any(len(v) > 500 or not v.startswith(("https://", "http://", "/uploads/", "/api/")) for v in values):
            raise ValueError("Images must use an HTTP URL or an uploaded asset path")
        return values

    @field_validator("pricing_options")
    @classmethod
    def unique_prices(cls, values):
        if len({p.id for p in values}) != len(values):
            raise ValueError("Pricing option IDs must be unique")
        return values


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    item_id: int = Field(gt=0)
    pricing_id: str | None = Field(default=None, max_length=80)
    quantity: Decimal = Field(default=1, gt=0, le=1000000, decimal_places=4)
    unit_price: Decimal | None = Field(default=None, ge=0, le=9999999999, decimal_places=2)
    discount: Decimal = Field(default=0, ge=0, le=100, decimal_places=2)


class LinesInput(BaseModel):
    lines: list[Line] = Field(max_length=100)


def authorize(user, source, kind="product", write=False, db=None):
    from app.module_registry import is_app_enabled
    module = "project_management" if source == "pms" else source
    if not is_app_enabled(module):
        raise HTTPException(404, "Application is unavailable")
    grants = getattr(user, "_suite_grants", None)
    if grants is not None and not user.is_superuser and not (grants.get(module) or {}).get("enabled"):
        raise HTTPException(403, "Application access is required")
    if source == "srm":
        if not user.is_superuser and not permission_names(user).intersection({"srm_manage", "srm_admin"} if write else {"srm_view", "srm_manage", "srm_admin"}):
            raise HTTPException(403, "Sales catalog permission is required")
    elif source == "crm":
        from app.apps.crm.api.router import _assert_entity_permission
        _assert_entity_permission("products" if kind == "product" else "services", user, "manage" if write else "view")
    elif not user.is_superuser:
        names = permission_names(user)
        required = {"pms_admin", "pms_manage_projects"} if write else {"pms_view", "pms_admin", "pms_manage_projects", "pms_manage_tasks", "pms_time_manage"}
        if not names.intersection(required):
            raise HTTPException(403, "Catalog management permission is required" if write else "PMS access is required")


def workspace_access(db, user, workspace_id, write=False):
    if workspace_id:
        from app.apps.project_management.workspaces import workspace_member
        workspace, _ = workspace_member(db, workspace_id, user, write)
        if (workspace.organization_id or 1) != tenant(user):
            raise HTTPException(404, "Workspace not found in your organization")


def metadata(db, kind, ident):
    return db.query(CatalogDetails).filter(getattr(CatalogDetails, kind + "_id") == ident).first()


def restrict_workspaces(query, model, db, user):
    # Legacy CRM master rows are retained as migration history.
    # Shared catalog IDs now refer to the existing POS master exclusively.
    if model is not SRMProduct:
        return query
    from app.apps.project_management.models import PMSWorkspaceMember, PMSWorkspace
    from app.apps.project_management.people_management import organization_admin
    restricted = select(func.coalesce(CatalogDetails.product_id, CatalogDetails.service_id)).where(CatalogDetails.workspace_id.is_not(None))
    if not user.is_superuser and not organization_admin(user):
        allowed = select(PMSWorkspaceMember.workspace_id).join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceMember.workspace_id).where(PMSWorkspaceMember.user_id == user.id, func.coalesce(PMSWorkspace.organization_id, 1) == tenant(user))
        restricted = restricted.where(CatalogDetails.workspace_id.notin_(allowed))
        return query.filter(model.id.notin_(restricted))
    return query


def item_record(db, user, source, kind, ident, write=False, archived=True):
    authorize(user, source, kind, write, db=db)
    model = SRMProduct
    row = db.query(model).filter(model.id == ident, func.coalesce(model.organization_id, 1) == tenant(user), model.deleted_at.is_(None)).with_for_update().first() if write else db.query(model).filter(model.id == ident, func.coalesce(model.organization_id, 1) == tenant(user), model.deleted_at.is_(None)).first()
    if not row or ("service" if row.product_type == "service" else "product") != kind:
        raise HTTPException(404, "Catalog item not found")
    if source == "crm":
        from app.apps.crm.api.router import _assert_record_visible
        _assert_record_visible(db, catalog_resource(), ident, tenant(user), user)
    detail = metadata(db, kind, ident)
    workspace_access(db, user, detail.workspace_id if detail else None, write)
    if not archived and not row.active:
        raise HTTPException(422, "Archived items cannot be added to records")
    return row, detail


def output(row, kind, detail):
    attributes = row.metadata_json or {}
    return {"follow_up": attributes.get("follow_up"), "id": row.id, "kind": kind, "name": row.item_name, "code": row.sku,
            "category": row.category_name or "", "description": row.description or "", "price": float(row.sales_rate or 0),
            "currency": attributes.get("currency", "INR"), "tax": float(row.gst_rate or 0), "unit": row.unit_code or "unit",
            "barcode": row.barcode or "", "hsn_code": row.hsn_code or "", "cost": float(row.purchase_rate or 0), "mrp": float(row.mrp or 0), "reorder_level": float(row.reorder_level or 0), "track_inventory": bool(row.track_inventory),
            "status": "Active" if row.active else "Archived", "workspace_id": detail.workspace_id if detail else None,
            "images": attributes.get("images", detail.images if detail else []), "custom_fields": detail.custom_fields if detail else {},
            "pricing_options": detail.pricing_options if detail else [], "version": detail.version if detail else 0}


def save_item(db, user, source, data, ident=None):
    authorize(user, source, data.kind, True, db=db)
    workspace_access(db, user, data.workspace_id, True)
    model = SRMProduct
    if ident:
        row, detail = item_record(db, user, source, data.kind, ident, True)
        if data.version is not None and data.version != (detail.version if detail else 0):
            raise HTTPException(409, "This item changed. Reload it before saving.")
    else:
        row, detail = model(organization_id=tenant(user), created_by=user.id, product_type="service" if data.kind == "service" else "stock", track_inventory=data.kind != "service"), None
        db.add(row)
    row.item_name, row.category_name, row.description = data.name, data.category, data.description
    row.gst_rate, row.active = data.tax, data.status == "Active"
    row.sku, row.sales_rate, row.unit_code = data.code, data.price, data.unit
    for field, attribute in (("barcode", "barcode"), ("hsn_code", "hsn_code"), ("cost", "purchase_rate"), ("mrp", "mrp"), ("reorder_level", "reorder_level"), ("track_inventory", "track_inventory")):
        value = getattr(data, field)
        if value is not None:
            setattr(row, attribute, (value or None) if field in {"barcode", "hsn_code"} else value)
    if data.kind == "service":
        row.track_inventory = False
    row.metadata_json = {**(row.metadata_json or {}), "currency": data.currency, "images": data.images, **({"follow_up": data.follow_up.model_dump(mode="json")} if data.follow_up is not None else {})}
    db.flush()
    if detail is None:
        detail = CatalogDetails(organization_id=tenant(user), **{data.kind + "_id": row.id}, version=0)
        db.add(detail)
    detail.workspace_id, detail.unit, detail.images = data.workspace_id, data.unit, data.images
    detail.custom_fields = data.custom_fields
    detail.pricing_options = [p.model_dump(mode="json") for p in data.pricing_options]
    detail.version += 1
    from app.apps.crm.api.router import _create_crm_audit_log
    _create_crm_audit_log(db, user_id=user.id, entity_type="catalog", entity_id=row.id, action="UPDATE" if ident else "CREATE", description=f"Shared {data.kind} {row.item_name}")
    db.flush()
    return output(row, data.kind, detail)


def catalog_resource():
    from app.apps.crm.api.router import Resource
    return Resource(SRMProduct, required=("item_name", "sku"), search=("item_name", "sku"), owner_field="created_by")


def legacy_output(item, db=None):
    """Keep existing CRM selectors on the same POS records without another master."""
    row = db.get(SRMProduct, item["id"]) if db else None
    cost = float(row.purchase_rate or 0) if row else 0
    return {**item, "sku": item["code"], "product_code": item["code"], "service_code": item["code"],
            "list_price": item["price"], "unit_price": item["price"], "default_rate": item["price"],
            "tax_rate": item["tax"], "unit_of_measure": item["unit"],
            "image_url": item["images"][0] if item["images"] else None, "active": item["status"] == "Active",
            "productCode": item["code"], "serviceCode": item["code"], "listPrice": item["price"], "unitPrice": item["price"], "defaultRate": item["price"],
            "cost_price": cost, "costPrice": cost, "default_cost": cost, "defaultCost": cost, "taxRate": item["tax"], "unitOfMeasure": item["unit"], "billing_type": row.billing_type if row else "fixed", "billingType": row.billing_type if row else "fixed"}


def save_legacy(db, user, entity, values, ident=None, persist=True):
    kind = "service" if entity == "services" else "product"
    data = get_item(kind, ident, "crm", db, user) if ident else {"kind": kind, "name": "", "code": f"{kind.upper()}-{uuid4().hex[:12]}"}
    data.pop("id", None)
    aliases = {"sku": "code", "product_code": "code", "service_code": "code", "list_price": "price", "unit_price": "price", "default_rate": "price", "tax_rate": "tax", "unit_of_measure": "unit"}
    for key, value in values.items():
        field = aliases.get(key, key)
        if field in ItemInput.model_fields:
            data[field] = value
    if "active" in values:
        data["status"] = "Active" if values["active"] else "Archived"
    if "image_url" in values:
        data["images"] = [values["image_url"]] if values["image_url"] else []
    if data.get("status") in {"Inactive", "Unavailable"}:
        data["status"] = "Archived"
    try:
        payload = ItemInput.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(422, str(exc))
    result = save_item(db, user, "crm", payload, ident)
    row = db.get(SRMProduct, result["id"])
    if "cost_price" in values or "default_cost" in values:
        row.purchase_rate = values.get("cost_price", values.get("default_cost", 0))
    if "billing_type" in values:
        row.metadata_json = {**(row.metadata_json or {}), "billing_type": values["billing_type"]}
    if persist:
        commit(db)
    return legacy_output(result, db)


@router.post("/images", status_code=201)
async def upload_image(source: Source = "crm", kind: Kind = "product", file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    authorize(user, source, kind, True, db=db)
    from pathlib import Path
    from PIL import Image, UnidentifiedImageError
    from app.core.config import settings
    from app.core.storage import persist_file
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Images must be 2 MB or smaller")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 16000000:
                raise HTTPException(422, "Use PNG, JPEG or WebP under 16 megapixels")
            image.load()
            image.thumbnail((1600, 1600))
            buffer = io.BytesIO()
            image.convert("RGBA").save(buffer, format="PNG")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Invalid image file")
    relative = f"catalog/{tenant(user)}/{uuid4().hex}.png"
    path = Path(settings.UPLOAD_DIR) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(buffer.getvalue())
        persist_file(str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"url": f"/uploads/{relative}"}


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That SKU or code already exists in this organization")


@router.get("/items")
def list_items(source: Source = "crm", kind: Kind | None = None, search: str = Query("", max_length=180), category: str = "", status: Literal["all", "Active", "Archived"] = "Active", workspace_id: int | None = None, sort: Literal["name", "price", "category", "code"] = "name", direction: Literal["asc", "desc"] = "asc", page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.project_management.models import PMSWorkspaceMember, PMSWorkspace
    from app.apps.project_management.people_management import organization_admin
    if workspace_id:
        workspace_access(db, user, workspace_id)
    queries = []
    permissions = {}
    for selected in ([kind] if kind else ["product", "service"]):
        try:
            authorize(user, source, selected, db=db)
        except HTTPException as exc:
            if kind or exc.status_code != 403:
                raise
            continue
        try:
            authorize(user, source, selected, True, db=db)
            permissions[selected] = True
        except HTTPException:
            permissions[selected] = False
        model = SRMProduct
        price = func.coalesce(model.sales_rate, 0)
        code = model.sku
        query = select(literal(selected).label("kind"), model.id.label("id"), model.item_name.label("name"), price.label("price"), model.category_name.label("category"), code.label("code")).outerjoin(CatalogDetails, getattr(CatalogDetails, selected + "_id") == model.id).where(func.coalesce(model.organization_id, 1) == tenant(user), model.deleted_at.is_(None))
        query = query.where(model.product_type == "service" if selected == "service" else func.coalesce(model.product_type, "stock") != "service")
        if not user.is_superuser and not organization_admin(user):
            visible = select(PMSWorkspaceMember.workspace_id).join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceMember.workspace_id).where(PMSWorkspaceMember.user_id == user.id, func.coalesce(PMSWorkspace.organization_id, 1) == tenant(user))
            query = query.where(or_(CatalogDetails.workspace_id.is_(None), CatalogDetails.workspace_id.in_(visible)))
        if source == "crm":
            from app.apps.crm.api.router import _apply_record_visibility
            visible_items = _apply_record_visibility(db.query(model), catalog_resource(), user, db).with_entities(model.id).subquery()
            query = query.where(model.id.in_(select(visible_items.c.id)))
        if status != "all": query = query.where(model.active == (status == "Active"))
        if category: query = query.where(model.category_name == category)
        if workspace_id: query = query.where(CatalogDetails.workspace_id == workspace_id)
        if search: query = query.where(or_(model.item_name.ilike(f"%{search}%"), code.ilike(f"%{search}%"), model.description.ilike(f"%{search}%")))
        queries.append(query)
    if not queries:
        raise HTTPException(403, "Catalog access is required")
    combined = union_all(*queries).subquery()
    total = db.scalar(select(func.count()).select_from(combined))
    ordering = combined.c[sort].asc() if direction == "asc" else combined.c[sort].desc()
    rows = db.execute(select(combined).order_by(ordering, combined.c.kind, combined.c.id).offset((page - 1) * per_page).limit(per_page)).mappings().all()
    items = []
    for selected in ("product", "service"):
        ids = [r["id"] for r in rows if r["kind"] == selected]
        if not ids: continue
        model = SRMProduct
        details = {getattr(d, selected + "_id"): d for d in db.query(CatalogDetails).filter(getattr(CatalogDetails, selected + "_id").in_(ids)).all()}
        items.extend(output(row, selected, details.get(row.id)) for row in db.query(model).filter(model.id.in_(ids)).all())
    indexed = {(v["kind"], v["id"]): v for v in items}
    return {"items": [indexed[(r["kind"], r["id"])] for r in rows], "total": total, "pages": (total + per_page - 1) // per_page, "permissions": permissions}


@router.post("/items", status_code=201)
def create_item(data: ItemInput, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = save_item(db, user, source, data)
        commit(db)
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That SKU or code already exists in this organization")


@router.get("/items/{kind}/{ident}")
def get_item(kind: Kind, ident: int, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return output(*item_output_args(db, user, source, kind, ident))


def item_output_args(db, user, source, kind, ident):
    row, detail = item_record(db, user, source, kind, ident)
    return row, kind, detail


@router.put("/items/{kind}/{ident}")
def update_item(kind: Kind, ident: int, data: ItemInput, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.kind != kind:
        raise HTTPException(422, "An item's type cannot be changed")
    try:
        result = save_item(db, user, source, data, ident)
        commit(db)
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That SKU or code already exists in this organization")


@router.post("/items/{kind}/{ident}/duplicate", status_code=201)
def duplicate(kind: Kind, ident: int, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = get_item(kind, ident, source, db, user)
    data.pop("id"); data.pop("version")
    data.update(name=(data["name"][:170] + " (copy)"), code=data["code"][:65] + "-" + uuid4().hex[:8])
    return create_item(ItemInput.model_validate(data), source, db, user)


@router.post("/items/{kind}/{ident}/archive")
def archive(kind: Kind, ident: int, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row, detail = item_record(db, user, source, kind, ident, True)
    data = output(row, kind, detail); data.pop("id"); data["status"] = "Archived"
    return update_item(kind, ident, ItemInput.model_validate(data), source, db, user)


@router.get("/export")
def export_items(source: Source = "crm", format: Literal["json", "csv"] = "json", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items, page = [], 1
    while True:
        result = list_items(source=source, kind=None, search="", category="", status="all", workspace_id=None, sort="name", direction="asc", page=page, per_page=100, db=db, user=user)
        items.extend({k: v for k, v in item.items() if k not in {"id", "version"}} for item in result["items"])
        if page >= result["pages"]: break
        page += 1
    if format == "json":
        return Response(json.dumps(items), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="products-services.json"'})
    stream = io.StringIO(); fields = list(ItemInput.model_fields); fields.remove("version")
    writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
    for item in items:
        values = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in item.items()}
        # CSV spreadsheet formula protection applies only to free text columns.
        for key in ("name", "code", "category", "description", "unit"):
            if str(values.get(key, "")).startswith(("=", "+", "-", "@", "\t", "\r")): values[key] = "'" + values[key]
        writer.writerow(values)
    return Response(stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="products-services.csv"'})


@router.post("/import")
def import_items(file: UploadFile = File(...), source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    raw = file.file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024: raise HTTPException(413, "Import files must be under 2 MB")
    try:
        text = raw.decode("utf-8-sig")
        rows = json.loads(text) if (file.filename or "").lower().endswith(".json") else list(csv.DictReader(io.StringIO(text)))
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500: raise ValueError("Import 1 to 500 items at a time")
        inputs = []
        for row in rows:
            for key in ("images", "custom_fields", "pricing_options"):
                if isinstance(row.get(key), str): row[key] = json.loads(row[key]) if row[key] else ([] if key != "custom_fields" else {})
            if row.get("workspace_id") == "": row["workspace_id"] = None
            inputs.append(ItemInput.model_validate(row))
        with db.begin_nested():
            results = [save_item(db, user, source, data) for data in inputs]
        commit(db)
        return {"created": len(results), "items": results}
    except (ValueError, TypeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(422, f"Invalid import: {str(exc)[:300]}")
    except IntegrityError:
        raise HTTPException(409, "Import contains a duplicate SKU or code; no items were imported")


def target_record(db, user, source, target, ident, write=False):
    if target == "project":
        if source != "pms": raise HTTPException(403, "Use PMS to manage project associations")
        from app.apps.project_management.access import get_project_for_action
        return get_project_for_action(db, ident, user, "edit_project" if write else "browse")
    if source != "crm": raise HTTPException(403, "CRM access is required for customer records")
    from app.apps.crm.api.router import _get_record, _get_resource, _assert_entity_permission, _assert_record_visible, _assert_write_scope
    entity = {"lead": "leads", "contact": "contacts", "customer": "companies", "account": "accounts", "deal": "deals"}[target]
    _assert_entity_permission(entity, user, "manage" if write else "view")
    resource = _get_resource(entity)
    row = _get_record(db, resource, ident, tenant(user))
    _assert_record_visible(db, resource, ident, tenant(user), user)
    if write: _assert_write_scope(resource, {resource.owner_field: getattr(row, resource.owner_field, None)} if resource.owner_field else {}, user, db)
    return row


def line_output(item, line, tax):
    price = Decimal(str(line.unit_price if line.unit_price is not None else item["price"]))
    subtotal = (price * line.quantity * (1 - line.discount / 100)).quantize(CENT, rounding=ROUND_HALF_UP)
    tax_amount = (subtotal * tax / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"kind": line.kind, "item_id": line.item_id, "name": item["name"], "pricing_id": line.pricing_id, "quantity": float(line.quantity), "unit_price": float(price), "discount": float(line.discount), "currency": item["currency"], "tax_rate": float(tax), "subtotal": float(subtotal), "tax_amount": float(tax_amount), "total_amount": float(subtotal + tax_amount), "status": item["status"]}


@router.get("/links/{target}/{ident}")
def get_links(target: Target, ident: int, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = target_record(db, user, source, target, ident)
    can_edit = True
    try:
        target_record(db, user, source, target, ident, True)
        grant = (getattr(user, "_suite_grants", None) or {}).get("project_management" if source == "pms" else "crm")
        if grant is not None and "edit" not in grant.get("actions", []): can_edit = False
    except HTTPException:
        can_edit = False
    if target == "deal":
        from app.apps.crm.api.router import _deal_products_for
        return {"lines": _deal_products_for(db, ident, tenant(user)), "currency": record.currency, "total": float(record.amount or 0), "can_edit": can_edit}
    rows = db.query(CatalogLink).filter_by(organization_id=tenant(user), target_type=target, target_id=ident).all()
    lines = []
    for row in rows:
        kind = "product" if row.product_id else "service"
        item, detail = item_record(db, user, source, kind, row.product_id or row.service_id)
        data = output(item, kind, detail); data["currency"] = row.currency
        lines.append(line_output(data, Line(kind=kind, item_id=item.id, pricing_id=row.pricing_id, quantity=row.quantity, unit_price=row.unit_price, discount=row.discount), row.tax_rate))
    totals = {}
    for line in lines: totals[line["currency"]] = round(totals.get(line["currency"], 0) + line["total_amount"], 2)
    return {"lines": lines, "totals": totals, "can_edit": can_edit}


def save_links(target, ident, data, source, db, user, persist=True):
    record = target_record(db, user, source, target, ident, True)
    db.query(type(record)).filter_by(id=record.id).with_for_update().one()
    previous = get_links(target, ident, source, db, user)["lines"]
    existing = {(line["kind"], line["item_id"]) for line in previous}
    normalized = []
    for line in data.lines:
        item, detail = item_record(db, user, source, line.kind, line.item_id, archived=(line.kind, line.item_id) in existing)
        values = output(item, line.kind, detail)
        if line.pricing_id:
            price = next((p for p in values["pricing_options"] if p["id"] == line.pricing_id), None)
            if not price: raise HTTPException(422, "Pricing option no longer exists")
            values["currency"], values["price"] = price["currency"], price["amount"]
        normalized.append(line_output(values, line, Decimal(str(values["tax"]))))
    if target == "deal":
        from app.apps.crm.api.router import update_record, CRMRecordPayload
        lines = [{k: line[k] for k in ("kind", "item_id", "quantity", "unit_price", "discount", "pricing_id")} for line in normalized]
        if any(line["currency"] != record.currency for line in normalized): raise HTTPException(422, "All prices must match the deal currency")
        update_record("deals", ident, CRMRecordPayload.model_validate({"catalog_items": lines, **({"amount": 0} if not lines else {})}), db, user)
    else:
        db.query(CatalogLink).filter_by(organization_id=tenant(user), target_type=target, target_id=ident).delete()
        for line in normalized:
            db.add(CatalogLink(organization_id=tenant(user), target_type=target, target_id=ident, **{line["kind"] + "_id": line["item_id"]}, **{key: line[key] for key in ("pricing_id", "quantity", "unit_price", "discount", "tax_rate", "currency")}))
        from app.apps.crm.api.router import _create_crm_audit_log
        _create_crm_audit_log(db, user_id=user.id, entity_type="catalog_links", entity_id=ident, action="UPDATE", description=f"Updated {target} products/services")
        if persist: commit(db)
        else: db.flush()
    return get_links(target, ident, source, db, user)


@router.put("/links/{target}/{ident}")
def put_links(target: Target, ident: int, data: LinesInput, source: Source = "crm", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return save_links(target, ident, data, source, db, user)


def save_form_links(db, user, record, lines):
    if lines is None: return
    from app.apps.crm.models import CRMLead, CRMContact, CRMCompany, CRMAccount
    target = {CRMLead: "lead", CRMContact: "contact", CRMCompany: "customer", CRMAccount: "account"}.get(type(record))
    if not target: raise HTTPException(422, "Catalog associations are unavailable for this record type")
    try: payload = LinesInput.model_validate({"lines": lines})
    except ValidationError: raise HTTPException(422, "Invalid product/service lines")
    save_links(target, record.id, payload, "crm", db, user, persist=False)
