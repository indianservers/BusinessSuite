from datetime import date
import pytest

from app.apps.interns_hub.models import InternApplication
from app.common.models import CommonPerson
from app.core.security import get_password_hash
from app.models.company import Company, Branch, Department, Designation
from app.models.employee import Employee, EmployeeChangeRequest, EmployeeEducation
from app.models.user import Role, User
from tests.test_intern_applications import application_payload  # noqa: F401


def login(client, user, portal=None):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "Profile@123456",
            **({"module": portal} if portal else {}),
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def account(db, name, employee=True, organization=1, intern=False):
    role_name = "intern" if intern else "employee" if employee else "crm_viewer"
    role = db.query(Role).filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, is_system=False)
        db.add(role)
        db.flush()
    user = User(
        email=f"{name}@example.com",
        hashed_password=get_password_hash("Profile@123456"),
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.flush()
    db.add(
        CommonPerson(
            user_id=user.id,
            organization_id=organization,
            primary_email=user.email,
            display_name=name,
            status="active",
        )
    )
    person = None
    if employee:
        person = Employee(
            employee_id=f"EMP-{name}",
            user_id=user.id,
            first_name="Profile",
            last_name=name,
            date_of_joining=date(2026, 1, 1),
            employment_type="Intern" if intern else "Full-time",
            status="Active",
            phone_number="9876543210",
            phone_number_country_code="+91",
            personal_email=user.email,
        )
        db.add(person)
    db.commit()
    return user, person


def test_approved_form_becomes_complete_profile_intern_portal_and_shared_identity(
    client, db, superuser_headers, application_payload
):
    company = db.get(Company, 1)
    if not company:
        company = Company(id=1, name="Profile Company")
        db.add(company)
        db.flush()
    branch = Branch(name="Profile HQ", company_id=1)
    db.add(branch)
    db.flush()
    department = Department(name="Profile Engineering", branch_id=branch.id)
    db.add(department)
    db.flush()
    designation = Designation(name="Profile Intern", department_id=department.id)
    db.add(designation)
    db.flush()
    manager = Employee(
        employee_id="PROFILE-MANAGER",
        first_name="HR",
        last_name="Manager",
        date_of_joining=date(2026, 1, 1),
        branch_id=branch.id,
    )
    db.add(manager)
    db.commit()
    payload = {
        **application_payload,
        "password": "Profile@123456",
        "linkedin": "https://www.linkedin.com/in/profile-person",
        "github": "https://github.com/profile-person",
        "portfolio": "https://portfolio.example.com",
    }
    response = client.post("/api/v1/interns-hub/applications", json=payload)
    assert response.status_code == 201, response.text
    application = db.query(InternApplication).filter_by(email=payload["email"]).one()
    response = client.post(
        f"/api/v1/interns-hub/admin/applications/{application.id}/decision",
        headers=superuser_headers,
        json={
            "status": "Approved",
            "branch_id": branch.id,
            "department_id": department.id,
            "designation_id": designation.id,
            "reporting_manager_id": manager.id,
            "date_of_joining": "2026-10-26",
        },
    )
    assert response.status_code == 200, response.text
    user = db.query(User).filter_by(email=payload["email"]).one()
    headers = login(client, user, "interns_hub")
    response = client.get("/api/v1/interns-hub/profile", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    values = result["values"]
    assert values["guardian_name"] == payload["parent_name"]
    assert values["current_year"] == payload["current_year"]
    assert values["college"] == payload["college"] and values["skills"] == [
        "Python",
        "React",
    ]
    assert values["github_url"] == payload["github"]
    assert (
        values["duration"] == "3 Months" and values["requested_role"] == payload["role"]
    )
    assert values["phone_number_country_code"] == "+91"
    assert len(values["education"]) == 3
    assert result["application"]["reference"] == application.reference
    assert result["application"]["status"] == "Approved"
    assert (
        "password" not in response.text
        and "TEST-ID-1234" not in response.text
        and "identity_number_encrypted" not in response.text
    )
    assert (
        client.get("/api/v1/profiles/me", headers=headers).status_code == 403
    )  # portal boundary is preserved


def test_profile_contact_edit_requests_hr_approval_and_syncs_after_approval(
    client, db, superuser_headers
):
    user, employee = account(db, "employee")
    headers = login(client, user)
    current = client.get("/api/v1/profiles/me", headers=headers).json()
    response = client.patch(
        "/api/v1/profiles/me",
        headers=headers,
        json={
            "version": current["version"],
            "values": {
                "bio": "Building useful software",
                "phone_number": "9123456789",
                "phone_number_country_code": "+91",
                "guardian_name": "Guardian Name",
            },
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["profile"]["values"]["bio"] == "Building useful software"
    assert result["profile"]["values"]["phone_number"] == "9876543210"
    assert result["pendingRequestId"]
    assert employee.phone_number == "9876543210"
    approved = client.post(
        f"/api/v1/hrms/profile-change-requests/{result['pendingRequestId']}/approve",
        headers=superuser_headers,
        json={"remarks": "Verified", "applyChanges": True},
    )
    assert approved.status_code == 200, approved.text
    profile = client.get("/api/v1/profiles/me", headers=headers).json()
    assert profile["values"]["phone_number"] == "9123456789"
    assert profile["values"]["guardian_name"] == "Guardian Name"
    assert not profile["pendingRequests"]
    assert (
        db.query(CommonPerson).filter_by(user_id=user.id).one().phone_number
        == "9123456789"
    )


def test_account_only_profile_has_editing_without_employee_or_privilege_changes(
    client, db
):
    user, _ = account(db, "account-only", employee=False)
    headers = login(client, user)
    response = client.patch(
        "/api/v1/profiles/me",
        headers=headers,
        json={
            "values": {
                "first_name": "Jamie",
                "last_name": "User",
                "bio": "CRM user",
                "skills": ["Sales"],
                "github_url": "https://github.com/jamie",
            }
        },
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["profile"]["kind"] == "user"
        and response.json()["profile"]["displayName"] == "Jamie User"
    )
    assert response.json()["pendingRequestId"] is None
    for key in [
        "role_id",
        "is_superuser",
        "loginEmail",
        "employee_id",
        "aadhaar_number",
        "account_number",
    ]:
        response = client.patch(
            "/api/v1/profiles/me", headers=headers, json={"values": {key: "forbidden"}}
        )
        assert response.status_code == 422, response.text
    assert user.is_superuser is False


def test_email_connection_is_explicit_scoped_and_case_insensitive(
    client, db, superuser_headers
):
    user, _ = account(db, "connect-me", employee=False)
    employee = Employee(
        employee_id="CONNECT-001",
        first_name="Connect",
        last_name="Person",
        personal_email=user.email.upper(),
        date_of_joining=date(2026, 1, 1),
        status="Active",
    )
    db.add(employee)
    db.commit()
    headers = login(client, user)
    assert (
        client.get("/api/v1/profiles/me", headers=headers).json()["employeeId"] is None
    )
    preview = client.get(
        f"/api/v1/profiles/users/{user.id}/connect-preview", headers=superuser_headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["candidates"][0]["employeeId"] == employee.id
    assert (
        client.post(
            f"/api/v1/profiles/users/{user.id}/connect-email",
            headers=headers,
            json={"employeeId": employee.id},
        ).status_code
        == 403
    )
    response = client.post(
        f"/api/v1/profiles/users/{user.id}/connect-email",
        headers=superuser_headers,
        json={"employeeId": employee.id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["employeeId"] == employee.id and employee.user_id == user.id


def test_profiles_and_links_cannot_cross_users_or_organizations(
    client, db, superuser_headers
):
    user, employee = account(db, "own")
    other, other_employee = account(db, "other")
    foreign, foreign_employee = account(db, "foreign", organization=2)
    headers = login(client, user)
    assert (
        client.get(f"/api/v1/profiles/users/{other.id}", headers=headers).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/profiles/users/{foreign.id}", headers=superuser_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/profiles/employees/{foreign_employee.id}",
            headers=superuser_headers,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/profiles/directory", headers=headers).status_code == 403
    response = client.get("/api/v1/profiles/directory", headers=superuser_headers)
    assert foreign.id not in {item["userId"] for item in response.json()["items"]}


def test_education_edits_keep_the_existing_row_and_academic_fields_consistent(
    client, db, superuser_headers
):
    user, employee = account(db, "education")
    row = EmployeeEducation(
        employee_id=employee.id,
        degree="B.Tech",
        institution="Old College",
        pass_year=2027,
    )
    db.add(row)
    db.commit()
    response = client.patch(
        f"/api/v1/profiles/users/{user.id}",
        headers=superuser_headers,
        json={"values": {"college": "New College", "specialization": "AI"}},
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["profile"]["values"]["education"][0]["institution"]
        == "New College"
    )
    assert db.query(EmployeeEducation).filter_by(employee_id=employee.id).count() == 1
    response = client.patch(
        f"/api/v1/profiles/users/{user.id}",
        headers=superuser_headers,
        json={
            "values": {
                "education": [
                    {"id": row.id, "degree": "B.Sc", "institution": "Updated College"}
                ]
            }
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["profile"]["values"]["degree"] == "B.Sc"
    assert response.json()["profile"]["values"]["college"] == "Updated College"


def test_stale_edits_invalid_contacts_and_foreign_education_are_rejected(
    client, db, superuser_headers
):
    user, employee = account(db, "validation")
    other, other_employee = account(db, "foreign-education")
    row = EmployeeEducation(employee_id=other_employee.id, degree="Other Degree")
    db.add(row)
    db.commit()
    path = f"/api/v1/profiles/users/{user.id}"
    version = client.get(path, headers=superuser_headers).json()["version"]
    assert (
        client.patch(
            path,
            headers=superuser_headers,
            json={"values": {"bio": "New bio"}, "version": version},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            path,
            headers=superuser_headers,
            json={"values": {"bio": "Stale bio"}, "version": version},
        ).status_code
        == 409
    )
    for values in [
        {"phone_number": "123"},
        {"linkedin_url": "javascript:alert(1)"},
        {"education": [{"id": row.id, "degree": "Wrong owner"}]},
        {"timezone": "Invalid/Timezone"},
        {"first_name": None},
    ]:
        response = client.patch(
            path, headers=superuser_headers, json={"values": values}
        )
        assert response.status_code == 422, response.text


def test_approved_application_backfill_preserves_later_profile_edits(
    client, db, superuser_headers, application_payload
):
    user, employee = account(db, "backfill")
    item = InternApplication(
        organization_id=1,
        email=user.email,
        full_name="Original Form Name",
        reference="APP-PROFILE-BACKFILL",
        password_hash="not-returned",
        identity_number_encrypted="secret-not-returned",
        identity_last4="1234",
        status="Approved",
        employee_id=employee.id,
        details={
            key: value
            for key, value in application_payload.items()
            if key not in {"password", "full_name", "email", "identity_number"}
        },
    )
    db.add(item)
    db.commit()
    path = f"/api/v1/profiles/users/{user.id}"
    response = client.get(path, headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.json()["values"]["guardian_name"] == "Parent Rao"
    assert (
        response.json()["values"]["phone_number"] == "9876543210"
    )  # canonical employee value wins
    assert (
        client.patch(
            path,
            headers=superuser_headers,
            json={"values": {"guardian_name": "Updated guardian"}},
        ).status_code
        == 200
    )
    result = client.get(path, headers=superuser_headers).json()
    assert result["values"]["guardian_name"] == "Updated guardian"
    assert result["application"]["values"]["parent_name"] == "Parent Rao"


def test_profile_photo_updates_the_same_employee_and_shared_profile(
    client, db, tmp_path, monkeypatch
):
    import io
    from PIL import Image
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    user, employee = account(db, "photo")
    headers = login(client, user)
    contents = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(contents, "PNG")
    response = client.post(
        "/api/v1/profiles/me/photo",
        headers=headers,
        files={"file": ("portrait.png", contents.getvalue(), "image/png")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["photoUrl"]
    assert employee.profile_photo_url == user.person.profile.profile_photo_url
    assert "_private/profiles/1/" in employee.profile_photo_url
    assert (
        client.post(
            "/api/v1/profiles/me/photo",
            headers=headers,
            files={"file": ("fake.png", b"not an image", "image/png")},
        ).status_code
        == 422
    )


def test_email_connection_does_not_bypass_pending_application(
    client, db, superuser_headers, application_payload
):
    user, _ = account(db, "pending-link", employee=False)
    employee = Employee(
        employee_id="PENDING-LINK",
        first_name="Pending",
        last_name="Applicant",
        personal_email=user.email,
        date_of_joining=date(2026, 1, 1),
        status="Active",
        employment_type="Intern",
    )
    db.add(employee)
    db.add(
        InternApplication(
            organization_id=1,
            email=user.email,
            full_name="Pending Applicant",
            reference="APP-PENDING-LINK",
            password_hash="hash",
            identity_number_encrypted="encrypted",
            identity_last4="1234",
            status="Pending",
            details={},
        )
    )
    db.commit()
    preview = client.get(
        f"/api/v1/profiles/users/{user.id}/connect-preview", headers=superuser_headers
    )
    assert preview.status_code == 200 and preview.json()["candidates"] == []
    assert (
        client.post(
            f"/api/v1/profiles/users/{user.id}/connect-email",
            headers=superuser_headers,
            json={"employeeId": employee.id},
        ).status_code
        == 409
    )
    assert employee.user_id is None


@pytest.fixture(autouse=True)
def _google_application_access(google_applicant):
    google_applicant('applicant@example.com')
