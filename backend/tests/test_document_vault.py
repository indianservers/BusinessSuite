from tests.rich_text_test_utils import organization_context
from datetime import date, timedelta
from io import BytesIO
from app.models.employee import Employee
from app.models.company import Company, Branch
from app.models.document import EmployeeCertificate
from app.shared.models import ServicePolicy

BASE = "/api/v1/documents/certificates"


def employee(db, code="VAULT-1", branch=None):
    e = Employee(
        employee_id=code,
        first_name="Vault",
        last_name=code,
        date_of_joining=date(2024, 1, 1),
        branch_id=branch,
    )
    db.add(e)
    db.commit()
    return e


def upload(client, headers, e, reference="REF1", body=b"%PDF-1.4 test vault", **extra):
    return client.post(
        BASE,
        headers=headers,
        data={
            "employee_id": str(e.id),
            "title": "Degree",
            "category": "Study",
            "certificate_type": "Degree",
            "certificate_number": reference,
            **extra,
        },
        files={"file": ("degree.pdf", BytesIO(body), "application/pdf")},
    )


def test_requirements_missing_expiry_and_scoped_library(client, db, superuser_headers):
    e = employee(db)
    r = client.post(
        BASE + "/requirements",
        headers=superuser_headers,
        json={
            "title": "Degree certificate",
            "certificate_type": "Degree",
            "verification_required": True,
        },
    )
    assert r.status_code == 200, r.text
    policy = r.json()
    assert (
        client.get(BASE + "/insights", headers=superuser_headers).json()["missing"] >= 1
    )
    created = upload(
        client, superuser_headers, e, expiry_date=str(date.today() + timedelta(days=20))
    )
    assert created.status_code == 201, created.text
    identity = created.json()["id"]
    assert (
        client.get(
            BASE + "/library", params={"q": e.employee_id}, headers=superuser_headers
        ).json()["total"]
        == 1
    )
    verified = client.put(
        BASE + f"/{identity}/verify",
        headers=superuser_headers,
        json={"verification_status": "Verified", "verifier_name": "HR"},
    )
    assert verified.status_code == 200, verified.text
    state = client.get(
        BASE + "/insights", params={"employee_id": e.id}, headers=superuser_headers
    ).json()
    assert state["missing"] == 0 and state["expiring"] == 1 and state["verified"] == 1
    stale = client.post(
        BASE + "/requirements",
        params={"identity": policy["id"]},
        headers=superuser_headers,
        json={"title": "Updated", "certificate_type": "Degree", "version": 0},
    )
    assert stale.status_code == 409
    # Explicit tenant isolation applies to superusers too.
    db.add(Company(id=2, name="Other vault company"))
    db.flush()
    branch = Branch(company_id=2, name="Other", code="VLT2")
    db.add(branch)
    db.flush()
    foreign = employee(db, "FOREIGN", branch.id)
    db.add(
        EmployeeCertificate(
            employee_id=foreign.id,
            title="Foreign",
            category="Identity",
            certificate_type="Passport",
            file_url="/uploads/foreign.pdf",
        )
    )
    db.commit()
    assert client.get(BASE + "/library", headers=superuser_headers).json()["total"] == 1
    assert (
        client.get(
            BASE + "/library", headers=superuser_headers, params={"q": "FOREIGN"}
        ).json()["total"]
        == 0
    )


def test_duplicates_replacement_and_verification_reasons(client, db, superuser_headers):
    e = employee(db)
    r = upload(client, superuser_headers, e)
    assert r.status_code == 201, r.text
    identity = r.json()["id"]
    assert upload(client, superuser_headers, e).status_code == 409
    assert upload(client, superuser_headers, e, "REF2").status_code == 409
    assert (
        upload(
            client,
            superuser_headers,
            e,
            "REF3",
            body=b"%PDF bad dates",
            issue_date="2026-12-01",
            expiry_date="2026-01-01",
        ).status_code
        == 422
    )
    replaced = upload(
        client,
        superuser_headers,
        e,
        body=b"%PDF-1.4 replacement",
        replace_certificate_id=str(identity),
    )
    assert replaced.status_code == 201, replaced.text
    assert replaced.json()["id"] == identity
    assert db.query(ServicePolicy).filter_by(kind="certificate_revision").count() == 1
    versions = client.get(BASE + f"/{identity}/revisions", headers=superuser_headers)
    assert versions.status_code == 200, versions.text
    version_file = client.get(
        BASE + f"/{identity}/revisions/{versions.json()[0]['id']}/file",
        headers=superuser_headers,
    )
    assert (
        version_file.status_code == 200
        and version_file.content == b"%PDF-1.4 test vault"
    )
    assert (
        client.put(
            BASE + f"/{identity}/verify",
            headers=superuser_headers,
            json={"verification_status": "Rejected"},
        ).status_code
        == 422
    )
    r = client.put(
        BASE + f"/{identity}/verify",
        headers=superuser_headers,
        json={
            "verification_status": "Correction Required",
            "verification_notes": "Please submit a readable copy",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "Correction Required"
    download = client.get(BASE + f"/{identity}/file", headers=superuser_headers)
    assert download.status_code == 200, download.text
    assert download.content == b"%PDF-1.4 replacement"
    assert "no-store" in download.headers["cache-control"]
    bulk = client.post(
        BASE + "/download-bulk", headers=superuser_headers, json={"ids": [identity]}
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.content.startswith(b"PK")
    assert (
        client.post(
            BASE + "/download-bulk",
            headers=superuser_headers,
            json={"ids": [identity, 999999]},
        ).status_code
        == 404
    )


def test_own_employee_permissions_and_no_data(client, db):
    from app.db.init_db import init_db

    init_db(db)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@aihrms.com", "password": "Employee@123456"},
    ).json()
    headers = {"Authorization": "Bearer " + login["access_token"]}
    own = db.query(Employee).filter_by(employee_id="DEMO-EMP-001").first()
    other = employee(db, "OTHER")
    created = upload(client, headers, own)
    assert created.status_code == 201, created.text
    result = client.get(BASE + "/library", headers=headers).json()
    assert result["total"] == 1
    assert result["items"][0]["employee_id"] == own.id
    assert (
        client.get(
            BASE + "/library", params={"employee_id": other.id}, headers=headers
        ).json()["total"]
        == 0
    )
    assert (
        client.post(
            BASE + "/requirements",
            headers=headers,
            json={"title": "Denied", "certificate_type": "Degree"},
        ).status_code
        == 403
    )
    assert client.get(BASE + "/metadata-export", headers=headers).status_code == 403
    assert (
        client.post(
            BASE + "/download-bulk",
            headers=headers,
            json={"ids": [created.json()["id"]]},
        ).status_code
        == 403
    )


def test_metadata_import_changes_metadata_only_and_reports_errors(
    client, db, superuser_headers
):
    e = employee(db)
    created = upload(client, superuser_headers, e).json()
    data = f"certificate_id,title,expiry_date\n{created['id']},Updated degree,2030-01-01\n999999,Foreign,2030-01-01\n{created['id']},Duplicate,2030-01-01"
    response = client.post(
        BASE + "/imports",
        headers=superuser_headers,
        data={"process_metadata": "true"},
        files={"file": ("metadata.csv", BytesIO(data.encode()), "text/csv")},
    )
    assert response.status_code == 201, response.text
    batch = response.json()
    assert (
        batch["status"] == "Completed"
        and batch["success_count"] == 1
        and batch["failure_count"] == 2
    )
    cert = db.get(EmployeeCertificate, created["id"])
    db.refresh(cert)
    assert cert.title == "Updated degree" and cert.original_filename == "degree.pdf"
    report = client.get(
        BASE + f"/imports/{batch['id']}/report", headers=superuser_headers
    )
    assert len(report.json()["errors"]) == 2
    assert db.query(EmployeeCertificate).count() == 1
    invalid = client.post(
        BASE,
        headers=superuser_headers,
        data={
            "employee_id": e.id,
            "title": "Invalid",
            "category": "Study",
            "certificate_type": "Other",
        },
        files={"file": ("fake.pdf", BytesIO(b"not a pdf"), "application/pdf")},
    )
    assert invalid.status_code == 400


def test_reminders_are_scoped_and_deduplicated(client, db, superuser_headers):
    from app.models.user import User
    from app.models.notification import Notification

    e = employee(db)
    e.user_id = db.query(User).filter(User.is_superuser.is_(True)).first().id
    db.commit()
    response = client.post(
        BASE + "/reminders", headers=superuser_headers, json={"employee_id": e.id}
    )
    assert response.status_code == 200, response.text
    again = client.post(
        BASE + "/reminders", headers=superuser_headers, json={"employee_id": e.id}
    )
    assert again.json()["duplicate"] is True
    assert db.query(Notification).filter_by(event_type="document_reminder").count() == 1
    assert (
        client.post(
            BASE + "/reminders", headers=superuser_headers, json={"employee_id": 999999}
        ).status_code
        == 404
    )


def test_opt_in_scheduler_reuses_current_scope_and_daily_deduplication(
    client, db, superuser_headers
):
    from app.services.document_reminders import run_document_reminders
    from app.models.user import User
    from app.models.notification import Notification

    e = employee(db)
    e.user_id = db.query(User).filter(User.is_superuser.is_(True)).first().id
    db.commit()
    r = client.post(
        BASE + "/requirements",
        headers=superuser_headers,
        json={
            "title": "Passport",
            "certificate_type": "Passport",
            "reminders_enabled": True,
        },
    )
    assert r.status_code == 200, r.text
    assert run_document_reminders(db) >= 1
    assert run_document_reminders(db) == 0
    assert db.query(Notification).filter_by(event_type="document_reminder").count() == 1
