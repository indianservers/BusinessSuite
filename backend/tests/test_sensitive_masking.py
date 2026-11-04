from tests.rich_text_test_utils import organization_context
from datetime import date

from app.db.init_db import init_db
from app.models.employee import Employee


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_employee_sensitive_fields_are_masked_for_manager_but_visible_to_hr(client, db):
    init_db(db)

    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.phone_number = "9876543210"
    employee.personal_email = "employee.private@example.com"
    employee.date_of_birth = date(1995, 4, 12)
    employee.account_number = "123456789012"
    employee.pan_number = "ABCDE1234F"
    employee.aadhaar_number = "123456789012"
    employee.present_address = "123 Sensitive Street"
    employee.health_information = "Diabetes care notes"
    db.commit()
    db.refresh(employee)

    manager_headers = _login(client, "manager@aihrms.com", "Manager@123456")
    hr_headers = _login(client, "hr@aihrms.com", "HR@123456")

    manager_detail = client.get(f"/api/v1/employees/{employee.id}", headers=manager_headers)
    assert manager_detail.status_code == 200
    manager_data = manager_detail.json()
    assert manager_data["personal_email"].startswith("em***")
    assert manager_data["personal_email"].endswith("@example.com")
    assert manager_data["phone_number"] == "******3210"
    assert manager_data["date_of_birth"] is None
    assert manager_data["account_number"] == "********9012"
    assert manager_data["pan_number"] == "******234F"
    assert manager_data["aadhaar_number"] == "********9012"
    assert manager_data["present_address"] == "Restricted"
    assert manager_data["health_information"] == "Restricted"

    manager_list = client.get("/api/v1/employees/", headers=manager_headers)
    assert manager_list.status_code == 200
    masked_employee = next(item for item in manager_list.json()["items"] if item["id"] == employee.id)
    assert masked_employee["personal_email"].startswith("em***")
    assert masked_employee["personal_email"].endswith("@example.com")
    assert masked_employee["phone_number"] == "******3210"

    hr_detail = client.get(f"/api/v1/employees/{employee.id}", headers=hr_headers)
    assert hr_detail.status_code == 200
    hr_data = hr_detail.json()
    assert hr_data["personal_email"] == "employee.private@example.com"
    assert hr_data["phone_number"] == "9876543210"
    assert hr_data["account_number"] == "123456789012"
    assert hr_data["pan_number"] == "ABCDE1234F"
