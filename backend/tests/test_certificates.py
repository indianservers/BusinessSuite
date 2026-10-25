from datetime import date
from io import BytesIO

from app.db.init_db import init_db


def _create_employee(db):
    from app.models.employee import Employee

    emp = Employee(
        employee_id=f"CERT{id(db)}",
        first_name="Certificate",
        last_name="Tester",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(emp)
    db.commit()
    return emp


def test_upload_and_verify_employee_certificate(client, superuser_headers, db):
    emp = _create_employee(db)

    upload = client.post(
        "/api/v1/documents/certificates",
        data={
            "employee_id": str(emp.id),
            "category": "Study",
            "certificate_type": "Class 10",
            "title": "Class 10 Marksheet",
            "issuing_entity": "CBSE",
            "issuing_entity_type": "Board",
            "class_or_grade": "10",
            "course_or_program": "Secondary School",
            "certificate_number": "CBSE-123",
            "issue_date": "2020-05-01",
        },
        files={"file": ("class10.pdf", BytesIO(b"%PDF-1.4 certificate"), "application/pdf")},
        headers=superuser_headers,
    )
    assert upload.status_code == 201
    data = upload.json()
    assert data["category"] == "Study"
    assert data["verification_status"] == "Pending"
    from app.core.storage import normalize_upload_references
    assert normalize_upload_references(data["file_url"]).startswith(f"/uploads/certificates/{emp.id}/")

    verify = client.put(
        f"/api/v1/documents/certificates/{data['id']}/verify",
        json={
            "verification_status": "Verified",
            "verifier_name": "Rina Verifier",
            "verifier_company": "CBSE",
            "verifier_designation": "Records Officer",
            "verifier_contact": "records@example.com",
            "verification_notes": "Verified against original board record.",
        },
        headers=superuser_headers,
    )
    assert verify.status_code == 200
    verified = verify.json()
    assert verified["verification_status"] == "Verified"
    assert verified["verifier_company"] == "CBSE"
    assert verified["verified_by_user_id"] is not None
    assert verified["verified_at"] is not None


def test_certificate_import_and_export_logs(client, superuser_headers, db):
    emp = _create_employee(db)

    imported = client.post(
        "/api/v1/documents/certificates/imports",
        data={"employee_id": str(emp.id), "remarks": "Bulk study certificates"},
        files={"file": ("certificates.csv", BytesIO(b"employee_id,title\n1,Class 12"), "text/csv")},
        headers=superuser_headers,
    )
    assert imported.status_code == 201
    assert imported.json()["operation_type"] == "Import"
    from app.core.storage import normalize_upload_references
    assert normalize_upload_references(imported.json()["source_file_url"]).startswith("/uploads/certificate_imports/")

    exported = client.post(
        f"/api/v1/documents/certificates/exports?employee_id={emp.id}&total_records=4",
        headers=superuser_headers,
    )
    assert exported.status_code == 201
    assert exported.json()["operation_type"] == "Export"
    assert exported.json()["success_count"] == 4

    batches = client.get("/api/v1/documents/certificates/import-export", headers=superuser_headers)
    assert batches.status_code == 200
    assert len(batches.json()) >= 2


def test_employee_can_upload_and_list_own_certificate_only(client, db):
    init_db(db)
    from app.models.employee import Employee

    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@aihrms.com", "password": "Employee@123456"},
    )
    assert login.status_code == 200
    assert login.json()["employee_id"] == employee.id
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    upload = client.post(
        "/api/v1/documents/certificates",
        data={
            "employee_id": str(employee.id),
            "category": "Study",
            "certificate_type": "Degree",
            "title": "Degree Certificate",
        },
        files={"file": ("degree.pdf", BytesIO(b"%PDF-1.4 certificate"), "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201
    assert upload.json()["employee_id"] == employee.id

    own_list = client.get("/api/v1/documents/certificates", headers=headers)
    assert own_list.status_code == 200
    assert own_list.json()[0]["employee_id"] == employee.id

    other_emp = _create_employee(db)
    denied = client.post(
        "/api/v1/documents/certificates",
        data={
            "employee_id": str(other_emp.id),
            "category": "Study",
            "certificate_type": "Degree",
            "title": "Other Degree",
        },
        files={"file": ("other.pdf", BytesIO(b"%PDF-1.4 certificate"), "application/pdf")},
        headers=headers,
    )
    assert denied.status_code == 403
