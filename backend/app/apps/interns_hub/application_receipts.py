"""Private application receipts with short-lived download authorization."""
from io import BytesIO
import time
from xml.sax.saxutils import escape
import jwt
from app.core.config import settings

FREE_PROGRAM_NOTICE = "Our internship program is completely free. If anyone asks you to pay a fee for this program, please report it to 9618222220."


def receipt_token(item):
    return jwt.encode({"sub": str(item.id), "reference": item.reference,
        "organization": item.organization_id, "aud": "intern-receipt",
        "iss": "interns-hub", "exp": int(time.time()) + 1800},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def receipt_pdf(item, deadline=None):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=(210*mm, 297*mm), leftMargin=22*mm,
        rightMargin=22*mm, topMargin=22*mm, bottomMargin=22*mm,
        title="Interns Hub application receipt")
    styles = getSampleStyleSheet()
    styles["BodyText"].leading = 16
    styles["BodyText"].spaceAfter = 9
    story = [Paragraph(escape(settings.INTERN_HUB_SES_BRAND), styles["Heading2"]),
        Paragraph("Internship application receipt", styles["Heading1"]), Spacer(1, 8*mm)]
    rows = [("Application reference", item.reference), ("Applicant", item.full_name),
        ("Email", item.email), ("Submitted on", item.created_at.strftime("%d %b %Y") if item.created_at else "Recorded"),
        ("Current status", item.status), ("Applied role", item.details.get("role", "")),
        ("Graduation year", item.details.get("passout_year", ""))]
    if deadline:
        rows.append(("Correction deadline", deadline.strftime("%d %b %Y") + " (India time)"))
    for label, value in rows:
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", styles["BodyText"]))
    story += [Spacer(1, 8*mm), Paragraph("Important: this program is free", styles["Heading2"]),
        Paragraph(FREE_PROGRAM_NOTICE, styles["BodyText"]), Spacer(1, 8*mm),
        Paragraph("This receipt confirms application submission. It is not an internship offer or approval. "
            "Check Application Status in Interns Hub for the latest review outcome.", styles["BodyText"])]
    document.build(story)
    return buffer.getvalue()
