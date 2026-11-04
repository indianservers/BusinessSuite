from tests.rich_text_test_utils import organization_context
from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from app.models.employee import Employee


def _create_employee(db):
    emp = Employee(
        employee_id=f"DOC{id(db)}",
        first_name="Doc",
        last_name="Owner",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(emp)
    db.commit()
    return emp


def test_employee_document_expiry_and_verification(client, superuser_headers, db):
    emp = _create_employee(db)
    expiry = date.today() + timedelta(days=20)

    upload = client.post(
        f"/api/v1/employees/{emp.id}/documents",
        data={
            "document_type": "Passport",
            "document_name": "Passport scan",
            "document_number": "P1234567",
            "expiry_date": expiry.isoformat(),
        },
        files={"file": ("passport.pdf", BytesIO(b"%PDF-1.4 doc"), "application/pdf")},
        headers=superuser_headers,
    )
    assert upload.status_code == 201
    document = upload.json()
    assert document["verification_status"] == "Pending"

    expiring = client.get("/api/v1/employees/documents/expiring?days=30", headers=superuser_headers)
    assert expiring.status_code == 200
    assert any(item["id"] == document["id"] for item in expiring.json())

    verified = client.put(
        f"/api/v1/employees/{emp.id}/documents/{document['id']}/verify",
        json={
            "verification_status": "Verified",
            "verifier_name": "HR Ops",
            "verifier_company": "Indian Servers",
            "verification_notes": "Matched against original.",
        },
        headers=superuser_headers,
    )
    assert verified.status_code == 200
    assert verified.json()["is_verified"] is True
    assert verified.json()["verifier_company"] == "Indian Servers"


def test_company_policy_versioning(client, superuser_headers):
    policy = client.post(
        "/api/v1/documents/policies",
        json={
            "title": "Leave Policy",
            "category": "HR",
            "content": "Version 1",
            "version": "1.0",
            "effective_date": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
            "is_published": True,
        },
        headers=superuser_headers,
    )
    assert policy.status_code == 201
    policy_id = policy.json()["id"]

    new_version = client.post(
        f"/api/v1/documents/policies/{policy_id}/versions",
        json={
            "version": "1.1",
            "content": "Version 1.1",
            "change_summary": "Added approval SLA.",
        },
        headers=superuser_headers,
    )
    assert new_version.status_code == 201
    assert new_version.json()["version"] == "1.1"

    versions = client.get(f"/api/v1/documents/policies/{policy_id}/versions", headers=superuser_headers)
    assert versions.status_code == 200
    assert {item["version"] for item in versions.json()} == {"1.0", "1.1"}
