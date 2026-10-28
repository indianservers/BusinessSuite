"""Letter and certificate management, scoped explicitly even for superusers."""
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, RequirePermission
from app.core.masking import user_has_permission
from app.core.config import settings
from app.apps.srm.services.commercial import tenant
from app.models.company import Company
from app.models.employee import Employee
from app.models.document import StudioAsset, StudioLetterhead, StudioTemplate, StudioDocument
from app.apps.interns_hub.models import InternApplication
from app.schemas.document_studio import TemplateInput, LetterheadInput, GenerateInput, RevokeInput
from app.services.document_studio import BASE_KEYS, validate_template, employee_query, company_data, make_snapshot, normalize_artwork, render_pdf

router = APIRouter(prefix="/studio", tags=["Letters & Certificates"])
issuer = RequirePermission("employee_update", "company_manage")
editor = RequirePermission("company_manage", "settings_manage")


def can(user, *permissions):
    return bool(user.is_superuser or any(user_has_permission(user, p) for p in permissions))


def scoped(db, model, user, identity):
    row = db.query(model).filter(model.organization_id == tenant(user), model.id == identity).first()
    if not row:
        raise HTTPException(404, "Record not found")
    return row


def fields(row, keys):
    return {key: getattr(row, key) for key in keys}


def template_out(row):
    return fields(row, ["id", "name", "document_type", "kind", "orientation", "recipient_scope", "title", "body", "custom_fields", "letterhead_id", "version", "is_active"])


def head_out(row):
    return fields(row, ["id", *[k for k in LetterheadInput.model_fields if k != "version"], "version"])


def document_out(row):
    return fields(row, ["id", "reference", "recipient_type", "recipient_id", "recipient_name", "title", "document_type", "status", "issue_date", "template_version", "issued_at", "revoke_reason"])


def validate_head(db, user, data):
    if data.show_company_header and data.top_margin_mm < 44:
        raise HTTPException(422, "Use a top margin of at least 44 mm when the company header is visible")
    for key, kind in (("logo_asset_id", "logo"), ("background_asset_id", "background"), ("signature_asset_id", "signature")):
        if getattr(data, key):
            asset = scoped(db, StudioAsset, user, getattr(data, key))
            if asset.kind != kind:
                raise HTTPException(422, f"Choose a {kind} asset for {key}")


def check_applicant(user, recipient_type):
    if recipient_type == "application" and not can(user, "employee_create", "intern_management_manage"):
        raise HTTPException(403, "Intern application access is required")


@router.get("/metadata")
def metadata(db: Session = Depends(get_db), user=Depends(issuer)):
    profile = db.query(Company).filter(Company.id == tenant(user)).first()
    company = company_data(profile)
    return {"placeholders": sorted(BASE_KEYS), "company": company,
        "has_company_logo": bool(profile.logo_url),
        "can_edit_templates": can(user, "company_manage", "settings_manage"),
        "can_use_applications": can(user, "employee_create", "intern_management_manage")}


@router.get("/templates")
def templates(db: Session = Depends(get_db), user=Depends(issuer)):
    return [template_out(row) for row in db.query(StudioTemplate).filter(StudioTemplate.organization_id == tenant(user)).order_by(StudioTemplate.name).all()]


@router.post("/templates", status_code=201)
def create_template(data: TemplateInput, db: Session = Depends(get_db), user=Depends(editor)):
    validate_template(data)
    if data.letterhead_id:
        scoped(db, StudioLetterhead, user, data.letterhead_id)
    row = StudioTemplate(**data.model_dump(exclude={"version"}), organization_id=tenant(user), created_by=user.id)
    db.add(row)
    db.commit()
    return template_out(row)


@router.put("/templates/{identity}")
def update_template(identity: int, data: TemplateInput, db: Session = Depends(get_db), user=Depends(editor)):
    row = scoped(db, StudioTemplate, user, identity)
    validate_template(data)
    if data.letterhead_id:
        scoped(db, StudioLetterhead, user, data.letterhead_id)
    changes = data.model_dump(exclude={"version"})
    count = db.query(StudioTemplate).filter(StudioTemplate.id == identity, StudioTemplate.organization_id == tenant(user), StudioTemplate.version == data.version).update({**changes, "version": StudioTemplate.version + 1}, synchronize_session=False)
    if not count:
        raise HTTPException(409, "Template changed. Reload before saving.")
    db.commit()
    db.refresh(row)
    return template_out(row)


@router.get("/letterheads")
def letterheads(db: Session = Depends(get_db), user=Depends(issuer)):
    return [head_out(row) for row in db.query(StudioLetterhead).filter(StudioLetterhead.organization_id == tenant(user)).order_by(StudioLetterhead.name).all()]


@router.post("/letterheads", status_code=201)
def create_head(data: LetterheadInput, db: Session = Depends(get_db), user=Depends(editor)):
    validate_head(db, user, data)
    row = StudioLetterhead(**data.model_dump(exclude={"version"}), organization_id=tenant(user), created_by=user.id)
    db.add(row)
    db.commit()
    return head_out(row)


@router.put("/letterheads/{identity}")
def update_head(identity: int, data: LetterheadInput, db: Session = Depends(get_db), user=Depends(editor)):
    row = scoped(db, StudioLetterhead, user, identity)
    validate_head(db, user, data)
    count = db.query(StudioLetterhead).filter(StudioLetterhead.id == identity, StudioLetterhead.organization_id == tenant(user), StudioLetterhead.version == data.version).update({**data.model_dump(exclude={"version"}), "version": StudioLetterhead.version + 1}, synchronize_session=False)
    if not count:
        raise HTTPException(409, "Letterhead changed. Reload before saving.")
    db.commit()
    db.refresh(row)
    return head_out(row)


@router.post("/assets", status_code=201)
async def upload_asset(kind: str = Query(pattern="^(logo|signature|background)$"), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(editor)):
    content, content_type = normalize_artwork(await file.read(2*1024*1024+1), kind)
    row = StudioAsset(organization_id=tenant(user), kind=kind, name=(file.filename or "Artwork")[:200], content_type=content_type, content=content, sha256=hashlib.sha256(content).hexdigest(), created_by=user.id)
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, "kind": row.kind}


@router.post("/company-logo", status_code=201)
def import_company_logo(db: Session = Depends(get_db), user=Depends(editor)):
    company = db.query(Company).filter(Company.id == tenant(user)).first()
    url = company.logo_url if company else ""
    # Company uploads are private storage keys, never arbitrary network URLs.
    if not url or not re.fullmatch(rf"/uploads/company_logos/{tenant(user)}_[a-f0-9]+\.(png|jpg|jpeg|webp)", url, re.IGNORECASE):
        raise HTTPException(422, "Upload the company logo here as a PNG or JPEG")
    from app.core.storage import materialize_file
    from PIL import Image
    path = Path(settings.UPLOAD_DIR) / url.removeprefix("/uploads/")
    if not path.resolve().is_relative_to(Path(settings.UPLOAD_DIR).resolve()):
        raise HTTPException(422, "Invalid company logo location")
    try:
        materialize_file(str(path))
        with path.open("rb") as source:
            content = source.read(2*1024*1024+1)
        if url.lower().endswith(".webp"):
            if len(content) > 2*1024*1024:
                raise HTTPException(422, "Company logo exceeds 2 MB. Upload a smaller image.")
            with Image.open(BytesIO(content)) as image:
                if max(image.size) > 6000 or image.width*image.height > 20000000:
                    raise HTTPException(422, "Company logo is too large. Upload a smaller image.")
                normalized = BytesIO(); image.convert("RGBA").save(normalized, format="PNG"); content = normalized.getvalue()
        content, content_type = normalize_artwork(content, "logo")
    except (OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Company logo could not be loaded. Upload the logo here.") from None
    asset = StudioAsset(organization_id=tenant(user), kind="logo", name="Company profile logo", content_type=content_type,
        content=content, sha256=hashlib.sha256(content).hexdigest(), created_by=user.id)
    db.add(asset); db.commit()
    return {"id": asset.id, "name": asset.name, "kind": asset.kind}


@router.get("/assets/{identity}")
def asset_preview(identity: int, db: Session = Depends(get_db), user=Depends(issuer)):
    row = scoped(db, StudioAsset, user, identity)
    return Response(row.content, media_type=row.content_type, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/recipients")
def recipients(kind: str = Query(default="employee", pattern="^(employee|application)$"), q: str = Query(default="", max_length=150), limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db), user=Depends(issuer)):
    check_applicant(user, kind)
    pattern = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
    if kind == "employee":
        query = employee_query(db, tenant(user))
        if q:
            query = query.filter(or_(Employee.first_name.ilike(pattern, escape="\\"), Employee.last_name.ilike(pattern, escape="\\"), Employee.employee_id.ilike(pattern, escape="\\")))
        return [{"id": e.id, "name": " ".join(filter(None, [e.first_name, e.middle_name, e.last_name])), "detail": e.employee_id} for e in query.order_by(Employee.first_name, Employee.id).limit(limit)]
    query = db.query(InternApplication).filter(InternApplication.organization_id == tenant(user))
    if q:
        query = query.filter(or_(InternApplication.full_name.ilike(pattern, escape="\\"), InternApplication.reference.ilike(pattern, escape="\\")))
    return [{"id": e.id, "name": e.full_name, "detail": e.reference} for e in query.order_by(InternApplication.full_name, InternApplication.id).limit(limit)]


def prepare(db, user, data, reference):
    check_applicant(user, data.recipient_type)
    template = scoped(db, StudioTemplate, user, data.template_id)
    head = scoped(db, StudioLetterhead, user, data.letterhead_id)
    return template, make_snapshot(db, tenant(user), template, head, data, reference)


def pdf_response(content, reference):
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{reference}.pdf"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/preview")
def preview(data: GenerateInput, db: Session = Depends(get_db), user=Depends(issuer)):
    _, snapshot = prepare(db, user, data, "PREVIEW")
    return pdf_response(render_pdf(db, tenant(user), snapshot, "PREVIEW"), "preview")


@router.post("/issue", status_code=201)
def issue(data: GenerateInput, db: Session = Depends(get_db), user=Depends(issuer)):
    request_hash = hashlib.sha256(json.dumps(data.model_dump(mode="json", exclude={"request_key"}), sort_keys=True).encode()).hexdigest()
    def existing():
        row = db.query(StudioDocument).filter(StudioDocument.organization_id == tenant(user), StudioDocument.request_key == data.request_key).first()
        if row and row.request_hash != request_hash:
            raise HTTPException(409, "Request key already used with different values")
        return row
    row = existing()
    if row:
        return document_out(row)
    reference = f"DOC-{data.issue_date.year}-{uuid4().hex[:16].upper()}"
    template, snapshot = prepare(db, user, data, reference)
    render_pdf(db, tenant(user), snapshot)  # Validate before recording issuance.
    row = StudioDocument(organization_id=tenant(user), reference=reference, template_id=template.id,
        template_version=template.version, recipient_type=data.recipient_type, recipient_id=data.recipient_id,
        recipient_name=snapshot["recipient_name"], title=snapshot["title"], document_type=template.document_type,
        issue_date=data.issue_date, snapshot=snapshot, request_key=data.request_key, request_hash=request_hash, issued_by=user.id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = existing()
        if not row:
            raise
    return document_out(row)


@router.get("/issued")
def issued(q: str = Query(default="", max_length=150), skip: int = Query(default=0, ge=0), limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db), user=Depends(issuer)):
    query = db.query(StudioDocument).filter(StudioDocument.organization_id == tenant(user))
    if not can(user, "employee_create", "intern_management_manage"):
        query = query.filter(StudioDocument.recipient_type == "employee")
    if q:
        pattern = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(StudioDocument.recipient_name.ilike(pattern, escape="\\"), StudioDocument.reference.ilike(pattern, escape="\\")))
    return {"total": query.count(), "items": [document_out(row) for row in query.order_by(StudioDocument.id.desc()).offset(skip).limit(limit)]}


@router.get("/issued/{identity}/pdf")
def download(identity: int, db: Session = Depends(get_db), user=Depends(issuer)):
    row = scoped(db, StudioDocument, user, identity)
    check_applicant(user, row.recipient_type)
    return pdf_response(render_pdf(db, tenant(user), row.snapshot, "REVOKED" if row.status == "Revoked" else ""), row.reference)


@router.post("/issued/{identity}/revoke")
def revoke(identity: int, data: RevokeInput, db: Session = Depends(get_db), user=Depends(issuer)):
    if len(data.reason.strip()) < 5:
        raise HTTPException(422, "Enter a revocation reason of at least five characters")
    row = scoped(db, StudioDocument, user, identity)
    check_applicant(user, row.recipient_type)
    if row.status != "Revoked":
        row.status, row.revoke_reason, row.revoked_by, row.revoked_at = "Revoked", data.reason.strip(), user.id, datetime.now(timezone.utc)
        db.commit()
    return document_out(row)


def starter_templates():
    def custom(key, label, type="text"):
        return {"key": key, "label": label, "type": type, "required": True, "default": ""}
    entries = [
        ("offer", "Offer Letter", "both", "Dear {{recipient.name}},\n\nWe are pleased to offer you the position of {{custom.position}} at {{company.name}}, starting on {{custom.start_date}}.\n\n{{custom.terms}}\n\nPlease confirm your acceptance by {{custom.accept_by}}. We look forward to welcoming you.", [custom("position", "Position"), custom("start_date", "Start date", "date"), custom("terms", "Offer terms and compensation", "multiline"), custom("accept_by", "Accept by", "date")]),
        ("intern_offer", "Internship Offer Letter", "both", "Dear {{recipient.name}},\n\nWe are pleased to offer you an internship in {{custom.program}} at {{company.name}} from {{custom.start_date}} to {{custom.end_date}}.\n\n{{custom.terms}}\n\nOur internship program is completely free. If anyone asks you to pay a fee for this program, please report it to 9618222220.", [custom("program", "Program"), custom("start_date", "Start date", "date"), custom("end_date", "End date", "date"), custom("terms", "Internship terms", "multiline")]),
        ("appointment", "Appointment Letter", "employee", "Dear {{recipient.name}},\n\nWe confirm your appointment as {{recipient.designation}} at {{company.name}}, effective {{recipient.joining_date}}.\n\n{{custom.terms}}", [custom("terms", "Appointment terms", "multiline")]),
        ("completion", "Completion Letter", "both", "This is to confirm that {{recipient.name}} successfully completed {{custom.program}} at {{company.name}} from {{custom.start_date}} to {{custom.end_date}}.\n\n{{custom.remarks}}", [custom("program", "Program"), custom("start_date", "Start date", "date"), custom("end_date", "End date", "date"), custom("remarks", "Completion remarks", "multiline")]),
        ("experience", "Experience Letter", "employee", "To whom it may concern,\n\nThis is to certify that {{recipient.name}} ({{recipient.employee_code}}) was employed with {{company.name}} as {{recipient.designation}} from {{recipient.joining_date}} to {{recipient.exit_date}}.\n\n{{custom.remarks}}", [custom("remarks", "Verified responsibilities and remarks", "multiline")]),
        ("relieving", "Relieving Letter", "employee", "Dear {{recipient.name}},\n\nWith reference to your resignation, we confirm that you have been relieved of your duties as {{recipient.designation}} at {{company.name}} effective {{recipient.exit_date}}.\n\n{{custom.clearance}}\n\nWe wish you success in your future endeavours.", [custom("clearance", "Approved clearance and settlement statement", "multiline")]),
        ("verification", "Employment Verification Letter", "employee", "To whom it may concern,\n\nThis is to confirm that {{recipient.name}} ({{recipient.employee_code}}) joined {{company.name}} on {{recipient.joining_date}}.\n\n{{custom.verification}}", [custom("verification", "Verified employment status and purpose", "multiline")]),
        ("recommendation", "Recommendation Letter", "both", "To whom it may concern,\n\nWe are pleased to recommend {{recipient.name}}.\n\n{{custom.recommendation}}\n\nFor further information, please contact {{company.email}}.", [custom("recommendation", "Recommendation", "multiline")]),
    ]
    result = []
    for key, name, scope, body, fields in entries:
        result.append(dict(starter_key=key, name=name, document_type=name, kind="letter", orientation="portrait", recipient_scope=scope, title=name, body=body, custom_fields=fields))
    for key, title, phrase in [("completion_cert", "Certificate of Completion", "successfully completed"), ("participation_cert", "Certificate of Participation", "participated in"), ("appreciation_cert", "Certificate of Appreciation", "made a valued contribution to"), ("training_cert", "Training Certificate", "successfully completed the training in")]:
        result.append(dict(starter_key=key, name=title, document_type=title, kind="certificate", orientation="landscape", recipient_scope="both", title=title,
            body="This certificate is presented to\n\n{{recipient.name}}\n\nwho " + phrase + " {{custom.program}} at {{company.name}}\nfrom {{custom.start_date}} to {{custom.end_date}}.\n\n{{custom.remarks}}",
            custom_fields=[custom("program", "Program or achievement"), custom("start_date", "Start date", "date"), custom("end_date", "End date", "date"), {**custom("remarks", "Remarks"), "required": False}]))
    return result


@router.post("/initialize")
def initialize(db: Session = Depends(get_db), user=Depends(editor)):
    org = tenant(user)
    # Serialize organization setup on PostgreSQL; unique starter keys protect retries.
    company = db.query(Company).filter(Company.id == org).with_for_update().first()
    company_data(company)
    head = db.query(StudioLetterhead).filter(StudioLetterhead.organization_id == org).order_by(StudioLetterhead.id).first()
    if not head:
        head = StudioLetterhead(organization_id=org, name="Company letterhead", created_by=user.id,
            footer_text=" | ".join(filter(None, [company.email, company.phone, company.website])))
        db.add(head)
        db.flush()
    existing = {key for (key,) in db.query(StudioTemplate.starter_key).filter(StudioTemplate.organization_id == org)}
    for starter in starter_templates():
        if starter["starter_key"] not in existing:
            db.add(StudioTemplate(**starter, organization_id=org, letterhead_id=head.id, created_by=user.id))
    db.commit()
    return {"message": "Reusable templates and company letterhead are ready"}
