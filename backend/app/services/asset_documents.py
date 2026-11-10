"""Printable, escaped asset documents generated from authorized database records."""
from io import BytesIO
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from app.models.asset import AssetAssignment, Asset
from app.models.company import Company
from app.models.exit import ExitChecklistItem
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc)


def tenant(user):
    from app.apps.srm.services.commercial import tenant as organization
    return organization(user)


def pdf_document(company, title, reference, facts, headings, rows, notes):
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="AssetTitle", parent=styles["Title"], fontSize=24, leading=30, textColor=colors.HexColor("#4c1d95"), alignment=0))
    styles.add(ParagraphStyle(name="AssetCell", fontSize=9, leading=13, spaceAfter=3))
    cell = lambda value: Paragraph(escape(str(value if value is not None else "Not recorded")), styles["AssetCell"])
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=38, leftMargin=38, topMargin=38, bottomMargin=42, title=title, author=company)
    story = [Paragraph(escape(company), styles["Heading2"]), Paragraph(escape(title), styles["AssetTitle"]),
        Paragraph(escape(reference), styles["Normal"]), Spacer(1, 20)]
    facts_table = Table([[cell(label), cell(value)] for label, value in facts], colWidths=[125, 394], hAlign="LEFT")
    facts_table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,-1),colors.HexColor("#f5f3ff")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story.extend([facts_table, Spacer(1, 22)])
    table = Table([[cell(h) for h in headings]]+[[cell(v) for v in row] for row in rows], colWidths=[519/len(headings)]*len(headings), repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#ede9fe")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#faf9ff")]),("LINEBELOW",(0,0),(-1,-1),.4,colors.HexColor("#e4ddf2")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9)]))
    story.extend([table, Spacer(1, 20)])
    for note in notes:
        story.extend([Paragraph(escape(note), styles["Normal"]), Spacer(1, 10)])
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e4ddf2"));canvas.line(38,35,A4[0]-38,35)
        canvas.setFont("Helvetica",8);canvas.setFillColor(colors.HexColor("#756985"))
        canvas.drawString(38,22,"Company assets | Generated from recorded lifecycle history")
        canvas.drawRightString(A4[0]-38,22,f"Page {doc.page}");canvas.restoreState()
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()


def company_name(db, user):
    company = db.get(Company, tenant(user))
    return company.name if company else "Company"


def handover_pdf(db, user, row):
    query = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user))
    if row.handover_group:
        rows = query.filter(AssetAssignment.handover_group == row.handover_group, AssetAssignment.employee_id == row.employee_id).order_by(AssetAssignment.id).all()
    else:
        rows = [row]
    employee = row.employee
    return pdf_document(company_name(db, user), "Asset handover receipt", f"HND-{row.handover_group or row.id}",
        [("Employee", f"{employee.first_name} {employee.last_name} ({employee.employee_id})"), ("Assigned on",row.assigned_date),
         ("Generated at",now().isoformat()), ("Acknowledgment", "Acknowledged by employee" if all(r.acknowledgement_signed for r in rows) else "Employee acknowledgment pending")],
        ["Asset / tag", "Handover condition", "Accessories", "Expected return"],
        [[f"{r.asset.name} / {r.asset.asset_tag}",r.condition_at_assignment,", ".join(r.accessories or []) or "None recorded",r.expected_return_date] for r in rows],
        [f"Acknowledgment for {r.asset.asset_tag}: {r.acknowledged_at.isoformat() if r.acknowledged_at else 'Pending'}; actor {r.acknowledged_by or 'not yet recorded'}." for r in rows]+
        ["This receipt reflects recorded acknowledgment. It does not assert a handwritten or cryptographic signature.", "Accessories and existing damage are recorded with the custody transaction. Keep this reference for returns."])


def clearance_pdf(db, user, record):
    rows = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user), AssetAssignment.employee_id == record.employee_id).order_by(AssetAssignment.id).all()
    employee = record.employee
    tasks = db.query(ExitChecklistItem).filter_by(exit_record_id=record.id).all()
    return pdf_document(company_name(db, user), "Asset clearance certificate", f"ASSET-CLEARANCE-{record.id}",
        [("Employee",f"{employee.first_name} {employee.last_name} ({employee.employee_id})"), ("Last working day",record.last_working_date),
         ("Asset clearance", "Completed - all recorded asset issues resolved"), ("Company exit status",record.status), ("Generated at",now().isoformat())],
        ["Asset / tag", "Return / transfer date", "Inspection", "Recovery"],
        [[f"{r.asset.name} / {r.asset.asset_tag}",r.returned_date,r.inspection_status,r.recovery_status] for r in rows] or [["No assigned assets","Not applicable","Not applicable","Not applicable"]],
        ["Scope: COMPANY ASSETS ONLY. This certificate does not approve or complete company-wide offboarding, final settlement, or employment termination.",
         "Department checks: "+"; ".join(f"{t.assigned_to_role or 'Department'}: {'completed' if t.is_completed else 'pending'}" for t in tasks),
         "Approved recoveries are proposals and settlement records only. No payroll deduction is created by this module."])
