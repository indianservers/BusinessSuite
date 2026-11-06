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
    branch = db.query(Branch).filter_by(company_id=1).first() or Branch(company_id=1, name="Main", code="MAIN")
    db.add(branch)
    db.commit()
    return {**superuser_headers, "X-Suite-Organization":"1", "X-Suite-Branch":str(branch.id)}


def test_new_company_block_repair_write_and_deleted_detail_recovery(client, db, scope):
    response = client.get("/api/v1/access/setup", headers=scope)
    assert response.status_code == 200, response.text
    assert response.json()["ready"] is False
    assert all(i["required"] and i["module"] == "company" for i in response.json()["items"])
    assert all(i["required"] is False for i in response.json()["recommendations"])
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
    branch = db.get(Branch, int(scope["X-Suite-Branch"]))
    for row in db.query(Branch).filter_by(company_id=1).all():
        row.is_active = False
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


def test_setup_guide_recommendations_are_scoped_and_optional(db, scope):
    from app.access.setup import optional_requirements
    from app.apps.crm.models import CRMLeadScoringRule
    db.add(CRMLeadScoringRule(organization_id=2, name="Foreign rule", field="source", operator="equals", is_active=True))
    db.commit()
    assert optional_requirements(db, 1, set()) == []
    checks = optional_requirements(db, 1, {"crm"})
    assert all(i["module"] == "crm" and i["required"] is False for i in checks)
    assert not next(i for i in checks if i["id"] == "crm-scoring")["ready"]
    rule = CRMLeadScoringRule(organization_id=1, name="Local rule", field="source", operator="equals", is_active=True)
    db.add(rule)
    db.commit()
    assert next(i for i in optional_requirements(db, 1, {"crm"}) if i["id"] == "crm-scoring")["ready"]
    rule.is_active = False
    db.commit()
    assert not next(i for i in optional_requirements(db, 1, {"crm"}) if i["id"] == "crm-scoring")["ready"]


def test_hrms_fam_recommendations_are_live_scoped_and_optional(db, scope):
    from datetime import date
    from app.access.setup import optional_requirements
    from app.models.attendance import Holiday
    from app.apps.fam.models import FAMCostCenter, FAMPaymentMode
    from app.branches.models import BranchOwnership
    branch_id = int(scope["X-Suite-Branch"])
    other = Company(id=2, name="Other recommendation scope")
    db.add(other)
    db.flush()
    foreign_branch = Branch(company_id=2, name="Other", code="OTHERGUIDE")
    db.add(foreign_branch)
    db.flush()
    holiday = Holiday(name="Calendar setup test", holiday_date=date(date.today().year, 1, 1))
    cost = FAMCostCenter(company_id=2, code="GUIDE", name="Guide cost center", active=True)
    payment = FAMPaymentMode(company_id=2, name="Guide transfer", type="neft", active=True)
    db.add_all([holiday, cost, payment])
    db.flush()
    owner = BranchOwnership(resource_table="holidays", resource_key=str(holiday.id), company_id=2,
                            branch_id=foreign_branch.id, source="test")
    db.add(owner)
    db.commit()
    def checks():
        return {i["id"]: i for i in optional_requirements(db, 1, {"hrms", "fam"})}
    status = checks()
    assert set(status) == {"hrms-holidays", "fam-cost-centers", "fam-payment-modes"}
    assert all(not i["ready"] and i["required"] is False for i in status.values())
    assert all(i["module"] in {"hrms", "fam"} for i in status.values())
    owner.company_id, owner.branch_id = 1, branch_id
    cost.company_id = payment.company_id = 1
    db.commit()
    assert all(i["ready"] for i in checks().values())
    holiday.holiday_date = date(date.today().year - 1, 1, 1)
    cost.active = payment.active = False
    db.commit()
    assert all(not i["ready"] for i in checks().values())
    holiday.holiday_date = date(date.today().year, 1, 1)
    holiday.is_active = False
    db.commit()
    assert not checks()["hrms-holidays"]["ready"]
    assert optional_requirements(db, 1, set()) == []


@pytest.mark.parametrize("path,title", [
    ("/api/v1/employees/", "Departments"),
    ("/api/v1/attendance/bulk-entry", "Work shifts"),
    ("/api/v1/leave/apply", "Leave types"),
    ("/api/v1/payroll/run", "Salary components"),
    ("/api/v1/payroll/runs/999999/worksheet/process", "Salary components"),
    ("/api/v1/fam/vouchers/999999/post", "Open financial year"),
])
def test_live_hrms_finance_operations_require_module_setup(client, db, scope, path, title):
    db.get(Company, 1).email = "office@setup.example.com"
    db.commit()
    payload = {"month": 5, "year": 2026, "force_run": True} if path == "/api/v1/payroll/run" else {}
    response = client.post(path, headers=scope, json=payload)
    assert response.status_code == 409, response.text
    assert response.headers["x-suite-setup-required"] == "1"
    assert title in response.json()["detail"]


def test_shared_leave_type_readiness_uses_company_ownership(client, db, scope):
    from app.access.setup import module_requirements
    from app.models.leave import LeaveType
    from app.models.security_boundary import SecurityResourceOwnership
    db.get(Company, 1).email = "office@setup.example.test"
    db.commit()
    response = client.post("/api/v1/leave/types", headers=scope, json={
        "name": "Setup leave", "code": "SETUP-LV", "days_allowed": 12})
    assert response.status_code == 201, response.text
    local = next(item for item in module_requirements(db, 1, {"hrms"}) if item["id"] == "leave-types")
    assert local["ready"]
    db.add(Company(id=2, name="Other setup company"))
    db.flush()
    assert not next(item for item in module_requirements(db, 2, {"hrms"}) if item["id"] == "leave-types")["ready"]


def test_project_setup_requires_live_project_in_company_workspace(db, scope):
    from datetime import datetime
    from app.access.setup import module_requirements
    from app.apps.project_management.models import PMSWorkspace, PMSProject

    def project_ready(company_id):
        return next(i for i in module_requirements(db, company_id, {"project_management"}) if i["id"] == "project")["ready"]

    workspace = PMSWorkspace(organization_id=1, name="Setup workspace")
    db.add(workspace)
    db.flush()
    project = PMSProject(organization_id=1, workspace_id=workspace.id, name="Setup project", project_key="SETUP")
    db.add(project)
    db.flush()
    assert project_ready(1)
    assert not project_ready(2)
    for attribute, value in [("is_archived", True), ("is_template", True), ("is_task_collection", True), ("deleted_at", datetime.now())]:
        original = getattr(project, attribute)
        setattr(project, attribute, value)
        db.flush()
        assert not project_ready(1)
        setattr(project, attribute, original)
        db.flush()
    assert project_ready(1)
