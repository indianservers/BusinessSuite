"""Paginated payslip rendering, shared by publishing and individual downloads."""
from decimal import Decimal
from xml.sax.saxutils import escape


def render_payslip(path: str, payload: dict, company_name: str = "", template: dict | None = None, branding: dict | None = None) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from app.services.payroll_delivery import DEFAULT_TEMPLATE

    styles = getSampleStyleSheet()
    styles["BodyText"].spaceBefore = 3
    styles["Heading2"].spaceBefore = 9
    template = {**DEFAULT_TEMPLATE, **(template or {})}
    if template["layout"] == "compact":
        styles["BodyText"].fontSize, styles["BodyText"].leading = 9, 11
    currency = payload.get("currency") or "INR"

    def money(value):
        return f"{currency} {Decimal(str(value or 0)):,.2f}"

    def para(value, style="BodyText"):
        return Paragraph(escape(str(value or "")), styles[style])

    employee = payload.get("employee") or {}
    def brand_image(kind, max_width, max_height):
        from pathlib import Path
        from app.core.config import settings
        from app.core.storage import upload_exists, materialize_file
        relative = (branding or {}).get(kind)
        if not relative:
            return None
        root = Path(settings.UPLOAD_DIR).resolve()
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or not upload_exists(str(target)):
            return None
        materialize_file(str(target))
        picture = Image(str(target))
        ratio = min(max_width / picture.imageWidth, max_height / picture.imageHeight)
        picture.drawWidth, picture.drawHeight = picture.imageWidth * ratio, picture.imageHeight * ratio
        picture.hAlign = "LEFT"
        return picture

    story = []
    logo = brand_image("logo", 150, 50)
    if logo:
        story.extend([logo, Spacer(1, 8)])
    title = "Full & Final Settlement Statement" if payload.get("document_kind") == "settlement" else "Payslip"
    story.extend([para(company_name, "Heading2"), para(title, "Title")])
    if payload.get("preview"):
        story.append(para("SAMPLE PREVIEW - not an employee payment statement", "Heading3"))
    story.append(para(f"Period: {payload['month']:02d}/{payload['year']}"))
    if payload.get("last_working_date"):
        story.append(para(f"Last working date: {payload['last_working_date']}"))
    code = f"{employee.get('employee_id', '')} - " if template["show_employee_code"] else ""
    story.append(para(f"Employee: {code}{employee.get('first_name', '')} {employee.get('last_name', '')}"))
    if template["show_department"] and payload.get("department"):
        story.append(para(f"Department: {payload['department']}"))
    if template["show_working_days"] and payload.get("document_kind") != "settlement":
        story.append(para(f"Working days: {payload.get('working_days') or 0} | Paid days: {payload.get('paid_days') or 0} | Loss of pay days: {payload.get('lop_days') or 0}"))
    story.append(Spacer(1, 14))
    for title, key in [("Earnings", "earnings"), ("Deductions", "deductions"),
                       ("Reimbursements", "reimbursements"), ("Employer Contributions", "employer_contributions")]:
        rows = payload.get(key) or []
        if key == "employer_contributions" and not template["show_employer_contributions"]:
            continue
        if key == "reimbursements" and not template["show_reimbursements"]:
            continue
        if not rows:
            continue
        story.append(para(title, "Heading2"))
        table = Table([[para("Component"), para("Amount")]] +
                      [[para(row["component_name"]), para(money(row["amount"]))] for row in rows],
                      colWidths=[340, 155], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe" if template["layout"] == "professional" else "#edf2f7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if template["layout"] == "compact" else 8),
            ("TOPPADDING", (0, 0), (-1, -1), 3 if template["layout"] == "compact" else 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.extend([table, Spacer(1, 6)])
    for title, key in [("Gross salary", "gross_salary"), ("Total deductions", "total_deductions"), ("Net pay", "net_salary")]:
        story.append(para(f"{title}: {money(payload.get(key))}", "Heading3"))
    if payload.get("ytd") and template["show_ytd"]:
        story.append(para(f"Year to date - {payload.get('ytd_period_label') or 'Financial year'}", "Heading2"))
        for title, key in [("Gross", "gross_salary"), ("Deductions", "total_deductions"), ("Net", "net_salary")]:
            story.append(para(f"{title}: {money(payload['ytd'].get(key))}"))
    signature = brand_image("signature", 140, 50)
    if signature:
        story.extend([Spacer(1, 16), signature, para("Authorized signatory")])

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        from reportlab.lib.utils import simpleSplit
        for index, line in enumerate(simpleSplit(template["footer"], "Helvetica", 8, A4[0] - 180)[:4]):
            canvas.drawString(50, 38 - index * 9, line)
        canvas.drawRightString(A4[0] - 50, 30, f"Page {doc.page}")

    SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50,
                      topMargin=40, bottomMargin=50, title="Payslip").build(story, onFirstPage=footer, onLaterPages=footer)
