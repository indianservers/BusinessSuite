from datetime import date


def test_employee_creation_auto_starts_onboarding(client, superuser_headers):
    template_response = client.post(
        "/api/v1/onboarding/templates",
        headers=superuser_headers,
        json={
            "name": "Default full-time onboarding",
            "description": "Standard joining checklist",
            "applicable_for": "full_time",
            "is_active": True,
        },
    )
    assert template_response.status_code == 201
    template_id = template_response.json()["id"]

    task_response = client.post(
        f"/api/v1/onboarding/templates/{template_id}/tasks",
        headers=superuser_headers,
        json={
            "task_name": "Upload ID proof",
            "description": "Submit required joining document",
            "category": "document",
            "due_day_offset": 1,
            "assigned_to_role": "employee",
            "is_mandatory": True,
            "order_index": 1,
        },
    )
    assert task_response.status_code == 201

    employee_response = client.post(
        "/api/v1/employees/",
        headers=superuser_headers,
        json={
            "employee_id": "ONB001",
            "first_name": "New",
            "last_name": "Joiner",
            "work_email": "new.joiner@example.com",
            "date_of_joining": str(date.today()),
            "employment_type": "Full-time",
            "create_user_account": True,
            "user_email": "new.joiner@example.com",
            "user_password": "Joiner@123",
        },
    )
    assert employee_response.status_code == 201
    employee_id = employee_response.json()["id"]

    onboarding_response = client.get(f"/api/v1/onboarding/{employee_id}", headers=superuser_headers)
    assert onboarding_response.status_code == 200
    onboarding = onboarding_response.json()
    assert onboarding["employee_id"] == employee_id
    assert onboarding["template_id"] == template_id
    assert onboarding["completion_percentage"] == 0
    assert len(onboarding["tasks"]) == 1
    assert onboarding["tasks"][0]["task_name"] == "Upload ID proof"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "new.joiner@example.com", "password": "Joiner@123"},
    )
    assert login.status_code == 200
    employee_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    my_response = client.get("/api/v1/onboarding/my", headers=employee_headers)
    assert my_response.status_code == 200
    task_id = my_response.json()["tasks"][0]["id"]

    complete_response = client.put(
        f"/api/v1/onboarding/tasks/{task_id}/complete",
        headers=employee_headers,
        json={"notes": "Uploaded"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    updated = client.get("/api/v1/onboarding/my", headers=employee_headers)
    assert updated.status_code == 200
    assert updated.json()["completion_percentage"] == 100
    assert updated.json()["status"] == "completed"


def test_skip_task_requires_reason(client, superuser_headers):
    template = client.post(
        "/api/v1/onboarding/templates",
        headers=superuser_headers,
        json={"name": "Intern onboarding", "applicable_for": "intern"},
    )
    assert template.status_code == 201
    template_id = template.json()["id"]
    client.post(
        f"/api/v1/onboarding/templates/{template_id}/tasks",
        headers=superuser_headers,
        json={"task_name": "Meet buddy", "assigned_to_role": "employee"},
    )
    employee = client.post(
        "/api/v1/employees/",
        headers=superuser_headers,
        json={
            "employee_id": "ONB002",
            "first_name": "Intern",
            "last_name": "User",
            "date_of_joining": str(date.today()),
            "employment_type": "Intern",
            "create_user_account": False,
        },
    )
    assert employee.status_code == 201
    onboarding = client.get(f"/api/v1/onboarding/{employee.json()['id']}", headers=superuser_headers)
    task_id = onboarding.json()["tasks"][0]["id"]

    denied = client.put(
        f"/api/v1/onboarding/tasks/{task_id}/skip",
        headers=superuser_headers,
        json={},
    )
    assert denied.status_code == 422

    skipped = client.put(
        f"/api/v1/onboarding/tasks/{task_id}/skip",
        headers=superuser_headers,
        json={"reason": "Handled offline"},
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
