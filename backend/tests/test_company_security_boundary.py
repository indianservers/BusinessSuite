import pytest
from fastapi import HTTPException
from sqlalchemy import text
from app.core.security import create_access_token
from app.core.tenant_boundary import install
from app.models.user import User, Role, Permission
from app.models.company import Company
from app.apps.crm.models import CRMLead
from app.apps.project_management.models import PMSProject, PMSTask, PMSComment
from tests.tenant_test_utils import assign_company


@pytest.fixture
def tenants(db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Company Alpha"))
    db.add(Company(id=2, name="Company Beta"))
    permissions = []
    for name in [
        "company_view",
        "company_manage",
        "crm_view",
        "crm_manage",
        "pms_admin",
        "pms_view",
        "employee_view",
        "portal_manage",
    ]:
        permission = Permission(
            name=name,
            module="crm"
            if name.startswith("crm")
            else "project_management"
            if name.startswith("pms")
            else "company",
        )
        db.add(permission)
        permissions.append(permission)
    admin = Role(name="pms_org_admin", permissions=permissions)
    viewer = Role(
        name="crm_viewer",
        permissions=[
            p for p in permissions if p.name in {"company_view", "crm_view", "pms_view"}
        ],
    )
    db.add_all([admin, viewer])
    db.flush()
    users = [
        User(
            email="alpha@example.com",
            hashed_password="unused",
            role_id=admin.id,
            is_active=True,
        ),
        User(
            email="beta@example.com",
            hashed_password="unused",
            role_id=admin.id,
            is_active=True,
        ),
        User(
            email="viewer@example.com",
            hashed_password="unused",
            role_id=viewer.id,
            is_active=True,
        ),
    ]
    db.add_all(users)
    db.flush()
    for user, company in zip(users, [1, 2, 1]):
        assign_company(db, user, company)
    leads = [
        CRMLead(
            organization_id=company,
            first_name=name,
            full_name=name,
            owner_user_id=users[company - 1].id,
        )
        for company, name in [(1, "Alpha private lead"), (2, "Beta private lead")]
    ]
    projects = [
        PMSProject(
            organization_id=company,
            name=name,
            project_key=name[:4],
            manager_user_id=users[company - 1].id,
        )
        for company, name in [(1, "Alpha project"), (2, "Beta project")]
    ]
    db.add_all(leads + projects)
    db.flush()
    tasks = [
        PMSTask(
            project_id=project.id,
            title=project.name + " task",
            task_key=f"TASK-{index + 1}",
            reporter_user_id=users[index].id,
        )
        for index, project in enumerate(projects)
    ]
    db.add_all(tasks)
    db.flush()
    comments = [
        PMSComment(
            task_id=task.id,
            author_user_id=users[index].id,
            body=f"private comment {index}",
        )
        for index, task in enumerate(tasks)
    ]
    db.add_all(comments)
    db.commit()
    headers = [
        {"Authorization": "Bearer " + create_access_token(user.id)} for user in users
    ]
    return dict(
        users=users,
        leads=leads,
        projects=projects,
        tasks=tasks,
        comments=comments,
        headers=headers,
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/company/",
        "/api/v1/users/search",
        "/api/v1/crm/leads",
        "/api/v1/project-management/projects",
        "/api/v1/project-management/module-info",
        "/api/v1/crm/module-info",
        "/api/v1/interns-hub/me",
    ],
)
def test_private_endpoints_require_authentication(client, path):
    assert client.get(path).status_code in {401, 403}


def test_company_discovery_and_switching_are_membership_checked(client, tenants):
    headers = tenants["headers"][0]
    result = client.get("/api/v1/company/", headers=headers)
    assert result.status_code == 200, result.text
    assert [row["id"] for row in result.json()] == [1]
    for query in ["?company_id=2", "?company_id=999999"]:
        assert (
            client.get("/api/v1/company/settings" + query, headers=headers).status_code
            == 404
        )
    assert (
        client.get(
            "/api/v1/company/", headers={**headers, "X-Suite-Organization": "2"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/company/", headers={**headers, "X-Suite-Organization": "garbage"}
        ).status_code
        == 403
    )


def test_crm_lists_search_exports_and_guessed_ids_cannot_leak(client, tenants):
    headers = tenants["headers"][0]
    for path in [
        "/api/v1/crm/leads",
        "/api/v1/crm/leads?search=Beta",
        "/api/v1/crm/leads/export",
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert "Beta private lead" not in response.text
    own, foreign = tenants["leads"]
    assert client.get(f"/api/v1/crm/leads/{own.id}", headers=headers).status_code == 200
    assert (
        client.get(f"/api/v1/crm/leads/{foreign.id}", headers=headers).status_code
        == 404
    )


def test_pms_nested_resources_and_atomic_bulk_are_scoped(client, db, tenants):
    headers = tenants["headers"][0]
    own, foreign = tenants["tasks"]
    for task in [foreign]:
        for suffix in ["", "/comments", "/attachments"]:
            assert client.get(
                f"/api/v1/project-management/tasks/{task.id}{suffix}", headers=headers
            ).status_code in {403, 404}
    response = client.patch(
        "/api/v1/project-management/tasks/bulk",
        headers=headers,
        json={"task_ids": [own.id, foreign.id], "priority": "High"},
    )
    assert response.status_code in {403, 404}, response.text
    db.expire_all()
    assert db.get(PMSTask, own.id).priority != "High"
    own_response = client.patch(
        "/api/v1/project-management/tasks/bulk",
        headers=headers,
        json={"task_ids": [own.id], "priority": "High"},
    )
    assert own_response.status_code == 200, own_response.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 9191),
        ("organization_id", 2),
        ("created_by", 2),
        ("is_superuser", True),
        ("role_id", 1),
        ("paid_amount", 100000),
    ],
)
def test_crm_server_owned_fields_are_not_writable(client, tenants, field, value):
    response = client.put(
        f"/api/v1/crm/leads/{tenants['leads'][0].id}",
        headers=tenants["headers"][0],
        json={field: value},
    )
    assert response.status_code == 422, response.text


def test_viewer_cannot_escalate_privileges_or_write(client, tenants):
    headers = tenants["headers"][2]
    response = client.put(
        f"/api/v1/crm/leads/{tenants['leads'][0].id}",
        headers=headers,
        json={"first_name": "Changed"},
    )
    assert response.status_code == 403
    assert (
        client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "email": "attacker@example.com",
                "password": "ExamplePassword123!",
                "is_superuser": True,
            },
        ).status_code
        == 403
    )


def test_orm_boundary_covers_identity_map_children_and_raw_queries(db, tenants):
    user = tenants["users"][0]
    foreign = tenants["tasks"][1]
    assert db.get(PMSTask, foreign.id) is foreign  # Deliberately preload before guard.
    cleanup = install(db, user, 1)
    try:
        assert db.get(PMSTask, foreign.id) is None
        assert [row.id for row in db.query(PMSTask).all()] == [tenants["tasks"][0].id]
        assert [row.id for row in db.query(PMSComment).all()] == [
            tenants["comments"][0].id
        ]
        assert db.query(CRMLead).count() == 1
        with pytest.raises(HTTPException):
            db.execute(text("SELECT * FROM crm_leads"))
    finally:
        cleanup()


def test_unknown_membership_denies_private_access(client, db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Alpha"))
    user = User(
        email="unassigned@example.com", hashed_password="unused", is_active=True
    )
    db.add(user)
    db.commit()
    response = client.get(
        "/api/v1/users/search",
        headers={"Authorization": "Bearer " + create_access_token(user.id)},
    )
    assert response.status_code == 403


def test_no_private_api_is_accidentally_public():
    from app.main import app
    from app.core.route_policy import is_public, dependency_names
    from fastapi.routing import APIRoute

    def walk(router, prefix=""):
        for route in router.routes:
            if hasattr(route, "original_router"):
                yield from walk(
                    route.original_router, prefix + route.include_context.prefix
                )
            elif isinstance(route, APIRoute):
                yield prefix + route.path, route

    inspected = 0
    for path, route in walk(app.router):
        if not path.startswith("/api/v1/") or path == "/api/v1/files/blob":
            continue
        inspected += 1
        assert is_public(path) or "get_current_user" in set(
            dependency_names(route.dependant)
        ), path
    assert inspected > 2000


def test_foreign_composite_key_assignment_is_rejected(db, tenants):
    from app.apps.project_management.models import PMSTaskAssignee

    cleanup = install(db, tenants["users"][0], 1)
    try:
        db.add(
            PMSTaskAssignee(
                task_id=tenants["tasks"][1].id, user_id=tenants["users"][0].id
            )
        )
        with pytest.raises(HTTPException):
            db.flush()
    finally:
        cleanup()


def test_legacy_settings_have_transactional_company_ownership(db, tenants):
    from app.apps.admin_security.models import AdminProfile

    profile = AdminProfile(name="Unclassified old profile")
    db.add(profile)
    db.flush()
    # No safe company inference is possible with two companies.
    cleanup = install(db, tenants["users"][0], 1)
    db.info["shared_actor"] = (tenants["users"][0].id, 1)
    try:
        assert db.query(AdminProfile).all() == []
        owned = AdminProfile(name="Alpha-owned profile")
        db.add(owned)
        db.flush()
        assert [row.id for row in db.query(AdminProfile).all()] == [owned.id]
    finally:
        db.info.pop("shared_actor", None)
        cleanup()
    cleanup = install(db, tenants["users"][1], 2)
    try:
        assert db.query(AdminProfile).all() == []
    finally:
        cleanup()


def test_other_modules_use_the_same_company_boundary(db, tenants):
    from app.apps.srm.models import SRMInvoice
    from app.apps.fam.models import FAMCompanyFinancialSettings
    from app.apps.automation.models import AutomationWorkflow
    from app.apps.communication.models import CommunicationEmailMessage
    from app.models.document import CompanyPolicy

    models = [
        SRMInvoice,
        FAMCompanyFinancialSettings,
        AutomationWorkflow,
        CommunicationEmailMessage,
        CompanyPolicy,
    ]
    for company in [1, 2]:
        db.add(SRMInvoice(organization_id=company, invoice_number=f"SEC-{company}"))
        db.add(FAMCompanyFinancialSettings(company_id=company))
        db.add(
            AutomationWorkflow(
                organization_id=company,
                name=f"Workflow {company}",
                module_name="crm",
                record_type="lead",
                trigger_type="manual",
            )
        )
        db.add(
            CommunicationEmailMessage(
                organization_id=company,
                related_record_type="lead",
                related_record_id=company,
                to_email=f"recipient{company}@example.com",
                subject=f"Private {company}",
                body="Test",
            )
        )
        db.add(
            CompanyPolicy(organization_id=company, title=f"Private policy {company}")
        )
    db.flush()
    cleanup = install(db, tenants["users"][0], 1)
    try:
        for model in models:
            rows = db.query(model).all()
            assert len(rows) == 1, model.__tablename__
            assert (
                getattr(
                    rows[0], "organization_id", getattr(rows[0], "company_id", None)
                )
                == 1
            )
    finally:
        cleanup()


def test_signed_file_references_cannot_be_rebound_to_a_different_actor_or_company(
    db, tenants, monkeypatch, tmp_path
):
    from app.core.config import settings
    from app.core.audit_context import context, set_audit_actor
    from app.core.storage import signed_file_url, normalize_upload_references

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    user = tenants["users"][0]
    user.organization_id = 1
    token = context.set({})
    try:
        set_audit_actor(user)
        url = signed_file_url(str(tmp_path / "private.txt"))
    finally:
        context.reset(token)
    assert (
        normalize_upload_references(url, db=db, actor_id=user.id, company_id=1)
        == "/uploads/private.txt"
    )
    with pytest.raises(HTTPException):
        normalize_upload_references(
            url, db=db, actor_id=tenants["users"][1].id, company_id=2
        )
    with pytest.raises(HTTPException):
        normalize_upload_references(url, db=db, actor_id=user.id, company_id=2)


def test_background_work_rechecks_membership_and_permissions(db, tenants):
    from app.access.service import background_scope

    user = tenants["users"][0]
    user.organization_id = 2
    with pytest.raises(HTTPException):
        with background_scope(db, user, "project_management", "edit"):
            raise AssertionError("Unauthorized job ran")
    user.organization_id = 1
    with background_scope(db, user, "project_management", "view"):
        assert db.query(PMSProject).count() == 1


def test_customer_portal_is_company_scoped_even_with_a_tainted_old_link(
    client, db, tenants
):
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.models import SRMInvoice
    from app.apps.saas.models import PortalCustomerLink

    customers = [
        CRMCompany(name=f"Customer {index}", organization_id=index) for index in [1, 2]
    ]
    db.add_all(customers)
    db.flush()
    for index, customer in enumerate(customers, 1):
        db.add(
            SRMInvoice(
                organization_id=index,
                customer_id=customer.id,
                invoice_number=f"PORTAL-{index}",
            )
        )
    db.commit()
    response = client.post(
        "/api/v1/portals/invite",
        headers=tenants["headers"][0],
        json={
            "email": "portal-alpha@example.com",
            "display_name": "Alpha customer",
            "portal_type": "customer",
            "customer_id": customers[0].id,
        },
    )
    assert response.status_code == 201, response.text
    invitation = response.json()
    db.add(
        PortalCustomerLink(
            portal_user_id=invitation["id"], customer_id=customers[1].id, active=True
        )
    )
    db.commit()
    headers = {"X-Portal-Session": invitation["one_time_session_token"]}
    response = client.get("/api/v1/customer-portal/invoices", headers=headers)
    assert response.status_code == 200, response.text
    assert "PORTAL-1" in response.text and "PORTAL-2" not in response.text
    assert client.get("/api/v1/customer-portal/me", headers=headers).json()[
        "customer_ids"
    ] == [customers[0].id]
    assert (
        client.post(
            "/api/v1/customer-portal/quotes/123/accept", headers=headers
        ).status_code
        == 403
    )
    response = client.post(
        "/api/v1/portals/invite",
        headers=tenants["headers"][0],
        json={
            "email": "forged-link@example.com",
            "display_name": "Forged",
            "portal_type": "customer",
            "customer_id": customers[1].id,
        },
    )
    assert response.status_code == 404


def test_central_permission_policy_and_company_guard_compose(client, db, tenants):
    from app.access.models import AccessPolicy

    user = tenants["users"][0]
    db.add(
        AccessPolicy(
            user_id=user.id,
            company_id=1,
            grants={
                "crm": {
                    "enabled": True,
                    "scope": "organization",
                    "actions": ["view", "edit", "create"],
                    "permissions": ["crm_view", "crm_manage"],
                }
            },
            status="active",
            version=1,
        )
    )
    db.commit()
    response = client.get("/api/v1/crm/leads", headers=tenants["headers"][0])
    assert response.status_code == 200, response.text
    assert (
        "Alpha private lead" in response.text
        and "Beta private lead" not in response.text
    )


def test_company_two_legacy_branch_and_department_null_org_are_scoped(
    client, db, tenants
):
    from app.models.company import Branch, Department

    branch = Branch(name="Beta branch", company_id=2)
    db.add(branch)
    db.flush()
    department = Department(name="Beta department", branch_id=branch.id)
    db.add(department)
    db.flush()
    cleanup = install(db, tenants["users"][1], 2)
    try:
        assert db.get(Branch, branch.id) is branch
        assert db.get(Department, department.id) is department
    finally:
        cleanup()
    cleanup = install(db, tenants["users"][0], 1)
    try:
        assert db.get(Branch, branch.id) is None
        assert db.get(Department, department.id) is None
    finally:
        cleanup()


def test_legacy_bulk_mapping_cannot_bypass_company_write_checks(db, tenants):
    from app.apps.project_management.models import PMSTaskAssignee

    cleanup = install(db, tenants["users"][0], 1)
    try:
        with pytest.raises(HTTPException):
            db.bulk_insert_mappings(
                PMSTaskAssignee,
                [
                    {
                        "task_id": tenants["tasks"][1].id,
                        "user_id": tenants["users"][0].id,
                    }
                ],
            )
    finally:
        cleanup()


def test_bulk_update_only_changes_the_authorized_company(db, tenants):
    from sqlalchemy import update

    cleanup = install(db, tenants["users"][0], 1)
    try:
        db.execute(update(CRMLead).values(status="Qualified"))
    finally:
        cleanup()
    db.expire_all()
    assert db.get(CRMLead, tenants["leads"][0].id).status == "Qualified"
    assert db.get(CRMLead, tenants["leads"][1].id).status != "Qualified"


def test_ownership_assignment_is_explicit_idempotent_and_audited(db, tenants):
    from app.apps.admin_security.models import AdminProfile
    from app.models.audit import AuditLog
    from scripts.assign_legacy_company import assign

    admin = User(
        email="operator@example.com",
        hashed_password="unused",
        is_active=True,
        is_superuser=True,
    )
    profile = AdminProfile(name="Legacy unmapped")
    db.add_all([admin, profile])
    db.flush()
    result = assign(
        db, admin, 1, "admin_profiles", [profile.id], "Reviewed customer provenance"
    )
    assert result["dry_run"] is True and len(result["changes"]) == 1
    assign(
        db,
        admin,
        1,
        "admin_profiles",
        [profile.id],
        "Reviewed customer provenance",
        apply=True,
    )
    assert (
        assign(
            db, admin, 1, "admin_profiles", [profile.id], "Reviewed customer provenance"
        )["changes"]
        == []
    )
    with pytest.raises(HTTPException):
        assign(
            db,
            admin,
            2,
            "admin_profiles",
            [profile.id],
            "Unreviewed attempted reassignment",
            apply=True,
        )
    assert db.query(AuditLog).filter_by(action="OWNERSHIP_ASSIGN").count() == 1


def test_legacy_role_permission_revocation_invalidates_file_capability(
    db, tenants, monkeypatch, tmp_path
):
    from urllib.parse import urlsplit, parse_qs
    from app.core.config import settings
    from app.core.audit_context import context, set_audit_actor
    from app.core.storage import signed_file_url, blob_token_path

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    user = tenants["users"][0]
    user.organization_id = 1
    state = context.set({})
    try:
        set_audit_actor(user)
        url = signed_file_url(str(tmp_path / "private.txt"))
    finally:
        context.reset(state)
    token = parse_qs(urlsplit(url).query)["token"][0]
    assert blob_token_path(token, db=db)
    user.role.permissions = [p for p in user.role.permissions if p.name != "crm_view"]
    db.flush()
    with pytest.raises(HTTPException):
        blob_token_path(token, db=db)


def test_bulk_parameter_updates_cannot_assign_a_foreign_user(db, tenants):
    from sqlalchemy import update

    cleanup = install(db, tenants["users"][0], 1)
    try:
        with pytest.raises(HTTPException):
            db.execute(
                update(PMSTask),
                [
                    {
                        "id": tenants["tasks"][0].id,
                        "assignee_user_id": tenants["users"][1].id,
                    }
                ],
            )
    finally:
        cleanup()
