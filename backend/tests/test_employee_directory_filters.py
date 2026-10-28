from datetime import date
from app.models.employee import Employee, EmployeeEducation


def seed(db):
    for code, city, year, joined, college in [
        ("A", "Hyderabad", 2026, date(2026, 1, 1), "Alpha College"),
        ("B", "Hyderabad", 2025, date(2026, 2, 1), "Beta College"),
        ("C", "Bangalore", 2026, date(2026, 3, 1), "Alpha College"),
    ]:
        row = Employee(employee_id=code, first_name=code, last_name="Test", present_city=city,
                       date_of_joining=joined, employment_type="Intern", gender="Other", work_location="Remote")
        db.add(row); db.flush()
        db.add(EmployeeEducation(employee_id=row.id, degree="B.Tech", institution=college, pass_year=year, specialization="CSE"))
        # Multiple qualifying education rows must not duplicate employee results.
        db.add(EmployeeEducation(employee_id=row.id, degree="Diploma", institution=college, pass_year=year))
    db.commit()


def test_combined_filters_counts_sort_and_pagination(client, db, superuser_headers):
    seed(db)
    params = {"city": "hyderabad", "employment_type": "Intern", "gender": "Other", "work_location": "Remote", "sort_by": "date_of_joining", "sort_order": "desc", "per_page": 1}
    result = client.get("/api/v1/employees/", headers=superuser_headers, params=params)
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 2
    assert result.json()["items"][0]["employee_id"] == "B"
    params["page"] = 2
    assert client.get("/api/v1/employees/", headers=superuser_headers, params=params).json()["items"][0]["employee_id"] == "A"
    params.update(passout_year=2026, college="Alpha College", degree="B.Tech", specialization="CSE", page=1)
    result = client.get("/api/v1/employees/", headers=superuser_headers, params=params)
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["employee_id"] == "A"


def test_options_export_and_date_validation(client, db, superuser_headers):
    seed(db)
    options = client.get("/api/v1/employees/filter-options", headers=superuser_headers)
    assert options.status_code == 200, options.text
    assert options.json()["city"] == ["Bangalore", "Hyderabad"]
    assert options.json()["passout_year"] == [2026, 2025]
    result = client.get("/api/v1/employees/export", headers=superuser_headers,
                        params={"city": "Hyderabad", "passout_year": 2025})
    assert result.status_code == 200, result.text
    assert len(result.text.strip().splitlines()) == 2
    assert result.text.strip().splitlines()[1].startswith("B,")
    result = client.get("/api/v1/employees/", headers=superuser_headers,
                        params={"joined_from": "2026-03-01", "joined_to": "2026-01-01"})
    assert result.status_code == 422, result.text
    for params in ({"sort_by": "password"}, {"sort_order": "sql"}, {"passout_year": 0}):
        assert client.get("/api/v1/employees/", headers=superuser_headers, params=params).status_code == 422


def test_search_account_and_deleted_filters(client, db, superuser_headers):
    seed(db)
    result = client.get("/api/v1/employees/", headers=superuser_headers,
                        params={"search": "B Test", "account_status": "unlinked", "joined_from": "2026-02-01"})
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1
    row = db.query(Employee).filter_by(employee_id="B").one()
    from datetime import datetime, timezone
    row.deleted_at = datetime.now(timezone.utc); db.commit()
    result = client.get("/api/v1/employees/filter-options", headers=superuser_headers)
    assert "Beta College" not in result.json()["college"]
