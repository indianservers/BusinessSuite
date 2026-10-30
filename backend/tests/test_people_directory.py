import pytest
from fastapi import HTTPException
from app.models.user import User, Role
from app.apps.project_management.directory import people_directory
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSWorkspaceTeam
from app.core.tenant_boundary import install
from tests.test_company_security_boundary import tenants


def test_accounts_without_employee_or_workspace_are_included_and_paginated(db):
    admin = User(email="admin@directory.test", hashed_password="unused", is_superuser=True)
    dsb = User(email="dsb@dsbchartered.com", hashed_password="unused")
    db.add_all([admin, dsb]); db.flush()
    workspace = PMSWorkspace(name="Other workspace", organization_id=1)
    db.add(workspace); db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=admin.id, role="Owner"))
    db.add(PMSWorkspaceTeam(workspace_id=workspace.id, name="Reviewers", alias="reviewers", member_ids_json=f"[{admin.id},{dsb.id}]"))
    db.commit()
    result = people_directory(db, admin, page=1, page_size=100)
    person = next(p for p in result["items"] if p["email"] == dsb.email)
    assert person["workspace_ids"] == []
    assert result["teams"][0]["member_ids"] == [admin.id]
    first = people_directory(db, admin, page=1, page_size=1)
    second = people_directory(db, admin, page=2, page_size=1)
    assert first["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_directory_photos_respect_profile_visibility(db):
    from app.common.models import CommonPerson, CommonProfile
    admin = User(email="photo.admin@directory.test", hashed_password="unused", is_superuser=True)
    public = User(email="public@directory.test", hashed_password="unused")
    private = User(email="private@directory.test", hashed_password="unused")
    db.add_all([admin, public, private]); db.flush()
    for user, visibility in [(public, "public"), (private, "hidden")]:
        person = CommonPerson(user_id=user.id, organization_id=1, display_name=user.email)
        db.add(person); db.flush()
        db.add(CommonProfile(person_id=person.id, profile_photo_url="/uploads/portrait.png", directory_visibility=visibility))
    db.commit()
    result = people_directory(db, admin, page=1, page_size=100)
    people = {row["id"]: row for row in result["items"]}
    assert people[public.id]["profile_photo_url"] == "/uploads/portrait.png"
    assert people[private.id]["profile_photo_url"] is None


@pytest.mark.parametrize("role", ["Admin", "HR", "hr_admin", "hr_manager", "CEO", "pms_org_admin"])
def test_senior_roles_can_explore(db, role):
    r = Role(name=role); db.add(r); db.flush()
    user = User(email="reader@directory.test", hashed_password="unused", role=r)
    db.add(user); db.commit()
    assert people_directory(db, user, page=1, page_size=100)["total"] == 1


def test_ordinary_user_cannot_explore(db):
    user = User(email="member@directory.test", hashed_password="unused")
    db.add(user); db.commit()
    with pytest.raises(HTTPException) as error:
        people_directory(db, user, page=1, page_size=100)
    assert error.value.status_code == 403


def test_company_boundary_is_preserved(db, tenants):
    user = tenants["users"][0]
    cleanup = install(db, user, 1)
    try:
        result = people_directory(db, user, page=1, page_size=100)
        assert "alpha@example.com" in {p["email"] for p in result["items"]}
        assert "beta@example.com" not in {p["email"] for p in result["items"]}
    finally:
        cleanup()


def test_shared_directory_http_access(client, db, tenants):
    from app.main import app
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        response = client.get("/api/v1/users/directory", headers=tenants["headers"][0])
        assert response.status_code == 200, response.text
        assert "alpha@example.com" in response.text
        assert "beta@example.com" not in response.text
        assert client.get("/api/v1/users/directory").status_code in {401, 403}
        assert client.get("/api/v1/users/directory", headers=tenants["headers"][2]).status_code == 403
    finally:
        del app.state.business_os_session_factory
        del app.state.business_os_close_session
