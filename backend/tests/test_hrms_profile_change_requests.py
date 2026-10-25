from datetime import date

from app.core.security import get_password_hash
from app.models.employee import Employee
from app.models.user import Role, User


def _login(client, email: str, password: str = "Pass@12345"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_employee_profile_change_request_requires_approval(client, db, superuser_headers):
    role = Role(name="employee", description="Employee")
    user = User(email="profile-change@test.com", hashed_password=get_password_hash("Pass@12345"), is_active=True, role=role)
    employee = Employee(
        employee_id="PCR-001",
        user=user,
        first_name="Profile",
        last_name="Change",
        date_of_joining=date(2025, 1, 1),
        status="Active",
        phone_number="9000000000",
        emergency_contact_name="Old Contact",
    )
    db.add_all([role, user, employee])
    db.commit()
    employee_headers = _login(client, "profile-change@test.com")

    create = client.post(
        f"/api/v1/hrms/employees/{employee.id}/change-request",
        json={
            "requestType": "Profile Update",
            "fieldChanges": {
                "phone_number": "9111111111",
                "phone_number_country_code": "+91",
                "emergency_contact_name": "New Contact",
                "marital_status": "Married",
            },
            "reason": "Updated profile data",
        },
        headers=employee_headers,
    )
    assert create.status_code == 201, create.text
    request = create.json()
    assert request["status"] == "Pending"
    assert request["old_value_json"]["phone_number"] == "9000000000"
    db.refresh(employee)
    assert employee.phone_number == "9000000000"

    approve = client.post(
        f"/api/v1/hrms/profile-change-requests/{request['id']}/approve",
        json={"remarks": "Verified", "applyChanges": True},
        headers=superuser_headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "Approved"
    db.refresh(employee)
    assert employee.phone_number == "9111111111"
    assert employee.emergency_contact_name == "New Contact"
    assert employee.marital_status == "Married"


def test_employee_cannot_create_change_request_for_other_employee(client, db):
    role = Role(name="employee", description="Employee")
    user = User(email="profile-self@test.com", hashed_password=get_password_hash("Pass@12345"), is_active=True, role=role)
    owner = Employee(employee_id="PCR-002", user=user, first_name="Self", last_name="Only", date_of_joining=date(2025, 1, 1), status="Active")
    other = Employee(employee_id="PCR-003", first_name="Other", last_name="Person", date_of_joining=date(2025, 1, 1), status="Active")
    db.add_all([role, user, owner, other])
    db.commit()
    headers = _login(client, "profile-self@test.com")

    response = client.post(
        f"/api/v1/hrms/employees/{other.id}/change-request",
        json={"fieldChanges": {"phone_number": "9222222222"}, "reason": "Not mine"},
        headers=headers,
    )
    assert response.status_code == 403
