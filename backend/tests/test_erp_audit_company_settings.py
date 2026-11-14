import pytest

from app.models.company import Company
from tests.rich_text_test_utils import organization_context


@pytest.mark.parametrize("field,value", [("default_timezone", "Invalid/Zone"), ("default_currency", "INVALID"), ("fiscal_year_start_month", 13), ("working_days_per_week", 0), ("name", "   "), ("default_timezone", ""), ("default_currency", "usd"), ("fiscal_year_start_month", 0), ("working_days_per_week", 8), ("default_timezone", None), ("default_currency", None), ("fiscal_year_start_month", None), ("working_days_per_week", None)])
@pytest.mark.parametrize("endpoint", ["/api/v1/company/1", "/api/v1/company/settings"])
def test_legacy_company_edits_reject_invalid_configuration_without_writing(client, db, superuser_headers, field, value, endpoint):
    row = db.get(Company, 1)
    before = getattr(row, field)
    response = client.put(endpoint, headers=superuser_headers, json={field: value})
    assert response.status_code == 422
    db.refresh(row)
    assert getattr(row, field) == before


@pytest.mark.parametrize("endpoint", ["/api/v1/company/1", "/api/v1/company/settings"])
def test_valid_company_default_edits_persist_and_partial_edits_preserve_others(client, db, superuser_headers, endpoint):
    payload = {"default_timezone": "Asia/Dubai", "default_currency": "AED", "fiscal_year_start_month": 1, "working_days_per_week": 6}
    changed = client.put(endpoint, headers=superuser_headers, json=payload)
    assert changed.status_code == 200, changed.text
    assert all(changed.json()[key] == value for key, value in payload.items())
    partial = client.put(endpoint, headers=superuser_headers, json={"city": "Audit city"})
    assert partial.status_code == 200
    assert partial.json()["city"] == "Audit city"
    assert all(partial.json()[key] == value for key, value in payload.items())


def test_branch_profile_edits_read_back_and_reject_company_reassignment(client, db, superuser_headers):
    headers = superuser_headers
    branch = client.post("/api/v1/company/branches/", headers=headers, json={"name": "Audit field office", "code": "QA-FIELD", "company_id": 1, "address": "Synthetic test address"})
    assert branch.status_code == 201, branch.text
    identity = branch.json()["id"]
    headers = {**headers, "X-Suite-Branch": str(identity)}
    changed = client.put(f"/api/v1/company/branches/{identity}", headers=headers, json={"name": "Audit renamed office", "code": "QA-RENAMED", "city": "Audit city", "email": "audit-branch@example.com"})
    assert changed.status_code == 200, changed.text
    listing = client.get("/api/v1/company/branches/", headers=headers)
    assert listing.status_code == 200
    saved = next(row for row in listing.json() if row["id"] == identity)
    assert saved["name"] == "Audit renamed office" and saved["code"] == "QA-RENAMED"
    assert saved["city"] == "Audit city" and saved["email"] == "audit-branch@example.com"
    assert saved["address"] == "Synthetic test address"
    blocked = client.put(f"/api/v1/company/branches/{identity}", headers=headers, json={"company_id": 999999})
    assert blocked.status_code == 422
    from app.models.company import Branch
    assert db.get(Branch, identity).company_id == 1
