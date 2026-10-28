"""Database-backed templates and immutable issuance snapshots; PDFs never stored on disk."""
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
from xml.sax.saxutils import escape

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, KeepTogether
from sqlalchemy import or_, and_

from app.models.company import Company, Branch
from app.models.employee import Employee
from app.models.document import StudioAsset
from app.apps.interns_hub.models import InternApplication


BASE_KEYS = {
    "recipient.name", "recipient.email", "recipient.employee_code", "recipient.designation",
    "recipient.department", "recipient.branch", "recipient.joining_date", "recipient.exit_date",
    "recipient.college", "recipient.degree", "recipient.graduation_year", "recipient.application_reference",
    "company.name", "company.legal_name", "company.address", "company.email", "company.phone", "company.website",
    "system.reference", "system.issue_date",
}
TOKEN = re.compile(r"{{\s*([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)\s*}}")


def fail(message):
    raise HTTPException(422, message)


def validate_template(data):
    fields = [f.model_dump() if hasattr(f, "model_dump") else f for f in data.custom_fields]
    keys = [f["key"] for f in fields]
    if len(keys) != len(set(keys)):
        fail("Custom field keys must be unique")
    allowed = BASE_KEYS | {"custom." + k for k in keys}
    for text in (data.title, data.body):
        unknown = set(TOKEN.findall(text)) - allowed
        if unknown:
            fail("Unknown placeholders: " + ", ".join(sorted(unknown)))
        stripped = TOKEN.sub("", text)
        if "{" in stripped or "}" in stripped:
            fail("Use plain text and {{group.field}} placeholders only")


def employee_query(db, org):
    return db.query(Employee).filter(Employee.deleted_at.is_(None), or_(
        Employee.branch.has(Branch.company_id == org),
        and_(Employee.branch_id.is_(None), org == 1),
    ))


def recipient_data(db, org, kind, identity):
    values = {key: "" for key in BASE_KEYS if key.startswith("recipient.")}
    if kind == "employee":
        person = employee_query(db, org).filter(Employee.id == identity).first()
        if not person:
            raise HTTPException(404, "Recipient not found")
        values.update({
            "recipient.name": " ".join(filter(None, [person.first_name, person.middle_name, person.last_name])),
            "recipient.email": person.work_email or "",
            "recipient.employee_code": person.employee_id,
            "recipient.designation": getattr(person.designation, "name", ""),
            "recipient.department": getattr(person.department, "name", ""),
            "recipient.branch": getattr(person.branch, "name", ""),
            "recipient.joining_date": person.date_of_joining,
            "recipient.exit_date": person.date_of_exit,
        })
        if person.educations:
            education = max(person.educations, key=lambda row: (row.pass_year or 0, row.id))
            values.update({"recipient.college": education.institution, "recipient.degree": education.degree,
                "recipient.graduation_year": education.pass_year})
    else:
        person = db.query(InternApplication).filter(InternApplication.id == identity, InternApplication.organization_id == org).first()
        if not person:
            raise HTTPException(404, "Recipient not found")
        details = person.details or {}
        values.update({"recipient.name": person.full_name, "recipient.email": person.email,
            "recipient.application_reference": person.reference,
            "recipient.college": details.get("college", ""),
            "recipient.degree": details.get("degree", ""),
            "recipient.graduation_year": details.get("passout_year", "")})
    return {key: format_value(value) for key, value in values.items()}


def format_value(value):
    if isinstance(value, date):
        return value.strftime("%d %B %Y")
    return str(value) if value is not None else ""


def company_data(company):
    if not company:
        fail("Configure your company profile before generating documents")
    return {"company.name": company.name, "company.legal_name": company.legal_name or company.name,
        "company.address": ", ".join(str(v) for v in [company.address, company.city, company.state, company.country, company.pincode] if v),
        "company.email": company.email or "", "company.phone": company.phone or "", "company.website": company.website or ""}


def make_snapshot(db, org, template, head, data, reference):
    if template.version != data.template_version or head.version != data.letterhead_version:
        raise HTTPException(409, "Template or letterhead changed. Reload and preview again.")
    if not template.is_active or not head.is_active:
        fail("Choose an active template and letterhead")
    if template.recipient_scope not in ("both", data.recipient_type):
        fail("This template cannot be used for this recipient type")
    company = company_data(db.query(Company).filter(Company.id == org).first())
    values = {**company, **recipient_data(db, org, data.recipient_type, data.recipient_id),
        "system.reference": reference, "system.issue_date": format_value(data.issue_date)}
    if not values["recipient.name"].strip() or len(values["recipient.name"]) > 250:
        fail("Recipient full name must contain between 1 and 250 characters")
    fields = {f["key"]: f for f in template.custom_fields}
    if set(data.variables) - set(fields):
        fail("Only the template's custom fields can be supplied")
    for key, field in fields.items():
        value = data.variables.get(key, field.get("default", "")).strip()
        if len(value) > 2000:
            fail(field["label"] + " exceeds 2,000 characters")
        if field.get("required") and not value:
            fail("Required field: " + field["label"])
        if value and field["type"] == "date":
            try:
                value = format_value(date.fromisoformat(value))
            except ValueError:
                fail("Invalid date: " + field["label"])
        if value and field["type"] == "number":
            try:
                if not Decimal(value).is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                fail("Invalid number: " + field["label"])
        values["custom." + key] = value
    missing = {key for key in TOKEN.findall(template.title + "\n" + template.body)
        if not values.get(key) and not key.startswith("custom.")}
    if missing:
        fail("Missing database values: " + ", ".join(sorted(missing)))
    substitute = lambda text: TOKEN.sub(lambda match: values[match.group(1)], text)
    title, body = substitute(template.title), substitute(template.body)
    if len(title) > 250 or len(body) > 50000:
        fail("Rendered document is too long")
    head_keys = ("name", "header_text", "footer_text", "accent_color", "show_company_header", "logo_asset_id",
        "background_asset_id", "signature_asset_id", "signatory_name", "signatory_title", "top_margin_mm", "bottom_margin_mm", "version")
    return {"title": title, "body": body, "kind": template.kind, "orientation": template.orientation,
        "reference": reference, "issue_date": format_value(data.issue_date), "recipient_name": values["recipient.name"],
        "values": values, "company": company, "letterhead": {key: getattr(head, key) for key in head_keys}}


def normalize_image(content):
    if not content or len(content) > 2 * 1024 * 1024:
        fail("Upload a PNG or JPEG image up to 2 MB")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in ("PNG", "JPEG") or max(image.size) > 6000 or image.width * image.height > 20000000:
                fail("Use a PNG or JPEG up to 6,000 pixels per side and 20 megapixels")
            image.load()
            output = BytesIO()
            image.convert("RGBA").save(output, format="PNG")
            normalized = output.getvalue()
            if len(normalized) > 8 * 1024 * 1024:
                fail("Image is too large after processing")
            return normalized
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        fail("Invalid image file")


def normalize_artwork(content, kind):
    if kind != "background" or not content.startswith(b"%PDF-"):
        return normalize_image(content), "image/png"
    if len(content) > 2*1024*1024:
        fail("Upload a single-page PDF up to 2 MB")
    from pypdf import PdfReader, PdfWriter
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted or len(reader.pages) != 1:
            fail("Letterhead PDF must have exactly one page and no password")
        page = reader.pages[0]
        if not (100 <= float(page.mediabox.width) <= 2000 and 100 <= float(page.mediabox.height) <= 2000):
            fail("Unsupported letterhead page size")
        # Copy only the printable page, excluding interactive annotations/actions.
        for key in ("/Annots", "/AA", "/OpenAction"):
            page.pop(key, None)
        writer = PdfWriter(); writer.add_page(page)
        output = BytesIO(); writer.write(output)
        return output.getvalue(), "application/pdf"
    except HTTPException:
        raise
    except Exception:
        fail("Invalid letterhead PDF")


def render_pdf(db, org, snapshot, watermark=""):
    head, company = snapshot["letterhead"], snapshot["company"]
    assets = {}
    pdf_background = None
    for key in ("logo_asset_id", "background_asset_id", "signature_asset_id"):
        identity = head.get(key)
        if identity:
            asset = db.query(StudioAsset).filter(StudioAsset.id == identity, StudioAsset.organization_id == org).first()
            if not asset:
                fail("Letterhead artwork is unavailable")
            if key == "background_asset_id" and asset.content_type == "application/pdf":
                pdf_background = asset.content
            else:
                assets[key] = asset.content
    certificate = snapshot["kind"] == "certificate"
    size = landscape(A4) if snapshot["orientation"] == "landscape" else A4
    width, height = size
    output = BytesIO()
    accent = colors.HexColor(head["accent_color"])
    style = ParagraphStyle("body", fontName="Helvetica", fontSize=13 if certificate else 11,
        leading=22 if certificate else 17, spaceAfter=12, alignment=TA_CENTER if certificate else 0)
    title_style = ParagraphStyle("title", parent=style, fontName="Helvetica-Bold", fontSize=25 if certificate else 17,
        leading=31 if certificate else 23, textColor=accent, spaceAfter=20)
    def paragraph(value, styling=style):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styling)
    def image_on(canvas, content, x, y, w, h):
        canvas.drawImage(ImageReader(BytesIO(content)), x, y, w, h, preserveAspectRatio=True, anchor="c", mask="auto")
    def decorate(canvas, document):
        canvas.saveState()
        if assets.get("background_asset_id"):
            image_on(canvas, assets["background_asset_id"], 0, 0, width, height)
        elif certificate and not pdf_background:
            canvas.setStrokeColor(accent)
            canvas.setLineWidth(1.5)
            canvas.rect(10*mm, 10*mm, width-20*mm, height-20*mm)
            canvas.setLineWidth(.4)
            canvas.rect(12*mm, 12*mm, width-24*mm, height-24*mm)
        if head.get("show_company_header", True):
            left = 22*mm
            if assets.get("logo_asset_id"):
                image_on(canvas, assets["logo_asset_id"], left, height-33*mm, 24*mm, 20*mm)
                left += 29*mm
            header_style = ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=accent)
            text = paragraph(company["company.name"], header_style)
            tw, th = text.wrap(width-left-22*mm, 20*mm)
            text.drawOn(canvas, left, height-17*mm-th)
            sub = paragraph(head.get("header_text") or company.get("company.address", ""), ParagraphStyle("sub", fontSize=8, leading=11))
            sw, sh = sub.wrap(width-left-22*mm, 20*mm)
            if sh > 16*mm:
                fail("Letterhead header is too tall; shorten the header text")
            if 19*mm + th + sh > (head["top_margin_mm"]-3)*mm:
                fail("Increase the top margin to fit the company name and header")
            sub.drawOn(canvas, left, height-19*mm-th-sh)
        footer = paragraph(head.get("footer_text", ""), ParagraphStyle("footer", fontSize=8, leading=10, alignment=TA_CENTER))
        fw, fh = footer.wrap(width-44*mm, 20*mm)
        if fh > (head["bottom_margin_mm"]-10)*mm:
            fail("Footer exceeds its margin; shorten it or increase the bottom margin")
        footer.drawOn(canvas, 22*mm, 13*mm)
        canvas.setFillColor(colors.HexColor("#59636d"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(22*mm, 8*mm, snapshot["reference"])
        canvas.drawRightString(width-22*mm, 8*mm, f"Page {document.page}")
        if watermark:
            canvas.translate(width/2, height/2)
            canvas.rotate(35)
            canvas.setFillColor(colors.Color(.6, .6, .6, alpha=.25))
            canvas.setFont("Helvetica-Bold", 65)
            canvas.drawCentredString(0, 0, watermark)
        canvas.restoreState()
    doc = SimpleDocTemplate(output, pagesize=size, topMargin=head["top_margin_mm"]*mm,
        bottomMargin=head["bottom_margin_mm"]*mm, leftMargin=24*mm, rightMargin=24*mm,
        title=snapshot["title"], author=company["company.name"])
    story = [paragraph(snapshot["title"], title_style)]
    story += [paragraph("Date: " + snapshot["issue_date"], ParagraphStyle("date", parent=style, fontSize=9, spaceAfter=15))]
    name_style = ParagraphStyle("recipient", parent=style, fontName="Helvetica-Bold", fontSize=23, leading=29, textColor=accent)
    story += [paragraph(part, name_style if certificate and part.strip() == snapshot["recipient_name"] else style)
        for part in snapshot["body"].split("\n\n") if part.strip()]
    signature = [Spacer(1, 10*mm)]
    if assets.get("signature_asset_id"):
        image = PDFImage(BytesIO(assets["signature_asset_id"]), width=40*mm, height=15*mm, kind="proportional")
        image.hAlign = "CENTER" if certificate else "LEFT"
        signature.append(image)
    if head.get("signatory_name"):
        signature.append(paragraph(head["signatory_name"]))
    signature.append(paragraph(head["signatory_title"]))
    story.append(KeepTogether(signature))
    from reportlab.platypus.doctemplate import LayoutError
    try:
        doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    except LayoutError:
        fail("Content does not fit. Shorten text or adjust letterhead margins.")
    result = output.getvalue()
    from pypdf import PdfReader, PdfWriter, PageObject, Transformation
    pages = len(PdfReader(BytesIO(result)).pages)
    if certificate and pages != 1:
        fail("Certificate exceeds one page. Shorten text or reduce margins.")
    if pages > 30:
        fail("Document exceeds 30 pages")
    if pdf_background:
        background = PdfReader(BytesIO(pdf_background)).pages[0]
        bw, bh = float(background.mediabox.width), float(background.mediabox.height)
        if (bw > bh) != (width > height):
            fail("Letterhead PDF orientation must match the document")
        scale = min(width/bw, height/bh)
        transform = Transformation().translate(-float(background.mediabox.left), -float(background.mediabox.bottom)).scale(scale).translate((width-bw*scale)/2, (height-bh*scale)/2)
        writer = PdfWriter()
        for page in PdfReader(BytesIO(result)).pages:
            composed = PageObject.create_blank_page(width=width, height=height)
            composed.merge_transformed_page(background, transform)
            composed.merge_page(page)
            writer.add_page(composed)
        combined = BytesIO(); writer.write(combined); result = combined.getvalue()
    return result
