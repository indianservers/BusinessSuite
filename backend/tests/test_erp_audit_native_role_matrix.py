"""Original DEF016 boundaries with verified identities, never superuser bypass."""
import pytest
from app.models.user import Role, User
from app.models.approval_os import ApprovalRequest
from test_identity_utils import own_workflow_records
from tests.payroll_test_utils import init_payroll_test_db


@pytest.mark.parametrize("role,ai,directory,onboarding", [
    ("hr_manager",200,200,200),
    ("manager",200,200,403),
    ("employee",200,403,403),
    ("crm_org_admin",403,403,403),
    ("pms_org_admin",403,200,403),
    ("srm_admin",403,403,403),
    ("fam_admin",403,403,403),
    ("accountant",403,403,403),
    ("fam_viewer",403,403,403),
])
def test_verified_native_roles_keep_domain_administration_boundaries(client, db, role, ai, directory, onboarding):
    init_payroll_test_db(db)
    user=db.query(User).filter_by(email="employee@aihrms.com").one()
    user.role=db.query(Role).filter_by(name=role).one()
    assert not user.is_superuser
    from app.common.models import CommonPerson
    other=db.query(User).join(CommonPerson,CommonPerson.user_id==User.id).filter(CommonPerson.organization_id==user.person.organization_id,User.id!=user.id).first()
    assert other is not None
    common=dict(organization_id=user.person.organization_id,source_module="crm",approval_type="Review",entity_type="fixture",entity_id=1,status="Pending")
    own=ApprovalRequest(**common,title="Own request",requester_user_id=user.id)
    private=ApprovalRequest(**common,title="Other user private request",requester_user_id=other.id,assigned_to_user_id=other.id)
    db.add_all([own,private]);own_workflow_records(db,own,private,company_id=user.person.organization_id)
    db.commit()
    login=client.post("/api/v1/auth/login",json={"email":user.email,"password":"Employee@123456"})
    assert login.status_code==200
    headers={"Authorization":"Bearer "+login.json()["access_token"]}
    context=client.get("/api/v1/access/me",headers=headers)
    assert context.status_code==200, context.text
    for path,expected in [("/ai-operator/assistant/tools",ai),("/users/directory",directory),("/onboarding/templates",onboarding),("/workflow-engine/definitions",403)]:
        response=client.get("/api/v1"+path,headers=headers)
        assert response.status_code==expected,(role,path,response.status_code,response.text)
        if expected==403:
            assert "membership" not in response.json().get("detail","").lower(), "Test must reach native feature authorization"

    imports={"hr_manager":"hrms","crm_org_admin":"crm","pms_org_admin":"pms","srm_admin":"srm","fam_admin":"fam","accountant":"fam"}
    for module in ("crm","hrms","pms","srm","fam"):
        response=client.get(f"/api/v1/imports/{module}/catalog",headers=headers)
        assert response.status_code==200,(role,module,response.status_code,response.text)
        assert bool(response.json())==(imports.get(role)==module),(role,module,response.json())
    for path,expected in [
        ("/approval-os/inbox",200),
        ("/accounting-sync/connections",200 if role in {"fam_admin","accountant"} else 403),
        ("/logs/requests",403),
    ]:
        response=client.get("/api/v1"+path,headers=headers)
        assert response.status_code==expected,(role,path,response.status_code,response.text)
        if expected==403:
            assert "membership" not in response.json().get("detail","").lower()

    inbox=client.get("/api/v1/approval-os/inbox",headers=headers).json()
    ids={item["id"] for item in inbox["items"]}
    assert f"approval:{own.id}" in ids
    assert f"approval:{private.id}" not in ids
    if role in {"fam_admin","accountant","fam_viewer"}:
        all_inbox=client.get("/api/v1/approval-os/inbox?scope=all",headers=headers)
        assert all_inbox.status_code==200
        assert f"approval:{private.id}" not in {item["id"] for item in all_inbox.json()["items"]}
