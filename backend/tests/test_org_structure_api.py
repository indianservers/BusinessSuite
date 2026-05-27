from app.core.security import get_password_hash
from app.models.company import Company
from app.models.user import Role, User


def _login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_org_structure_crud_endpoints(client, db, superuser_headers):
    company = Company(name="Org API Company", legal_name="Org API Company Pvt Ltd")
    db.add(company)
    db.commit()
    db.refresh(company)

    branch = client.post(
        "/api/v1/org/branches",
        json={"organization_id": company.id, "name": "Mumbai HQ", "code": "MUM-HQ", "description": "Main branch"},
        headers=superuser_headers,
    )
    assert branch.status_code == 201
    branch_id = branch.json()["id"]

    department = client.post(
        "/api/v1/org/departments",
        json={"organization_id": company.id, "branch_id": branch_id, "name": "Engineering", "code": "ENG"},
        headers=superuser_headers,
    )
    assert department.status_code == 201
    department_id = department.json()["id"]

    designation = client.post(
        "/api/v1/org/designations",
        json={"organization_id": company.id, "department_id": department_id, "name": "Developer", "code": "DEV"},
        headers=superuser_headers,
    )
    assert designation.status_code == 201

    business_unit = client.post(
        "/api/v1/org/business-units",
        json={"organization_id": company.id, "name": "Product", "code": "PROD"},
        headers=superuser_headers,
    )
    assert business_unit.status_code == 201
    business_unit_id = business_unit.json()["id"]

    cost_center = client.post(
        "/api/v1/org/cost-centers",
        json={"organization_id": company.id, "business_unit_id": business_unit_id, "name": "Platform Cost", "code": "PLAT-COST"},
        headers=superuser_headers,
    )
    assert cost_center.status_code == 201

    location = client.post(
        "/api/v1/org/locations",
        json={"organization_id": company.id, "branch_id": branch_id, "name": "Mumbai Office", "code": "MUM-OFC"},
        headers=superuser_headers,
    )
    assert location.status_code == 201

    grade_band = client.post(
        "/api/v1/org/grade-bands",
        json={"organization_id": company.id, "name": "G5", "code": "G5", "level": 5},
        headers=superuser_headers,
    )
    assert grade_band.status_code == 201

    position = client.post(
        "/api/v1/org/positions",
        json={"organization_id": company.id, "name": "Backend Engineer", "code": "POS-BE"},
        headers=superuser_headers,
    )
    assert position.status_code == 201

    updated = client.put(
        f"/api/v1/org/departments/{department_id}",
        json={"description": "Builds business suite products"},
        headers=superuser_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Builds business suite products"

    deleted = client.delete(f"/api/v1/org/departments/{department_id}", headers=superuser_headers)
    assert deleted.status_code == 200

    visible = client.get("/api/v1/org/departments", params={"organization_id": company.id}, headers=superuser_headers)
    assert visible.status_code == 200
    assert all(item["id"] != department_id for item in visible.json())


def test_org_structure_get_all_allows_any_authenticated_user(client, db, superuser_headers):
    company = Company(name="Org Read Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    created = client.post(
        "/api/v1/org/branches",
        json={"organization_id": company.id, "name": "Read Branch", "code": "READ"},
        headers=superuser_headers,
    )
    assert created.status_code == 201

    role = Role(name="plain_employee", description="Plain employee")
    db.add(role)
    db.flush()
    user = User(
        email="plain.employee@test.com",
        hashed_password=get_password_hash("User@123456"),
        is_active=True,
        is_superuser=False,
        role_id=role.id,
    )
    db.add(user)
    db.commit()

    headers = _login(client, "plain.employee@test.com", "User@123456")
    listed = client.get("/api/v1/org/branches", params={"organization_id": company.id}, headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["code"] == "READ"

    blocked = client.post(
        "/api/v1/org/branches",
        json={"organization_id": company.id, "name": "Blocked Branch", "code": "BLOCKED"},
        headers=headers,
    )
    assert blocked.status_code == 403
