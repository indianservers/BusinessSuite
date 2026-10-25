from tests.security_file_fixtures import uploaded_reference
from app.db.init_db import init_db
from app.models.employee import Employee


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_okr_360_competency_and_compensation_foundations(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    manager = db.query(Employee).filter(Employee.employee_id == "DEMO-MGR-001").first()

    cycle = client.post("/api/v1/performance/cycles", json={
        "name": "FY27 OKR Cycle",
        "cycle_type": "Quarterly",
        "start_date": "2026-04-01",
        "end_date": "2026-06-30",
    }, headers=admin)
    assert cycle.status_code == 201

    goal = client.post("/api/v1/performance/goals", json={
        "cycle_id": cycle.json()["id"],
        "title": "Improve payroll accuracy",
        "goal_type": "Objective",
        "weightage": "50",
        "target": "Zero critical payroll defects",
    }, headers=employee_headers)
    assert goal.status_code == 201

    check_in = client.post("/api/v1/performance/goals/check-ins", json={
        "goal_id": goal.json()["id"],
        "progress_percent": "45",
        "confidence": "On Track",
        "update_text": "Statutory validation is moving.",
    }, headers=employee_headers)
    assert check_in.status_code == 201
    assert check_in.json()["progress_percent"] == "45.00"

    template = client.post("/api/v1/performance/review-templates", json={
        "name": "360 Template",
        "template_type": "360",
        "questions": [
            {"question_text": "Collaboration", "question_type": "Rating", "competency_code": "COLLAB", "weightage": "50"},
            {"question_text": "Comments", "question_type": "Text", "order_sequence": 2},
        ],
    }, headers=admin)
    assert template.status_code == 201
    assert len(template.json()["questions"]) == 2

    feedback = client.post("/api/v1/performance/360/requests", json={
        "cycle_id": cycle.json()["id"],
        "employee_id": employee.id,
        "reviewer_id": manager.id,
        "relationship_type": "Manager",
        "due_date": "2026-06-15",
    }, headers=admin)
    assert feedback.status_code == 201
    submitted = client.put(f"/api/v1/performance/360/requests/{feedback.json()['id']}/submit", json={
        "responses_json": [{"question": "Collaboration", "rating": 4}],
        "overall_rating": "4.0",
        "comments": "Strong ownership.",
    }, headers=admin)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "Submitted"

    competency = client.post("/api/v1/performance/competencies", json={
        "code": "PAYROLL-COMPLIANCE",
        "name": "Payroll Compliance",
        "category": "Payroll",
    }, headers=admin)
    assert competency.status_code == 201
    requirement = client.post("/api/v1/performance/role-skill-requirements", json={
        "designation_id": employee.designation_id,
        "competency_id": competency.json()["id"],
        "required_level": 4,
        "importance": "Critical",
    }, headers=admin)
    assert requirement.status_code == 201
    assessment = client.post("/api/v1/performance/competency-assessments", json={
        "employee_id": employee.id,
        "competency_id": competency.json()["id"],
        "assessed_level": 2,
        "assessment_source": "Manager",
    }, headers=admin)
    assert assessment.status_code == 201
    gap = client.get(f"/api/v1/performance/employees/{employee.id}/skill-gap", headers=admin)
    assert gap.status_code == 200
    assert gap.json()["gap_count"] >= 1

    comp_cycle = client.post("/api/v1/performance/compensation/cycles", json={
        "name": "FY27 Merit",
        "financial_year": "2026-27",
        "budget_amount": "1000000",
        "budget_percent": "8",
    }, headers=admin)
    assert comp_cycle.status_code == 201
    pay_band = client.post("/api/v1/performance/compensation/pay-bands", json={
        "name": "G1 India",
        "min_ctc": "500000",
        "midpoint_ctc": "750000",
        "max_ctc": "1000000",
    }, headers=admin)
    assert pay_band.status_code == 201
    merit = client.post("/api/v1/performance/compensation/merit-recommendations", json={
        "compensation_cycle_id": comp_cycle.json()["id"],
        "employee_id": employee.id,
        "current_ctc": "600000",
        "recommended_ctc": "660000",
        "performance_rating": "4.0",
    }, headers=admin)
    assert merit.status_code == 201
    assert merit.json()["increase_percent"] == "10.00"


def test_benefit_claims_and_esop_vesting_foundations(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    plan = client.post("/api/v1/benefits/plans", json={
        "name": "Group Health Plus",
        "plan_type": "Group Health",
        "provider_name": "Demo Insure",
        "taxable": False,
    }, headers=admin)
    assert plan.status_code == 201
    policy = client.post("/api/v1/benefits/flexi-policies", json={
        "name": "Medical Reimbursement",
        "component_code": "MED",
        "annual_limit": "15000",
        "taxable_if_unclaimed": True,
    }, headers=admin)
    assert policy.status_code == 201
    allocation = client.post("/api/v1/benefits/flexi-allocations", json={
        "employee_id": employee.id,
        "policy_id": policy.json()["id"],
        "financial_year": "2026-27",
        "allocated_amount": "15000",
    }, headers=admin)
    assert allocation.status_code == 201

    claim = client.post("/api/v1/benefits/claims", json={
        "employee_id": employee.id,
        "benefit_plan_id": plan.json()["id"],
        "policy_id": policy.json()["id"],
        "claim_type": "Medical",
        "claim_date": "2026-05-02",
        "claim_amount": "5000",
        "receipt_url": uploaded_reference('benefits/receipt.pdf'),
    }, headers=admin)
    assert claim.status_code == 201
    reviewed = client.put(f"/api/v1/benefits/claims/{claim.json()['id']}/review", json={
        "status": "Approved",
        "approved_amount": "4500",
        "taxable_amount": "0",
        "tax_exempt_amount": "4500",
        "review_remarks": "Within limit",
    }, headers=admin)
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "Approved"

    esop_plan = client.post("/api/v1/benefits/esop/plans", json={
        "name": "Founders ESOP",
        "plan_code": "ESOP-2026",
        "exercise_price": "10",
        "vesting_frequency": "Annual",
        "cliff_months": 12,
        "total_vesting_months": 48,
    }, headers=admin)
    assert esop_plan.status_code == 201
    grant = client.post("/api/v1/benefits/esop/grants", json={
        "esop_plan_id": esop_plan.json()["id"],
        "employee_id": employee.id,
        "grant_date": "2026-01-01",
        "granted_units": "400",
    }, headers=admin)
    assert grant.status_code == 201
    vesting = client.get(f"/api/v1/benefits/esop/grants/{grant.json()['id']}/vesting", headers=admin)
    assert vesting.status_code == 200
    assert len(vesting.json()) == 4
