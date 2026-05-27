from app.db.init_db import init_db
from app.models.employee import Employee


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_basic_appraisal_workflow_rules(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    manager_headers = _login(client, "manager@aihrms.com", "Manager@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")

    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    manager = db.query(Employee).filter(Employee.employee_id == "DEMO-MGR-001").first()
    assert employee.reporting_manager_id == manager.id

    cycle = client.post(
        "/api/v1/performance/cycles",
        headers=admin_headers,
        json={
            "name": "FY27 Annual Appraisal",
            "cycle_type": "annual",
            "review_period_start": "2026-04-01",
            "review_period_end": "2027-03-31",
            "self_review_deadline": "2027-04-10",
            "manager_review_deadline": "2027-04-20",
        },
    )
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]

    draft_review = client.post(
        "/api/v1/performance/reviews",
        headers=employee_headers,
        json={
            "employee_id": employee.id,
            "cycle_id": cycle_id,
            "review_type": "self",
            "overall_rating": "4.0",
        },
    )
    assert draft_review.status_code == 400

    activated = client.put(f"/api/v1/performance/cycles/{cycle_id}/activate", headers=admin_headers)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    self_review = client.post(
        "/api/v1/performance/reviews",
        headers=employee_headers,
        json={
            "employee_id": employee.id,
            "cycle_id": cycle_id,
            "review_type": "self",
            "overall_rating": "4.0",
            "strengths": "Delivered payroll accuracy improvements.",
            "rating_criteria": [
                {
                    "criteria_name": "Delivery",
                    "criteria_category": "Execution",
                    "rating": "4.0",
                    "weightage": "60",
                }
            ],
        },
    )
    assert self_review.status_code == 201
    assert self_review.json()["status"] == "submitted"
    assert len(self_review.json()["rating_criteria"]) == 1

    duplicate_self_review = client.post(
        "/api/v1/performance/reviews",
        headers=employee_headers,
        json={
            "employee_id": employee.id,
            "cycle_id": cycle_id,
            "review_type": "self",
            "overall_rating": "3.5",
        },
    )
    assert duplicate_self_review.status_code == 400

    pending = client.get("/api/v1/performance/reviews/pending", headers=manager_headers)
    assert pending.status_code == 200
    assert any(item["employee_id"] == employee.id and item["cycle_id"] == cycle_id for item in pending.json())

    manager_review = client.post(
        "/api/v1/performance/reviews",
        headers=manager_headers,
        json={
            "employee_id": employee.id,
            "cycle_id": cycle_id,
            "review_type": "manager",
            "overall_rating": "4.5",
            "comments": "Strong ownership and reliable execution.",
        },
    )
    assert manager_review.status_code == 201
    review_id = manager_review.json()["id"]
    db.refresh(employee)
    assert employee.performance_rating == 4

    my_reviews = client.get("/api/v1/performance/reviews/my", headers=employee_headers)
    assert my_reviews.status_code == 200
    assert {item["review_type"] for item in my_reviews.json()} >= {"self", "manager"}

    acknowledged = client.put(f"/api/v1/performance/reviews/{review_id}/acknowledge", headers=employee_headers)
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"

    summary = client.get(f"/api/v1/performance/summary/{employee.id}", headers=manager_headers)
    assert summary.status_code == 200
    assert summary.json()["latest_performance_score"] == 4
    assert len(summary.json()["reviews"]) >= 2


def test_manager_cannot_review_non_reportee(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    manager = db.query(Employee).filter(Employee.employee_id == "DEMO-MGR-001").first()

    cycle = client.post(
        "/api/v1/performance/cycles",
        headers=admin_headers,
        json={
            "name": "FY27 Midyear",
            "cycle_type": "half_yearly",
            "review_period_start": "2026-04-01",
            "review_period_end": "2026-09-30",
        },
    )
    cycle_id = cycle.json()["id"]
    client.put(f"/api/v1/performance/cycles/{cycle_id}/activate", headers=admin_headers)

    response = client.post(
        "/api/v1/performance/reviews",
        headers=employee_headers,
        json={
            "employee_id": manager.id,
            "cycle_id": cycle_id,
            "review_type": "manager",
            "overall_rating": "4.0",
        },
    )
    assert response.status_code == 403
