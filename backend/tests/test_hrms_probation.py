from test_identity_utils import attach_test_identity
from datetime import date

from app.core.security import get_password_hash
from app.models.employee import Employee
from app.models.user import Role, User


def test_probation_manager_review_hr_confirm_and_letter(client, superuser_headers, db):
    from app.models.company import Branch
    branch = Branch(name="Local probation branch", company_id=1)
    db.add(branch); db.flush()
    manager_role = Role(name="manager", description="Manager", is_system=True)
    db.add(manager_role)
    db.flush()
    manager_user = User(
        email="probation.manager@test.com",
        hashed_password=get_password_hash("Manager@123456"),
        is_active=True,
        role_id=manager_role.id,
    )
    db.add(manager_user)
    attach_test_identity(db, manager_user)
    db.flush()
    manager = Employee(
        employee_id="PBM001",
        branch_id=branch.id,
        first_name="Probation",
        last_name="Manager",
        date_of_joining=date(2023, 1, 1),
        user_id=manager_user.id,
        probation_status="confirmed",
    )
    db.add(manager)
    db.flush()
    employee = Employee(
        employee_id="PBE001",
        branch_id=branch.id,
        first_name="Probation",
        last_name="Employee",
        date_of_joining=date(2025, 12, 1),
        probation_period_months=6,
        probation_status="on_probation",
        reporting_manager_id=manager.id,
    )
    db.add(employee)
    db.commit()

    login = client.post("/api/v1/auth/login", json={"email": "probation.manager@test.com", "password": "Manager@123456"})
    assert login.status_code == 200
    manager_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    due = client.get("/api/v1/hrms/probation/due-list?days=180", headers=manager_headers)
    assert due.status_code == 200, due.text
    assert any(item["employeeId"] == employee.id for item in due.json())

    review = client.post(
        f"/api/v1/hrms/probation/{employee.id}/review",
        json={
            "performanceRating": 4,
            "conductRating": 5,
            "attendanceRating": 4,
            "recommendation": "confirm",
            "comments": "Ready for confirmation",
        },
        headers=manager_headers,
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "submitted"

    confirmed = client.post(
        f"/api/v1/hrms/probation/{employee.id}/confirm",
        json={"effectiveDate": "2026-05-31", "remarks": "Confirmed after review"},
        headers=superuser_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["actionType"] == "confirm"

    letter = client.get(f"/api/v1/hrms/probation/{employee.id}/letter", headers=superuser_headers)
    assert letter.status_code == 200
    assert "application/pdf" in letter.headers["content-type"]

    db.refresh(employee)
    assert employee.probation_status == "confirmed"
    assert employee.date_of_confirmation == date(2026, 5, 31)
