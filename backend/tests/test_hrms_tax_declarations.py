from tests.rich_text_test_utils import organization_context
from datetime import date
from decimal import Decimal

from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, TaxDeclarationCycle


def test_investment_declaration_review_and_tds_projection(client, superuser_headers, db):
    employee = Employee(
        employee_id="TAX001",
        first_name="Tax",
        last_name="Saver",
        date_of_joining=date(2024, 4, 1),
    )
    db.add(employee)
    db.flush()
    db.add(
        EmployeeSalary(
            employee_id=employee.id,
            ctc=Decimal("1000000"),
            basic=Decimal("35000"),
            hra=Decimal("17500"),
            effective_from=date(2024, 4, 1),
            is_active=True,
        )
    )
    cycle = TaxDeclarationCycle(
        name="FY 2026-27",
        financial_year="2026-27",
        start_date=date(2026, 4, 1),
        end_date=date(2027, 3, 31),
        status="Open",
    )
    db.add(cycle)
    db.commit()

    categories = client.get(
        "/api/v1/hrms/tax-declaration/categories?financialYear=2026-27",
        headers=superuser_headers,
    )
    assert categories.status_code == 200, categories.text
    section_80c = next(item for item in categories.json() if item["code"] == "80C")

    created = client.post(
        "/api/v1/hrms/tax-declarations",
        json={
            "employeeId": employee.id,
            "financialYear": "2026-27",
            "items": [{"categoryId": section_80c["id"], "declaredAmount": 175000}],
        },
        headers=superuser_headers,
    )
    assert created.status_code == 200, created.text
    declaration = created.json()
    assert declaration["items"][0]["declaredAmount"] == 150000

    item_id = declaration["items"][0]["id"]
    uploaded = client.post(
        f"/api/v1/hrms/tax-declarations/{declaration['id']}/upload-proof",
        data={"declarationItemId": str(item_id)},
        files={"file": ("80c.pdf", b"%PDF-1.4\nproof", "application/pdf")},
        headers=superuser_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["items"][0]["proofs"][0]["fileName"] == "80c.pdf"

    submitted = client.post(
        f"/api/v1/hrms/tax-declarations/{declaration['id']}/submit",
        headers=superuser_headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    reviewed = client.post(
        f"/api/v1/hrms/tax-declarations/{declaration['id']}/review",
        json={"items": [{"itemId": item_id, "status": "approved", "approvedAmount": 150000, "remarks": "Verified"}]},
        headers=superuser_headers,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    assert reviewed.json()["approvedTotal"] == 150000

    projection = client.get(
        f"/api/v1/payroll/tax/projection?cycle_id={cycle.id}&employee_id={employee.id}",
        headers=superuser_headers,
    )
    assert projection.status_code == 200, projection.text
    assert Decimal(str(projection.json()["approved_amount"])) >= Decimal("150000")
    assert Decimal(str(projection.json()["projected_taxable_income"])) == Decimal("850000.00")
