"""Live setup checks, direct API writes, and recovery boundaries."""
import pytest
from fastapi import HTTPException
from app.models.company import Company, Branch
from app.models.user import User
from app.access.models import AccessMembership, AccessPolicy
from app.access.setup import essentials, is_business_write, protect_last_company_admin, protect_administrator_account


@pytest.fixture
def scope(db, superuser_headers):
    company = db.get(Company, 1)
    if not company:
        company = Company(id=1, name="Setup test company")
        db.add(company)
    company.email = None
    company.country = "India"
    branch = Branch(company_id=1, name="Main", code="MAIN")
    db.add(branch)
    db.commit()
    return {**superuser_headers, "X-Suite-Organization":"1", "X-Suite-Branch":str(branch.id)}


def test_new_company_block_repair_write_and_deleted_detail_recovery(client, db, scope):
    response = client.get("/api/v1/access/setup", headers=scope)
    assert response.status_code == 200, response.text
    assert response.json()["ready"] is False
    assert next(i for i in response.json()["items"] if i["id"] == "company")["canRepair"]
    endpoint = "/api/v1/crm/lead-management/leads"
    payload = {"values":{"full_name":"Setup readiness lead"}}
    blocked = client.post(endpoint, headers=scope, json=payload)
    assert blocked.status_code == 409, blocked.text
    assert blocked.headers["x-suite-setup-required"] == "1"
    assert client.get(endpoint, headers=scope).status_code == 200
    repaired = client.patch("/api/v1/access/settings/company-profile", headers=scope,
                            json={"email":"office@setup.example.com"})
    assert repaired.status_code == 200, repaired.text
    assert client.get("/api/v1/access/setup", headers=scope).json()["ready"]
    created = client.post(endpoint, headers=scope, json=payload)
    assert created.status_code == 201, created.text
    db.get(Company, 1).email = None
    db.commit()
    assert not client.get("/api/v1/access/setup", headers=scope).json()["ready"]
    assert client.post(endpoint, headers=scope, json=payload).status_code == 409


def test_invalid_defaults_missing_branch_and_other_company_do_not_count(db, scope):
    company = db.get(Company, 1)
    company.email = "office@setup.example.com"
    company.default_timezone = "Invalid/Timezone"
    db.query(Branch).filter_by(company_id=1).update({"is_active":False})
    db.add(Company(id=2, name="Other", email="other@setup.example.com"))
    db.add(Branch(company_id=2, name="Foreign", code="OTHER"))
    db.commit()
    status = {i["id"]:i["ready"] for i in essentials(db, 1)}
    assert status == {"company":True, "branch":False, "defaults":False, "administrator":True}


def test_stale_branch_does_not_block_setup_or_repair(client, db, scope):
    stale = {**scope, "X-Suite-Branch":"999999"}
    assert client.get("/api/v1/access/setup", headers=stale).status_code == 200
    assert client.patch("/api/v1/access/settings/company-profile", headers=stale,
                        json={"email":"repaired@setup.example.com"}).status_code == 200


def test_no_active_branch_can_be_restored_without_a_valid_branch_selection(client, db, scope):
    branch = db.query(Branch).filter_by(company_id=1).one()
    branch.is_active = False
    db.commit()
    status = client.get("/api/v1/access/setup", headers=scope)
    assert status.status_code == 200, status.text
    assert not next(i for i in status.json()["items"] if i["id"] == "branch")["ready"]
    response = client.post(f"/api/v1/branches/{branch.id}/restore", headers=scope,
                           json={"reason":"Restore required main branch", "expected_version":0})
    assert response.status_code == 200, response.text
    status = client.get("/api/v1/access/setup", headers=scope).json()
    assert next(i for i in status["items"] if i["id"] == "branch")["ready"]


def test_missing_module_setup_only_blocks_affected_operation(client, db, scope):
    db.get(Company, 1).email = "office@setup.example.com"
    db.commit()
    response = client.post("/api/v1/employees/", headers=scope, json={})
    assert response.status_code == 409, response.text
    assert "Departments" in response.json()["detail"]
    response = client.post("/api/v1/crm/lead-management/leads", headers=scope,
                           json={"values":{"full_name":"Independent CRM lead"}})
    assert response.status_code == 201, response.text


def test_last_company_administrator_requires_replacement(db, scope):
    users = [User(email=f"setupadmin{i}@example.com", hashed_password="unused", is_active=True) for i in range(2)]
    db.add_all(users)
    db.flush()
    membership = AccessMembership(company_id=1, user_id=users[0].id, active=True, is_admin=True)
    db.add(membership)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        protect_last_company_admin(db, membership, False, False)
    assert exc.value.status_code == 409
    db.add(AccessMembership(company_id=1, user_id=users[1].id, active=True, is_admin=True))
    db.commit()
    protect_last_company_admin(db, membership, False, False)
    # A suspended replacement cannot preserve usable administrator access.
    db.add(AccessPolicy(company_id=1, user_id=users[1].id, grants={}, status="suspended"))
    db.commit()
    with pytest.raises(HTTPException):
        protect_administrator_account(db, users[0])


def test_non_admin_can_see_setup_but_cannot_repair_or_switch_company(client, db):
    from tests.test_branch_access import setup
    from app.core.security import create_access_token
    user, branch, *_ = setup(db)
    headers = {"Authorization":"Bearer " + create_access_token(user.id),
               "X-Suite-Organization":"1", "X-Suite-Branch":str(branch.id)}
    response = client.get("/api/v1/access/setup", headers=headers)
    assert response.status_code == 200, response.text
    assert not any(i["canRepair"] for i in response.json()["items"])
    response = client.patch("/api/v1/access/settings/company-profile", headers=headers,
                            json={"email":"unauthorized@example.com"})
    assert response.status_code == 403, response.text
    db.add(Company(id=2, name="Foreign setup company"))
    db.commit()
    response = client.get("/api/v1/access/setup", headers={**headers,"X-Suite-Organization":"2"})
    assert response.status_code == 403, response.text


def test_last_global_admin_account_cannot_be_suspended(db, scope):
    target = db.query(User).filter_by(is_superuser=True).one()
    with pytest.raises(HTTPException) as exc:
        protect_administrator_account(db, target)
    assert exc.value.status_code == 409


def test_profile_rejects_invalid_defaults_and_email(client, scope):
    for patch in ({"default_currency":"invalid"}, {"default_timezone":"Invalid/Zone"},
                  {"fiscal_year_start_month":13}, {"email":"invalid"}):
        response = client.patch("/api/v1/access/settings/company-profile", headers=scope, json=patch)
        assert response.status_code == 422, response.text


@pytest.mark.parametrize("method,path,blocked", [
    ("POST","/api/v1/project-management/tasks/1/complete",True),
    ("POST","/api/v1/project-management/task-workspace/tasks/1/actions",True),
    ("POST","/api/v1/power-apps/approvals/requests/1/decisions",True),
    ("POST","/api/v1/srm/inventory/stock-movements",True),
    ("POST","/api/v1/branches",False),
    ("POST","/api/v1/company/departments/",False),
    ("POST","/api/v1/payroll/setup/pay-groups",False),
    ("POST","/api/v1/attendance/shifts",False),
    ("POST","/api/v1/leave/types",False),
    ("POST","/api/v1/crm/lead-management/settings",False),
    ("POST","/api/v1/srm/inventory/warehouses",False),
    ("POST","/api/v1/crm/pipelines",False),
    ("POST","/api/v1/fam/ledgers",False),
    ("POST","/api/v1/fam/integrations/srm/post-invoice/1",True),
    ("POST","/api/v1/communication/messages",True),
    ("GET","/api/v1/employees/",False),
    ("PATCH","/api/v1/access/settings/company-profile",False),
])
def test_operation_and_repair_boundaries(method, path, blocked):
    assert is_business_write(method, path) is blocked
