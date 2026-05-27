from datetime import date, time, timedelta


def _create_employee_user(client, headers, code="OPS001"):
    email = f"{code.lower()}@example.com"
    response = client.post(
        "/api/v1/employees/",
        headers=headers,
        json={
            "employee_id": code,
            "first_name": "Ops",
            "last_name": "User",
            "work_email": email,
            "date_of_joining": date.today().isoformat(),
            "employment_type": "Full-time",
            "create_user_account": True,
            "user_email": email,
            "user_password": "Employee@123",
        },
    )
    assert response.status_code == 201, response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Employee@123"})
    assert login.status_code == 200, login.text
    return response.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_company_settings_update(client, superuser_headers):
    company = client.post(
        "/api/v1/company/",
        headers=superuser_headers,
        json={
            "name": "Indian Servers",
            "legal_name": "Indian Servers Pvt Ltd",
            "registration_number": "REG001",
            "cin_number": "U72900TG2026PTC000001",
            "pan_number": "ABCDE1234F",
            "working_days_per_week": 6,
            "fiscal_year_start_month": 4,
            "default_timezone": "Asia/Kolkata",
            "default_currency": "INR",
        },
    )
    assert company.status_code == 201, company.text

    settings = client.get("/api/v1/company/settings", headers=superuser_headers)
    assert settings.status_code == 200, settings.text
    assert settings.json()["cin_number"] == "U72900TG2026PTC000001"

    updated = client.put(
        f"/api/v1/company/settings?company_id={company.json()['id']}",
        headers=superuser_headers,
        json={"name": "Indian Servers", "working_days_per_week": 5, "default_currency": "INR"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["working_days_per_week"] == 5


def test_shift_roster_publish_swap_and_employee_view(client, superuser_headers):
    employee, employee_headers = _create_employee_user(client, superuser_headers, "ROSTER001")
    other_employee, _ = _create_employee_user(client, superuser_headers, "ROSTER002")

    shift_a = client.post(
        "/api/v1/attendance/shifts",
        headers=superuser_headers,
        json={"name": "Morning", "code": "M", "start_time": "09:00:00", "end_time": "18:00:00", "working_hours": "8.0"},
    )
    shift_b = client.post(
        "/api/v1/attendance/shifts",
        headers=superuser_headers,
        json={"name": "Evening", "code": "E", "start_time": "12:00:00", "end_time": "21:00:00", "working_hours": "8.0"},
    )
    assert shift_a.status_code == 201, shift_a.text
    assert shift_b.status_code == 201, shift_b.text

    roster_date = date.today() + timedelta(days=1)
    assign_a = client.post(
        "/api/v1/hrms/shift-roster/assign",
        headers=superuser_headers,
        json={"employeeId": employee["id"], "shiftId": shift_a.json()["id"], "rosterDate": roster_date.isoformat(), "status": "draft"},
    )
    assign_b = client.post(
        "/api/v1/hrms/shift-roster/assign",
        headers=superuser_headers,
        json={"employeeId": other_employee["id"], "shiftId": shift_b.json()["id"], "rosterDate": roster_date.isoformat(), "status": "draft"},
    )
    assert assign_a.status_code == 200, assign_a.text
    assert assign_b.status_code == 200, assign_b.text

    swapped = client.post(
        "/api/v1/hrms/shift-roster/swap",
        headers=superuser_headers,
        json={"firstRosterId": assign_a.json()["id"], "secondRosterId": assign_b.json()["id"]},
    )
    assert swapped.status_code == 200, swapped.text
    assert swapped.json()["swapped"] is True

    published = client.post(
        "/api/v1/hrms/shift-roster/publish",
        headers=superuser_headers,
        json={"fromDate": roster_date.isoformat(), "toDate": roster_date.isoformat(), "employeeIds": [employee["id"], other_employee["id"]]},
    )
    assert published.status_code == 200, published.text
    assert published.json()["published"] == 2

    my_roster = client.get("/api/v1/hrms/shift-roster/my", headers=employee_headers)
    assert my_roster.status_code == 200, my_roster.text
    assert len(my_roster.json()) == 1


def test_exit_asset_helpdesk_and_announcements(client, superuser_headers):
    employee, employee_headers = _create_employee_user(client, superuser_headers, "OPSFOUND001")

    exit_record = client.post(
        "/api/v1/exit/records",
        headers=superuser_headers,
        json={"employee_id": employee["id"], "exit_type": "Resignation", "resignation_date": date.today().isoformat()},
    )
    assert exit_record.status_code == 201, exit_record.text
    checklist = client.get(f"/api/v1/exit/records/{exit_record.json()['id']}/checklist", headers=superuser_headers)
    assert checklist.status_code == 200, checklist.text
    assert len(checklist.json()) >= 5
    for item in checklist.json():
        completed = client.put(f"/api/v1/exit/checklist/{item['id']}/complete?remarks=Done", headers=superuser_headers)
        assert completed.status_code == 200, completed.text
    closed = client.put(f"/api/v1/exit/records/{exit_record.json()['id']}/complete", headers=superuser_headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "Completed"

    category = client.post("/api/v1/assets/categories", headers=superuser_headers, json={"name": "Laptop"})
    assert category.status_code == 201, category.text
    asset = client.post(
        "/api/v1/assets/",
        headers=superuser_headers,
        json={"asset_tag": "LAP-001", "name": "ThinkPad", "category_id": category.json()["id"], "condition": "New"},
    )
    assert asset.status_code == 201, asset.text
    assignment = client.post(
        "/api/v1/assets/assignments",
        headers=superuser_headers,
        json={"asset_id": asset.json()["id"], "employee_id": employee["id"], "assigned_date": date.today().isoformat(), "condition_at_assignment": "New"},
    )
    assert assignment.status_code == 201, assignment.text
    acknowledged = client.put(f"/api/v1/assets/assignments/{assignment.json()['id']}/acknowledge", headers=employee_headers)
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["acknowledgement_signed"] is True

    ticket = client.post(
        "/api/v1/helpdesk/tickets/json",
        headers=employee_headers,
        json={"subject": "Need salary certificate", "description": "Please issue salary certificate.", "priority": "Medium"},
    )
    assert ticket.status_code == 201, ticket.text
    assert ticket.json()["status"] == "Open"

    announcement = client.post(
        "/api/v1/engagement/announcements",
        headers=superuser_headers,
        json={"title": "Holiday Notice", "body": "Office closed tomorrow.", "audience": "All", "is_published": True, "requires_acknowledgement": True},
    )
    assert announcement.status_code == 201, announcement.text
    ack = client.post(f"/api/v1/engagement/announcements/{announcement.json()['id']}/acknowledge", headers=employee_headers)
    assert ack.status_code == 201, ack.text
    assert ack.json()["employee_id"] == employee["id"]
