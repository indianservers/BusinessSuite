"""Safe structured template rendering, persistent designs and CRM mail merge."""
import html
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.srm.services.commercial import tenant
from app.apps.communication.models import CommunicationEmailTemplate
from .template_models import CRMVisualTemplate

router = APIRouter(prefix="/template-studio", tags=["CRM template studio"])
READ = RequirePermission("crm_view", "crm_manage", "crm_admin", "communication_view", "communication_templates_manage")
WRITE = RequirePermission("crm_manage", "crm_admin", "communication_templates_manage")
TOKEN = re.compile(r"\{\{\s*([a-z][a-z0-9_.]*)\s*\}\}")
# Label, token and example are deliberately kept together in the picker.
FIELDS = [
    ("Organization", "organization.name", "Company name", "Acme Studio"),
    ("Organization", "organization.address", "Company address", "24 Park Road, Bengaluru 560001"),
    ("Organization", "organization.email", "Company email", "accounts@example.com"),
    ("Organization", "organization.phone", "Company phone", "+91 98765 43210"),
    ("Organization", "organization.tax_id", "Company tax / GST number", "29ABCDE1234F1Z5"),
    ("Recipient", "name", "Recipient full name", "Ananya Rao"),
    ("Recipient", "first_name", "Recipient first name", "Ananya"),
    ("Recipient", "email", "Recipient email", "ananya@example.com"),
    ("Recipient", "phone", "Recipient phone", "+91 98765 12345"),
    ("Recipient", "company", "Recipient company", "Northstar Technologies"),
    ("Recipient", "address", "Billing / postal address", "18 Residency Road, Bengaluru 560025"),
    ("Document", "document.number", "Document reference", "INV-2026-0042"),
    ("Document", "document.date", "Issue date", "7 November 2026"),
    ("Document", "document.due_date", "Due / valid until date", "21 November 2026"),
    ("Document", "document.currency", "Currency code", "INR"),
    ("Document", "document.subtotal", "Subtotal", "25,000.00"),
    ("Document", "document.discount", "Discount", "0.00"),
    ("Document", "document.tax", "Tax amount", "4,500.00"),
    ("Document", "document.total", "Grand total", "29,500.00"),
    ("Document", "document.balance", "Balance due", "29,500.00"),
    ("Document", "document.terms", "Payment / document terms", "Payment due within 14 days of issue."),
    ("Sender", "sender", "Sender / signatory name", "Priya Sharma"),
    ("Sender", "sender_title", "Sender designation", "Customer Success Manager"),
    ("Sender", "sender_email", "Sender email", "priya@example.com"),
    ("Relationship", "product", "Product / service name", "Business Suite Professional"),
    ("Relationship", "deal.name", "Deal name", "Northstar annual subscription"),
    ("Relationship", "deal.amount", "Deal value", "25,000.00"),
    ("Relationship", "meeting.date", "Meeting date", "12 November 2026"),
    ("Relationship", "meeting.time", "Meeting time", "10:30 AM IST"),
    ("Relationship", "contract.start_date", "Agreement start date", "1 December 2026"),
    ("Relationship", "contract.end_date", "Agreement end date", "30 November 2027"),
]
SAMPLES = {key: sample for _, key, _, sample in FIELDS}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Block(Strict):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    type: Literal["heading", "text", "brand", "image", "button", "divider", "spacer", "items", "totals", "signature"]
    text: str = Field(default="", max_length=15000)
    url: str = Field(default="", max_length=2000)
    align: Literal["left", "center", "right"] = "left"
    size: int = Field(default=14, ge=10, le=64)
    color: str = Field(default="#243047", pattern=r"^#[0-9a-fA-F]{6}$")
    bold: bool = False
    padding: int = Field(default=12, ge=0, le=80)


class Design(Strict):
    blocks: list[Block] = Field(max_length=100)
    accent: str = Field(default="#6554c0", pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    font: Literal["Arial", "Georgia", "Verdana", "Times New Roman"] = "Arial"
    @model_validator(mode="after")
    def unique_blocks(self):
        if len({b.id for b in self.blocks}) != len(self.blocks):
            raise ValueError("Block identifiers must be unique")
        return self


class TemplateInput(Strict):
    name: str = Field(min_length=2, max_length=180)
    category: Literal["email", "inventory", "mail_merge"]
    document_type: Literal["email", "invoice", "quotation", "sales_order", "purchase_order", "letter", "agreement", "form", "label", "envelope"]
    module: Literal["lead", "contact", "account", "deal", "quotation"] = "contact"
    subject: str = Field(default="", max_length=240)
    folder: str = Field(default="General", min_length=1, max_length=100)
    status: Literal["draft", "ready"] = "draft"
    version: int = Field(default=1, ge=1)
    design: Design
    @model_validator(mode="after")
    def consistent_type(self):
        categories = {"email": {"email"}, "inventory": {"invoice", "quotation", "sales_order", "purchase_order"}, "mail_merge": {"letter", "agreement", "form", "label", "envelope"}}
        if self.document_type not in categories[self.category]:
            raise ValueError("Choose a document type belonging to this category")
        if self.status == "ready" and (not self.design.blocks or (self.category == "email" and not self.subject)):
            raise ValueError("Ready templates need content and email templates need a subject")
        return self


class Line(Strict):
    description: str = Field(max_length=500)
    quantity: str = Field(default="1", max_length=30)
    rate: str = Field(default="0.00", max_length=40)
    amount: str = Field(default="0.00", max_length=40)


class RenderInput(Strict):
    template: TemplateInput
    values: dict[str, str] = Field(default_factory=dict, max_length=100)
    lines: list[Line] = Field(default_factory=list, max_length=100)
    sample: bool = False


def safe_url(value, image=False):
    if not value:
        return ""
    if not re.match(r"^https://[^\s<>\"']+$", value, re.I) and not (not image and re.match(r"^mailto:[^\s<>\"']+@[^\s<>\"']+$", value, re.I)):
        raise HTTPException(422, "Use a valid HTTPS URL (or mailto link for buttons)")
    return html.escape(value, quote=True)


def render(data: RenderInput):
    t = data.template
    values = {**(SAMPLES if data.sample else {}), **data.values}
    if any(len(v) > 15000 for v in values.values()):
        raise HTTPException(422, "Placeholder values must be under 15,000 characters")
    unresolved = set()
    def merge(text):
        def replace(match):
            key = match.group(1)
            if key not in values or not values[key].strip():
                unresolved.add(key)
                return match.group(0)
            return values[key]
        # One pass only: values cannot introduce new merge expressions or HTML.
        return html.escape(TOKEN.sub(replace, text)).replace("\n", "<br>")
    blocks = []
    for b in t.design.blocks:
        style = f"padding:{b.padding}px 24px;text-align:{b.align};font-size:{b.size}px;color:{b.color};font-weight:{700 if b.bold else 400};line-height:1.6;overflow-wrap:anywhere;"
        content = merge(b.text)
        if b.type == "heading": content = f'<h1 style="margin:0;font-size:inherit;font-weight:700;color:inherit">{content}</h1>'
        elif b.type == "brand": content = f'<div style="font-weight:700;letter-spacing:1px;color:{t.design.accent}">{content}</div>'
        elif b.type == "divider": content = f'<hr style="border:0;border-top:1px solid {t.design.accent};margin:0">'
        elif b.type == "spacer": content = '<div style="height:24px"></div>'
        elif b.type == "image":
            url = safe_url(b.url, image=True)
            content = f'<img src="{url}" alt="{html.escape(b.text, quote=True)}" style="max-width:100%;max-height:240px;height:auto">' if url else '<div style="padding:30px;border:1px dashed #cbd5e1;color:#64748b">Add a logo or image · HTTPS image URL</div>'
        elif b.type == "button":
            url = safe_url(b.url)
            content = f'<a href="{url}" style="display:inline-block;background:{t.design.accent};color:#fff;text-decoration:none;padding:12px 24px;border-radius:6px">{content}</a>'
        elif b.type == "items":
            lines = data.lines or ([Line(description="Professional subscription", quantity="1", rate="25,000.00", amount="25,000.00")] if data.sample else [])
            rows = ''.join('<tr>'+''.join(f'<td style="padding:12px 8px;border-bottom:1px solid #e2e8f0;text-align:{"left" if i == 0 else "right"}">{html.escape(v)}</td>' for i, v in enumerate([line.description, line.quantity, line.rate, line.amount]))+'</tr>' for line in lines)
            if not lines: unresolved.add("document.items")
            content = f'<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="background:{t.design.accent};color:#fff">'+''.join(f'<th style="padding:10px 8px;text-align:{"left" if i == 0 else "right"}">{label}</th>' for i, label in enumerate(["Description", "Qty", "Rate", "Amount"]))+f'</tr></thead><tbody>{rows or "<tr><td colspan=\"4\" style=\"padding:16px\">{{document.items}}</td></tr>"}</tbody></table>'
        elif b.type == "totals":
            content = '<table style="width:65%;margin-left:auto;font-size:14px">'+''.join(f'<tr><td style="padding:5px">{label}</td><td style="text-align:right;padding:5px;font-weight:700">{merge("{{document."+key+"}}")}</td></tr>' for label, key in [("Subtotal", "subtotal"), ("Discount", "discount"), ("Tax", "tax"), ("Total", "total"), ("Balance due", "balance")])+'</table>'
        elif b.type == "signature": content = f'<div style="border-top:1px solid #cbd5e1;padding-top:12px;display:inline-block;min-width:180px">{content}</div>'
        blocks.append({"id": b.id, "html": f'<div style="{style}">{content}</div>'})
    subject = merge(t.subject)
    body = f'<div style="max-width:{640 if t.category == "email" else 794}px;margin:0 auto;background:{t.design.background};font-family:{t.design.font},serif;padding:28px 12px;box-sizing:border-box">'+''.join(b['html'] for b in blocks)+'</div>'
    document = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(t.name)+'</title><style>@page{size:A4;margin:12mm}body{margin:0;background:#fff}img{max-width:100%}tr{break-inside:avoid}@media print{a{color:inherit}}</style></head><body>'+body+'</body></html>'
    return {"html": document, "body": body, "blocks": blocks, "subject": html.unescape(subject), "unresolved": sorted(unresolved), "sample": data.sample}


def output(row):
    return {key: getattr(row, key) for key in ("id", "name", "category", "document_type", "module", "subject", "folder", "status", "design", "version", "email_template_id", "updated_at")}


def scoped(db, user, identity):
    row = db.query(CRMVisualTemplate).filter_by(id=identity, organization_id=tenant(user)).first()
    if not row: raise HTTPException(404, "Template not found")
    return row


@router.get("/metadata")
def metadata(user=Depends(READ)):
    from app.core.masking import user_has_permission
    return {"fields": [{"group": g, "key": k, "label": label, "sample": sample} for g, k, label, sample in FIELDS],
            "can_edit": bool(user.is_superuser or any(user_has_permission(user, p) for p in ("crm_manage", "crm_admin", "communication_templates_manage"))),
            "can_publish_email": bool(user.is_superuser or user_has_permission(user, "communication_templates_manage"))}


@router.get("/templates")
def list_templates(db: Session = Depends(get_db), user=Depends(READ)):
    return {"items": [output(row) for row in db.query(CRMVisualTemplate).filter_by(organization_id=tenant(user)).order_by(CRMVisualTemplate.updated_at.desc(), CRMVisualTemplate.id.desc()).all()]}


@router.post("/render")
def preview(data: RenderInput, user=Depends(READ)):
    return render(data)


@router.post("/templates", status_code=201)
def create(data: TemplateInput, db: Session = Depends(get_db), user=Depends(WRITE)):
    render(RenderInput(template=data))  # Validate URLs before persisting.
    row = CRMVisualTemplate(**data.model_dump(exclude={"version"}), version=1, organization_id=tenant(user), created_by=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return output(row)


@router.put("/templates/{identity}")
def update(identity: int, data: TemplateInput, db: Session = Depends(get_db), user=Depends(WRITE)):
    row = scoped(db, user, identity)
    render(RenderInput(template=data))
    # Compare-and-swap also protects against simultaneous writers.
    changed = db.query(CRMVisualTemplate).filter_by(id=row.id, organization_id=tenant(user), version=data.version).update({**data.model_dump(exclude={"version"}), "version": data.version + 1}, synchronize_session=False)
    if not changed: raise HTTPException(409, "Someone updated this template. Reload the saved version before saving.")
    db.commit(); db.refresh(row)
    return output(row)


@router.delete("/templates/{identity}", status_code=204)
def delete(identity: int, db: Session = Depends(get_db), user=Depends(WRITE)):
    row = scoped(db, user, identity)
    db.delete(row); db.commit()


@router.post("/templates/{identity}/publish-email")
def publish(identity: int, db: Session = Depends(get_db), user=Depends(RequirePermission("communication_templates_manage"))):
    row = scoped(db, user, identity)
    if row.category != "email" or row.status != "ready": raise HTTPException(422, "Save a ready email template before publishing")
    t = TemplateInput.model_validate(output(row) | {} if False else {k: getattr(row, k) for k in TemplateInput.model_fields})
    # The existing composer resolves these fields. Other merge values must be filled before sending.
    supported = {"name", "email", "company", "phone"}
    keys = set(TOKEN.findall(t.subject + ' '.join(b.text for b in t.design.blocks)))
    if keys - supported: raise HTTPException(422, "The email composer supports {{name}}, {{email}}, {{company}}, {{phone}}. Replace other placeholders with your company / sender details before publishing.")
    rendered = render(RenderInput(template=t))
    email = db.query(CommunicationEmailTemplate).filter_by(id=row.email_template_id, organization_id=tenant(user)).first() if row.email_template_id else None
    if not email:
        email = CommunicationEmailTemplate(organization_id=tenant(user), created_by=user.id)
        db.add(email)
    email.name = row.name; email.subject = row.subject; email.body_html = rendered['body']
    email.body_text = '\n'.join(b.text for b in t.design.blocks)
    email.module_name = row.module; email.template_type = "email"; email.active = True
    db.flush(); row.email_template_id = email.id
    db.commit()
    return {"email_template_id": email.id}


class MergeInput(Strict):
    entity: Literal["leads", "contacts", "accounts", "deals", "quotations"]
    record_ids: list[int] = Field(min_length=1, max_length=50)
    values: dict[str, str] = Field(default_factory=dict, max_length=100)


@router.post("/templates/{identity}/merge")
def merge_records(identity: int, data: MergeInput, db: Session = Depends(get_db), user=Depends(READ)):
    from .api import router as crm
    row = scoped(db, user, identity)
    expected = {"lead": "leads", "contact": "contacts", "account": "accounts", "deal": "deals", "quotation": "quotations"}
    if expected[row.module] != data.entity: raise HTTPException(422, "Choose records from the template's module")
    crm._assert_entity_permission(data.entity, user, "view")
    resource = crm._get_resource(data.entity)
    query = crm._apply_record_visibility(crm._base_query(db, resource, tenant(user)), resource, user, db)
    records = query.filter(resource.model.id.in_(data.record_ids)).all()
    if len(records) != len(set(data.record_ids)): raise HTTPException(404, "One or more records are unavailable")
    t = TemplateInput.model_validate({k: getattr(row, k) for k in TemplateInput.model_fields})
    results = []
    for record in records:
        # Only explicitly supported visible fields are exposed; never serialize arbitrary CRM data.
        values = dict(data.values)
        for key, attrs in {"name": ("full_name", "name", "title"), "email": ("email",), "phone": ("phone",), "company": ("company_name",), "address": ("address",)}.items():
            value = next((getattr(record, a, None) for a in attrs if getattr(record, a, None)), None)
            if value is not None: values[key] = str(value)
        if values.get("name"): values["first_name"] = values["name"].split()[0]
        result = render(RenderInput(template=t, values=values))
        results.append({"record_id": record.id, "name": values.get("name", str(record.id)), **result})
    return {"items": results}
