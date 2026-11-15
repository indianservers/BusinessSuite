from datetime import date, datetime, timezone

from app.db.init_db import init_db
from app.models.company import Branch, Company, Department, Designation
from app.models.employee import Employee
from app.models.user import User


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_core_concepts_foundations_work(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    branch = db.get(Branch, employee.branch_id)
    company = db.get(Company, branch.company_id)
    department = db.get(Department, employee.department_id)
    designation = db.get(Designation, employee.designation_id)

    business_unit = client.post("/api/v1/company/business-units", json={
        "name": "Product Engineering", "code": "BU-ENG", "company_id": company.id,
    }, headers=admin)
    assert business_unit.status_code == 201, business_unit.text

    cost_center = client.post("/api/v1/company/cost-centers", json={
        "name": "Platform Cost Center", "code": "CC-PLAT", "company_id": company.id,
        "business_unit_id": business_unit.json()["id"], "budget_amount": "5000000",
    }, headers=admin)
    assert cost_center.status_code == 201

    location = client.post("/api/v1/company/locations", json={
        "name": "Hyderabad HQ", "code": "LOC-HYD", "company_id": company.id,
        "branch_id": branch.id, "city": "Hyderabad", "state": "Telangana",
    }, headers=admin)
    assert location.status_code == 201

    grade = client.post("/api/v1/company/grade-bands", json={
        "name": "Senior", "code": "G5", "level": 5, "min_ctc": "1200000", "max_ctc": "2400000",
    }, headers=admin)
    assert grade.status_code == 201

    family = client.post("/api/v1/company/job-families", json={
        "name": "Engineering", "code": "JF-ENG",
    }, headers=admin)
    assert family.status_code == 201

    profile = client.post("/api/v1/company/job-profiles", json={
        "title": "Senior Backend Engineer", "code": "JP-SBE",
        "job_family_id": family.json()["id"], "grade_band_id": grade.json()["id"],
        "required_skills_json": ["Python", "FastAPI"],
    }, headers=admin)
    assert profile.status_code == 201

    position = client.post("/api/v1/company/positions", json={
        "position_code": "POS-ENG-001",
        "title": "Senior Backend Engineer",
        "company_id": company.id,
        "business_unit_id": business_unit.json()["id"],
        "cost_center_id": cost_center.json()["id"],
        "location_id": location.json()["id"],
        "department_id": department.id,
        "designation_id": designation.id,
        "job_profile_id": profile.json()["id"],
        "grade_band_id": grade.json()["id"],
        "incumbent_employee_id": employee.id,
        "status": "Filled",
        "budgeted_ctc": "1800000",
    }, headers=admin)
    assert position.status_code == 201

    hierarchy = client.get("/api/v1/company/manager-hierarchy/validate", headers=admin)
    assert hierarchy.status_code == 200
    assert hierarchy.json()["valid"] is True

    plan = client.post("/api/v1/company/headcount-plans", json={
        "name": "FY Engineering Plan", "financial_year": "2026-27", "company_id": company.id,
        "business_unit_id": business_unit.json()["id"], "department_id": department.id,
        "planned_headcount": 10, "approved_headcount": 8, "planned_budget": "12000000",
    }, headers=admin)
    assert plan.status_code == 201
    approved = client.put(f"/api/v1/company/headcount-plans/{plan.json()['id']}/approve", headers=admin)
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"

    change = client.post("/api/v1/employees/change-requests", json={
        "employee_id": employee.id,
        "request_type": "Org Assignment",
        "effective_date": date(2026, 5, 2).isoformat(),
        "field_changes_json": {
            "business_unit_id": business_unit.json()["id"],
            "cost_center_id": cost_center.json()["id"],
            "location_id": location.json()["id"],
            "grade_band_id": grade.json()["id"],
            "position_id": position.json()["id"],
            "worker_type": "Employee",
        },
        "reason": "Move to approved position",
    }, headers=admin)
    assert change.status_code == 201
    reviewed = client.put(f"/api/v1/employees/change-requests/{change.json()['id']}/review", json={
        "status": "Approved", "review_remarks": "Approved",
    }, headers=admin)
    assert reviewed.status_code == 200
    db.refresh(employee)
    assert employee.position_id == position.json()["id"]

    user = db.query(User).filter(User.email == "employee@aihrms.com").first()
    session = client.post("/api/v1/auth/sessions", json={
        "user_id": user.id,
        "session_token_hash": "hash-demo",
        "device_name": "Chrome Windows",
        "trusted_device": True,
        "expires_at": datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat(),
    }, headers=admin)
    assert session.status_code == 201

    mfa = client.post("/api/v1/auth/mfa-methods", json={
        "user_id": user.id, "method_type": "Email OTP", "email": user.email, "is_primary": True,
    }, headers=admin)
    assert mfa.status_code == 201
    verified_mfa = client.put(f"/api/v1/auth/mfa-methods/{mfa.json()['id']}/verify", headers=admin)
    assert verified_mfa.status_code == 200
    assert verified_mfa.json()["is_verified"] is True

    policy = client.post("/api/v1/auth/password-policies", json={
        "name": "Default Enterprise Policy", "min_length": 10, "require_symbol": True,
    }, headers=admin)
    assert policy.status_code == 201

    credential = client.post("/api/v1/enterprise/integration-credentials", json={
        "provider": "Zoho Books", "credential_name": "Payroll GL", "secret_ref": "secret://zoho/books",
    }, headers=admin)
    assert credential.status_code == 201

    webhook = client.post("/api/v1/enterprise/webhooks", json={
        "name": "Payroll Approved", "event_type": "payroll.approved", "target_url": "https://example.com/webhook",
    }, headers=admin)
    assert webhook.status_code == 201

    event = client.post("/api/v1/enterprise/integration-events", json={
        "subscription_id": webhook.json()["id"], "event_type": "payroll.approved", "payload_json": {"run_id": 1},
    }, headers=admin)
    assert event.status_code == 201

    consent = client.post("/api/v1/enterprise/consents", json={
        "employee_id": employee.id, "consent_type": "BGV", "purpose": "Employment verification",
    }, headers=admin)
    assert consent.status_code == 201
    revoked = client.put(f"/api/v1/enterprise/consents/{consent.json()['id']}/revoke", headers=admin)
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "Revoked"

    privacy = client.post("/api/v1/enterprise/privacy-requests", json={
        "employee_id": employee.id, "request_type": "Access", "requested_by_email": employee.personal_email,
    }, headers=admin)
    assert privacy.status_code == 201
    closed = client.put(f"/api/v1/enterprise/privacy-requests/{privacy.json()['id']}", json={
        "status": "Closed", "resolution_notes": "Shared profile export",
    }, headers=admin)
    assert closed.status_code == 200
    assert closed.json()["closed_at"] is not None

    retention = client.post("/api/v1/enterprise/retention-policies", json={
        "module": "employees", "record_type": "employee_documents", "retention_days": 2555,
        "legal_basis": "Employment records retention",
    }, headers=admin)
    assert retention.status_code == 201

    hold = client.post("/api/v1/enterprise/legal-holds", json={
        "name": "Employee Dispute Hold", "module": "employees", "entity_type": "employee", "entity_id": employee.id,
    }, headers=admin)
    assert hold.status_code == 201

    metric = client.post("/api/v1/enterprise/metrics", json={
        "name": "Attrition Rate", "code": "ATTRITION_RATE", "module": "employees",
        "formula_json": {"numerator": "exits", "denominator": "average_headcount"},
    }, headers=admin)
    assert metric.status_code == 201
