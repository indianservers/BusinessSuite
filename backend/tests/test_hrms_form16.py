from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.pdfgen import canvas

from app.models.employee import Employee
from app.models.payroll import (
    EmployeeTaxDeclaration,
    EmployeeTaxDeclarationItem,
    PayrollRecord,
    PayrollRun,
    TaxDeclarationCategory,
)
from app.models.statutory_compliance import Form16Record


def _pdf_bytes() -> bytes:
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(72, 720, "TRACES Part A")
    pdf.save()
    return stream.getvalue()


def _seed_form16_employee(db):
    employee = Employee(
        employee_id="F16001",
        first_name="Form",
        last_name="Sixteen",
        pan_number="ABCDE1234F",
        date_of_joining=date(2025, 4, 1),
    )
    db.add(employee)
    db.flush()

    run = PayrollRun(month=5, year=2026, status="locked", pay_period_start=date(2026, 5, 1), pay_period_end=date(2026, 5, 31))
    db.add(run)
    db.flush()
    db.add(
        PayrollRecord(
            payroll_run_id=run.id,
            employee_id=employee.id,
            gross_salary=Decimal("100000"),
            total_deductions=Decimal("12000"),
            tds=Decimal("3500"),
            net_salary=Decimal("88000"),
        )
    )

    category = TaxDeclarationCategory(
        financial_year="2026-27",
        code="80C",
        name="Section 80C",
        section="80C",
        max_limit=Decimal("150000"),
        requires_proof=True,
    )
    db.add(category)
    db.flush()
    declaration = EmployeeTaxDeclaration(employee_id=employee.id, financial_year="2026-27", status="approved")
    db.add(declaration)
    db.flush()
    db.add(
        EmployeeTaxDeclarationItem(
            declaration_id=declaration.id,
            category_id=category.id,
            declared_amount=Decimal("150000"),
            approved_amount=Decimal("150000"),
            status="approved",
        )
    )
    db.commit()
    return employee


def test_form16_generate_upload_publish_and_download(client, db, superuser_headers):
    employee = _seed_form16_employee(db)

    generated = client.post(
        "/api/v1/hrms/form16/generate",
        json={"financialYear": "2026-27", "employeeIds": [employee.id]},
        headers=superuser_headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()[0]["status"] == "generated"
    from app.core.storage import normalize_upload_references
    assert normalize_upload_references(generated.json()[0]["partBFilePath"]).endswith("form16_part_b.pdf")
    assert Decimal(str(generated.json()[0]["taxDeducted"])) == Decimal("3500.00")
    assert Decimal(str(generated.json()[0]["taxableIncome"])) == Decimal("0.00")

    listed = client.get("/api/v1/hrms/form16?financialYear=2026-27", headers=superuser_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["employee"]["pan"] == "ABCDE1234F"

    record_id = generated.json()[0]["id"]
    uploaded = client.post(
        f"/api/v1/hrms/form16/{record_id}/upload-part-a",
        files={"file": ("part-a.pdf", _pdf_bytes(), "application/pdf")},
        headers=superuser_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert normalize_upload_references(uploaded.json()["partAFilePath"]).endswith(".pdf")
    assert normalize_upload_references(uploaded.json()["combinedFilePath"]).endswith(".pdf")

    published = client.post(f"/api/v1/hrms/form16/{record_id}/publish", headers=superuser_headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    downloaded = client.get(f"/api/v1/hrms/form16/{record_id}/download", headers=superuser_headers)
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content.startswith(b"%PDF")

    stored = db.query(Form16Record).filter(Form16Record.id == record_id).first()
    assert stored.status == "published"
