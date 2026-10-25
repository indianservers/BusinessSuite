import pytest
from datetime import date


def test_list_employees(client, superuser_headers):
    response = client.get("/api/v1/employees/", headers=superuser_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_create_employee(client, superuser_headers, db):
    from app.models.company import Branch, Department, Designation, Company

    # Create company structure
    company = Company(name="Test Corp")
    db.add(company)
    db.flush()
    branch = Branch(name="HQ", company_id=company.id)
    db.add(branch)
    db.flush()
    dept = Department(name="Engineering", branch_id=branch.id)
    db.add(dept)
    db.flush()
    desig = Designation(name="Engineer", department_id=dept.id)
    db.add(desig)
    db.commit()

    response = client.post("/api/v1/employees/", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_joining": str(date.today()),
        "employment_type": "Full-time",
        "branch_id": branch.id,
        "department_id": dept.id,
        "designation_id": desig.id,
        "create_user_account": False,
    }, headers=superuser_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert "employee_id" in data


def test_get_employee(client, superuser_headers, db):
    from app.models.employee import Employee
    from app.models.company import Designation

    emp = Employee(
        employee_id="EMP99999",
        first_name="Jane",
        last_name="Smith",
        date_of_joining=date.today(),
    )
    db.add(emp)
    db.commit()

    response = client.get(f"/api/v1/employees/{emp.id}", headers=superuser_headers)
    assert response.status_code == 200
    assert response.json()["first_name"] == "Jane"


def test_update_employee(client, superuser_headers, db):
    from app.models.employee import Employee

    emp = Employee(
        employee_id="EMP88888",
        first_name="Alice",
        last_name="Brown",
        date_of_joining=date.today(),
    )
    db.add(emp)
    db.commit()

    response = client.put(f"/api/v1/employees/{emp.id}", json={
        "phone_number": "9876543210", "phone_number_country_code": "+91",
        "marital_status": "Single",
    }, headers=superuser_headers)
    assert response.status_code == 200
    assert response.json()["phone_number"] == "9876543210"


def test_get_employee_stats(client, superuser_headers):
    response = client.get("/api/v1/employees/stats", headers=superuser_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "active" in data


def test_employee_not_found(client, superuser_headers):
    response = client.get("/api/v1/employees/999999", headers=superuser_headers)
    assert response.status_code == 404


def test_employee_csv_import_export_with_row_errors(client, superuser_headers):
    csv_body = (
        "employee_id,first_name,last_name,date_of_joining,personal_email,phone_number,phone_number_country_code\n"
        "BULK001,Bulk,Good,2024-01-15,bulk.good@test.com,9999999999,+91\n"
        "BULK002,,Missing,2024-01-16,missing@test.com,8888888888,+91\n"
        "BULK003,Bad,Date,15-01-2024,bad.date@test.com,7777777777,+91\n"
    )

    response = client.post(
        "/api/v1/employees/import",
        files={"file": ("employees.csv", csv_body, "text/csv")},
        headers=superuser_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["created"] == 1
    assert data["failed"] == 2
    assert data["errors"][0]["row"] == 3

    exported = client.get("/api/v1/employees/export", headers=superuser_headers)
    assert exported.status_code == 200
    assert "BULK001" in exported.text
    assert "bulk.good@test.com" in exported.text


def test_employee_directory_filters_and_team_only(client, superuser_headers, db):
    from app.core.security import get_password_hash
    from app.models.company import Branch, Company, Department, Designation, WorkLocation
    from app.models.employee import Employee
    from app.models.user import Role, User

    company = Company(name=f"Directory Corp {id(db)}")
    db.add(company)
    db.flush()
    branch = Branch(name="Directory HQ", company_id=company.id)
    db.add(branch)
    db.flush()
    dept = Department(name="Directory Engineering", branch_id=branch.id)
    db.add(dept)
    db.flush()
    desig = Designation(name="Directory Engineer", department_id=dept.id)
    db.add(desig)
    db.flush()
    location = WorkLocation(name="Directory Floor", code=f"DIR{id(db)}", company_id=company.id, branch_id=branch.id)
    db.add(location)
    db.flush()

    role = Role(name=f"directory_manager_{id(db)}", description="Manager")
    db.add(role)
    db.flush()
    manager_user = User(
        email=f"directory_manager_{id(db)}@test.com",
        hashed_password=get_password_hash("Test@123"),
        is_active=True,
        role_id=role.id,
    )
    db.add(manager_user)
    db.flush()
    manager = Employee(
        employee_id=f"DIRMGR{id(db)}",
        first_name="Directory",
        last_name="Manager",
        date_of_joining=date.today(),
        user_id=manager_user.id,
    )
    db.add(manager)
    db.flush()
    reportee = Employee(
        employee_id=f"DIRREP{id(db)}",
        first_name="Directory",
        last_name="Reportee",
        preferred_display_name="Dir Reportee",
        work_email="dir.reportee@test.com",
        personal_email="personal.dir.reportee@test.com",
        phone_number="9999999999",
        office_extension="1234",
        date_of_joining=date.today(),
        branch_id=branch.id,
        department_id=dept.id,
        designation_id=desig.id,
        location_id=location.id,
        reporting_manager_id=manager.id,
        desk_code="A-101",
        skills_tags="python,fastapi,react",
        profile_completeness=80,
    )
    hidden = Employee(
        employee_id=f"DIRHID{id(db)}",
        first_name="Hidden",
        last_name="Person",
        date_of_joining=date.today(),
        directory_visibility="hidden",
    )
    db.add_all([reportee, hidden])
    db.commit()

    filtered = client.get(
        "/api/v1/employees/directory",
        params={
            "department_id": dept.id,
            "designation_id": desig.id,
            "branch_id": branch.id,
            "location_id": location.id,
            "search": "fastapi",
        },
        headers=superuser_headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["full_name"] == "Dir Reportee"
    assert items[0]["email"] == "dir.reportee@test.com"
    assert items[0]["office_extension"] == "1234"
    assert items[0]["desk_code"] == "A-101"
    assert items[0]["profile_completeness"] == 80

    login = client.post("/api/v1/auth/login", json={"email": manager_user.email, "password": "Test@123"})
    manager_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    team = client.get("/api/v1/employees/directory", params={"team_only": True}, headers=manager_headers)
    assert team.status_code == 200
    team_ids = {item["employee_id"] for item in team.json()["items"]}
    assert reportee.employee_id in team_ids
    assert hidden.employee_id not in team_ids


def test_create_employee_lifecycle_event(client, superuser_headers, db):
    from app.models.employee import Employee

    emp = Employee(
        employee_id="EMP77777",
        first_name="Ravi",
        last_name="Kumar",
        date_of_joining=date.today(),
        status="Probation",
    )
    db.add(emp)
    db.commit()

    response = client.post(
        f"/api/v1/employees/{emp.id}/lifecycle",
        json={
            "event_type": "confirmation",
            "event_date": str(date.today()),
            "to_status": "Active",
            "reason": "Probation completed",
        },
        headers=superuser_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "confirmation"
    assert data["from_status"] == "Probation"
    assert data["to_status"] == "Active"
    assert data["employee_id"] == emp.id


def test_lifecycle_event_can_apply_employee_changes(client, superuser_headers, db):
    from app.models.employee import Employee

    emp = Employee(
        employee_id="EMP66666",
        first_name="Meera",
        last_name="Shah",
        date_of_joining=date.today(),
        status="Probation",
    )
    db.add(emp)
    db.commit()

    response = client.post(
        f"/api/v1/employees/{emp.id}/lifecycle",
        json={
            "event_type": "confirmation",
            "event_date": str(date.today()),
            "to_status": "Active",
            "apply_to_employee": True,
        },
        headers=superuser_headers,
    )

    assert response.status_code == 201
    db.refresh(emp)
    assert emp.status == "Active"

    history = client.get(f"/api/v1/employees/{emp.id}/lifecycle", headers=superuser_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["from_status"] == "Probation"


def test_hr_cannot_create_employee_login_account(client, db):
    from app.db.init_db import init_db

    init_db(db)
    login = client.post("/api/v1/auth/login", json={
        "email": "hr@aihrms.com",
        "password": "HR@123456",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/api/v1/employees/", json={
        "first_name": "Login",
        "last_name": "Blocked",
        "date_of_joining": str(date.today()),
        "create_user_account": True,
        "user_email": "blocked.employee@aihrms.com",
        "user_password": "Employee@123456",
    }, headers=headers)
    assert response.status_code == 403
    assert "only admin" in response.json()["detail"].lower()
