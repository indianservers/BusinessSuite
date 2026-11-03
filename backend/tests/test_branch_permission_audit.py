import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.branches.api import read_policy, save_policy, PolicyInput
from app.branches.models import BranchGrant, BranchPolicy
from app.branches.service import context
from app.models.user import User
from app.access.models import AccessMembership
from app.core.security import create_access_token, get_password_hash
from tests.test_branch_module_ownership import matrix


def request():
    return Request({"type":"http", "method":"PUT", "path":"/api/v1/branches/access", "headers":[]})


def test_legacy_user_branch_editor_loads_and_linking_requires_verified_admin(client, db, matrix):
    branches, people = matrix
    admin = people["super"]
    admin.hashed_password = get_password_hash("BranchAudit!Test209")
    legacy = User(email="legacy.branch.editor@example.test", hashed_password="unused", is_active=True)
    db.add(legacy); db.commit()
    headers = {"Authorization":"Bearer " + create_access_token(admin.id)}
    response = client.get(f"/api/v1/branches/access/{legacy.id}", headers=headers)
    assert response.status_code == 200, response.text
    payload = {"expected_version":0,"use_home_branch":False,"grants":[{"branch_id":branches[0].id,"can_write":False}],"reason":"Explicitly assign a legacy account to its branch"}
    denied = client.put(f"/api/v1/branches/access/{legacy.id}", headers=headers, json=payload)
    assert denied.status_code == 403
    assert not db.query(AccessMembership).filter_by(user_id=legacy.id).first()
    assert not db.query(BranchGrant).filter_by(user_id=legacy.id).first()
    verified = client.post("/api/v1/access/step-up", headers=headers, json={"password":"BranchAudit!Test209"})
    assert verified.status_code == 200, verified.text
    saved = client.put(f"/api/v1/branches/access/{legacy.id}", headers={**headers,"X-Access-Step-Up":verified.json()["token"]}, json=payload)
    assert saved.status_code == 200, saved.text
    member = db.query(AccessMembership).filter_by(user_id=legacy.id,company_id=1).one()
    assert member.active and not member.is_admin
    assert context(db, legacy, 1).allowed == frozenset({branches[0].id})


def test_removing_explicit_branch_roles_cannot_bypass_company_admin_authority(db, matrix):
    branches, people = matrix
    target, head = people["employee_a"], people["head_a"]
    db.query(BranchGrant).filter_by(user_id=target.id,branch_id=branches[0].id).one().module_grants = {}
    db.query(BranchPolicy).filter_by(user_id=target.id).one().use_home_branch = True
    db.commit()
    before = read_policy(target.id,db,head)
    # Removing the whitelist would inherit the broader company role through home access.
    payload = PolicyInput(expected_version=before["version"],use_home_branch=True,grants=[],reason="Attempt to erase branch role restrictions")
    with pytest.raises(HTTPException) as denied:
        save_policy(target.id,payload,request(),db,head)
    assert denied.value.status_code == 403
    assert db.query(BranchGrant).filter_by(user_id=target.id,branch_id=branches[0].id).one().module_grants == {}


def test_delegated_manager_cannot_enable_an_unmanaged_home_branch(db, matrix):
    branches, people = matrix
    target, head = people["employee_a"], people["head_b"]
    db.query(BranchGrant).filter_by(user_id=target.id).delete()
    db.add(BranchGrant(user_id=target.id,company_id=1,branch_id=branches[1].id,can_write=False))
    db.commit()
    before = read_policy(target.id,db,head)
    payload = PolicyInput(expected_version=before["version"],use_home_branch=True,grants=before["grants"],reason="Attempt to enable another branch through home access")
    with pytest.raises(HTTPException) as denied:
        save_policy(target.id,payload,request(),db,head)
    assert denied.value.status_code == 403
    assert "home-branch" in denied.value.detail
    assert branches[0].id not in context(db,target,1).allowed


def test_explicit_read_only_membership_overrides_implicit_home_writes(db, matrix):
    branches, people = matrix
    target = people["employee_a"]
    db.query(BranchPolicy).filter_by(user_id=target.id).one().use_home_branch = True
    db.query(BranchGrant).filter_by(user_id=target.id,branch_id=branches[0].id).one().can_write = False
    db.commit()
    ctx = context(db,target,1)
    assert branches[0].id in ctx.allowed
    assert branches[0].id not in ctx.writable
    from app.branches.roles import effective_grants
    base = {"crm":{"enabled":True,"role":"admin","permissions":["crm_admin"],"actions":["view","create","edit","delete","export"],"scope":"organization"}}
    effective = effective_grants(db,target,1,str(branches[0].id),base)
    assert effective["crm"]["actions"] == ["view","export"]


def test_employee_code_allocation_does_not_restart_in_an_empty_branch(db, matrix):
    from app.branches.boundary import install
    from app.crud.crud_employee import crud_employee as employee_crud
    from app.models.employee import Employee
    from sqlalchemy import select, func
    branches, people = matrix
    # Reserve the next generated code in a different branch, including manual codes.
    top = db.connection().execute(select(func.max(Employee.id))).scalar()
    hidden = db.query(Employee).filter_by(user_id=people["employee_a"].id).one()
    hidden.employee_id = f"EMP{top+1:05d}"
    db.commit()
    cleanup = install(db,people["super"],context(db,people["super"],1,str(branches[2].id)))
    try:
        assert db.query(Employee).count() == 0
        assert employee_crud.generate_employee_id(db) == f"EMP{top+2:05d}"
    finally:
        cleanup()


@pytest.mark.parametrize("broad",["crm_admin","crm_manage","crm_view"])
def test_registered_crm_features_can_narrow_a_broad_company_admin(db, matrix, broad):
    from app.models.user import Permission
    from app.access.feature_permissions import CRM_FEATURE_PERMISSIONS
    from app.access.models import AccessPolicy
    from app.access.service import resolved_grants
    from app.branches.roles import effective_grants
    from app.apps.crm.api.router import CRM_ENTITY_PERMISSION_KEYS, CRM_SPECIAL_PERMISSIONS
    assert {name for name, _, _ in CRM_FEATURE_PERMISSIONS} == {f"crm_{key}_{action}" for key in set(CRM_ENTITY_PERMISSION_KEYS.values()) for action in ("view","manage")} | set(CRM_SPECIAL_PERMISSIONS)
    existing = {p.name for p in db.query(Permission)}
    for name, description, module in CRM_FEATURE_PERMISSIONS:
        if name not in existing:
            db.add(Permission(name=name,description=description,module=module))
    if broad not in existing:
        db.add(Permission(name=broad,description="CRM broad permission",module="crm"))
    branches, people = matrix
    target = people["employee_a"]
    base = {"crm":{"enabled":True,"role":"admin","permissions":[broad],"actions":["view","create","edit"],"scope":"organization"}}
    policy = AccessPolicy(user_id=target.id,company_id=1,status="active",grants=base)
    db.add(policy)
    db.query(BranchGrant).filter_by(user_id=target.id,branch_id=branches[0].id).one().module_grants = {"crm":{"enabled":True,"role":"custom","permissions":["crm_accounts_view"],"actions":["view"],"scope":"organization"}}
    db.commit()
    grants = effective_grants(db,target,1,str(branches[0].id),resolved_grants(db,policy))
    assert grants["crm"]["permissions"] == ["crm_accounts_view"]
    assert "crm_admin" not in grants["crm"]["permissions"]
    assert grants["crm"]["actions"] == ["view"]


def test_legacy_crm_org_admin_still_cannot_read_an_unassigned_branch(db):
    from tests.test_branch_access import setup
    from app.models.user import Permission, Role
    from app.apps.crm.models import CRMCompany
    from app.apps.crm.api.router import _crm_has_full_visibility
    from app.branches.boundary import install
    user, east, west, own, foreign, _ = setup(db)
    permission = db.query(Permission).filter_by(name="crm_admin").first()
    if permission is None:
        permission = Permission(name="crm_admin",description="CRM administrator",module="crm")
        db.add(permission)
    role = Role(name="crm_org_admin",permissions=[permission])
    db.add(role); user.role=role; db.commit()
    assert not user.is_superuser
    assert _crm_has_full_visibility(user)  # The native module treats this as an admin.
    cleanup = install(db,user,context(db,user,1,str(east.id)))
    try:
        assert {row.id for row in db.query(CRMCompany)} == {own.id}
        assert db.get(CRMCompany,foreign.id) is None
    finally:
        cleanup()


def test_board_columns_inherit_authorized_project_scope(db, matrix):
    from app.access.scope import install_scope
    from app.branches.boundary import install
    from app.branches.models import BranchOwnership
    from app.apps.project_management.models import PMSProject, PMSBoard, PMSBoardColumn
    branches, people = matrix
    actor = people["employee_a"]
    db.query(BranchGrant).filter_by(user_id=actor.id,branch_id=branches[0].id).one().can_write = True
    own = PMSProject(organization_id=1,branch_id=branches[0].id,name="Allowed board",project_key="ALLOWBOARD",owner_user_id=actor.id)
    foreign = PMSProject(organization_id=1,branch_id=branches[1].id,name="Foreign board",project_key="DENYBOARD",owner_user_id=actor.id)
    db.add_all([own,foreign]); db.flush()
    boards = [PMSBoard(project_id=p.id,name="Board",board_type="Kanban") for p in (own,foreign)]
    db.add_all(boards); db.flush()
    for project,board,branch in zip((own,foreign),boards,branches):
        for record in (project,board):
            db.add(BranchOwnership(resource_table=record.__tablename__,resource_key=str(record.id),company_id=1,branch_id=branch.id,source="permission-audit"))
    db.commit()
    branch_cleanup = install(db,actor,context(db,actor,1,str(branches[0].id)))
    scope_cleanup = install_scope(db,actor,1,{"project_management":{"enabled":True,"role":"custom","permissions":["pms_manage_tasks"],"actions":["view","create","edit"],"scope":"organization"}})
    try:
        column = PMSBoardColumn(board_id=boards[0].id,name="To Do",status_key="TODO",position=0)
        db.add(column); db.flush()
        assert db.query(PMSBoardColumn).filter_by(id=column.id).one().board_id == boards[0].id
        denied = PMSBoardColumn(board_id=boards[1].id,name="Must not create",status_key="TODO",position=0)
        db.add(denied)
        with pytest.raises(HTTPException) as exc:
            db.flush()
        assert exc.value.status_code == 403
    finally:
        scope_cleanup(); branch_cleanup()


def test_explicit_company_membership_revocation_beats_person_and_home_branch(db, matrix):
    from app.core.tenant_boundary import company_ids
    from app.access.service import companies_for
    branches, people = matrix
    actor = people["employee_a"]
    assert 1 in company_ids(db,actor)
    row = AccessMembership(user_id=actor.id,company_id=1,active=False,is_admin=False)
    db.add(row); db.commit()
    assert 1 not in company_ids(db,actor)
    assert 1 not in companies_for(db,actor)
    with pytest.raises(HTTPException) as denied:
        context(db,actor,1,str(branches[0].id))
    assert denied.value.status_code == 403
    row.active=True; db.commit()
    assert branches[0].id in context(db,actor,1).allowed
