from uuid import uuid4
import pytest
from app.models.user import User, Role, Permission
from app.models.company import Company
from app.access.models import AccessPolicy, AccessMembership
from app.access.settings_hub import OPTIONS, allows
from app.core.security import create_access_token
from app.db.init_db import SYSTEM_ROLES, SYSTEM_PERMISSIONS

BASE = "/api/v1/access/settings"


def actor(db, role="employee", permissions=(), superuser=False, grants=None, admin=False):
    existing = {p.name:p for p in db.query(Permission)}
    selected=[]
    definitions={p[0]:p for p in SYSTEM_PERMISSIONS}
    for name in permissions:
        if name not in existing:
            value=definitions.get(name,(name,name,"hrms"))
            existing[name]=Permission(name=name,description=value[1],module=value[2]);db.add(existing[name])
        selected.append(existing[name])
    r=Role(name=role,permissions=selected);db.add(r);db.flush()
    if not db.get(Company,1):db.add(Company(id=1,name="Settings Test Company"));db.flush()
    u=User(email=uuid4().hex+"@example.invalid",hashed_password="unusable-test-password",is_active=True,is_superuser=superuser,role_id=r.id)
    db.add(u);db.flush()
    if grants is not None:db.add(AccessPolicy(user_id=u.id,company_id=1,status="active",grants=grants))
    if not superuser:db.add(AccessMembership(user_id=u.id,company_id=1,active=True,is_admin=admin))
    db.commit()
    return {"Authorization":"Bearer "+create_access_token(u.id)},u


@pytest.mark.parametrize("definition",SYSTEM_ROLES,ids=lambda r:r["name"])
def test_every_seeded_role_has_no_implicit_admin_settings(client,db,definition):
    headers,u=actor(db,definition["name"],definition["permissions"],definition["name"]=="super_admin")
    result=client.get(BASE,headers=headers);assert result.status_code==200,result.text
    ids={o["id"] for o in result.json()["options"]}
    assert {"account","preferences","company-profile"} <= ids
    if not u.is_superuser:
        assert not ids.intersection({"users","security","connections","communication","global","modules","ai"})
        for key in ["users","security","connections","communication","global","modules","ai"]:
            assert client.get(BASE+"/"+key,headers=headers).status_code==403
    for option in result.json()["options"]:
        assert client.get(BASE+"/"+option["id"],headers=headers).status_code==200


def test_employee_cannot_write_company_or_discover_other_company(client,db):
    headers,u=actor(db)
    db.add(Company(id=77,name="Other tenant"));db.commit()
    result=client.get(BASE,headers=headers);assert {o["id"] for o in result.json()["options"]}=={"account","preferences","company-profile"}
    profile=client.get(BASE+"/company-profile",headers=headers).json()
    assert not profile["editable"] and "gstin" not in profile["profile"]
    assert client.patch(BASE+"/company-profile",headers=headers,json={"name":"Changed"}).status_code==403
    assert client.get(BASE,headers={**headers,"X-Suite-Organization":"77"}).status_code==403
    assert client.get(BASE+"/security",headers=headers).status_code==403
    assert client.get(BASE+"/made-up",headers=headers).status_code==403


def test_company_admin_only_company_settings_and_audited_profile(client,db):
    headers,u=actor(db,admin=True)
    ids={o["id"] for o in client.get(BASE,headers=headers).json()["options"]}
    assert {"users","audit","modules"} <= ids
    assert not ids.intersection({"security","connections","communication","global"})
    result=client.patch(BASE+"/company-profile",headers=headers,json={"name":"Updated Company","default_timezone":"Asia/Kolkata"})
    assert result.status_code==200,result.text
    assert db.get(Company,1).name=="Updated Company"
    assert client.patch(BASE+"/company-profile",headers=headers,json={"id":77,"name":"Cross tenant"}).status_code==422
    assert client.patch(BASE+"/company-profile",headers=headers,json={"name":" "}).status_code==422
    assert client.patch(BASE+"/company-profile",headers=headers,json={"default_timezone":"Invalid/Zone"}).status_code==422


@pytest.mark.parametrize("scope,actions,enabled,expected",[("organization",["view","configure"],True,True),("own",["view","configure"],True,False),("organization",["view"],True,False),("organization",["view","configure"],False,False)])
def test_managed_grants_need_enabled_module_action_and_scope(client,db,scope,actions,enabled,expected):
    grants={"project_management":{"enabled":enabled,"role":"custom","permissions":["pms_admin"],"actions":actions,"scope":scope}}
    headers,u=actor(db,permissions=["pms_admin"],grants=grants)
    # Company grants are a ceiling; an actual branch membership is also required.
    from app.models.company import Branch
    from app.branches.models import BranchPolicy, BranchGrant
    branch = Branch(name="Settings scope branch", code="SET-SCOPE", company_id=1, organization_id=1, is_active=True)
    db.add(branch); db.flush()
    db.add(BranchPolicy(user_id=u.id, company_id=1, use_home_branch=False))
    db.add(BranchGrant(user_id=u.id, company_id=1, branch_id=branch.id, can_write=True))
    db.commit()
    ids={o["id"] for o in client.get(BASE,headers=headers).json()["options"]}
    assert ("pms" in ids)==expected
    assert client.get(BASE+"/pms",headers=headers).status_code==(200 if expected else 403)


def test_anonymous_denied(client):
    assert client.get(BASE).status_code in (401,403)
    assert client.get(BASE+"/company-profile").status_code in (401,403)


def test_central_integrations_require_superuser_and_roles_require_company_admin(client, db):
    headers, _ = actor(db, admin=True)
    assert client.get(BASE + "/roles", headers=headers).status_code == 200
    assert client.get(BASE + "/business-defaults", headers=headers).status_code == 200
    for key in ("api-credentials", "webhooks", "financial-years", "cost-centers", "crm-pipelines"):
        assert client.get(BASE + "/" + key, headers=headers).status_code == 403


def test_central_finance_settings_honor_branch_and_company_module_ceiling(client, db):
    from app.models.company import Branch
    from app.branches.models import BranchPolicy, BranchGrant
    grant = {"enabled": True, "role": "admin", "permissions": ["fam_admin"], "actions": ["view", "configure"], "scope": "organization"}
    headers, user = actor(db, permissions=["fam_admin"], grants={"fam": grant})
    # No branch membership must not expose module configuration.
    assert client.get(BASE + "/financial-years", headers=headers).status_code == 403
    branch = Branch(name="Finance settings", code="FIN-SET", company_id=1, organization_id=1, is_active=True)
    db.add(branch); db.flush()
    db.add(BranchPolicy(user_id=user.id, company_id=1, use_home_branch=False))
    db.add(BranchGrant(user_id=user.id, company_id=1, branch_id=branch.id, can_write=True))
    db.commit()
    for key in ("financial-years", "cost-centers", "accounting-branches", "voucher-types", "payment-modes", "tax-settings"):
        assert client.get(BASE + "/" + key, headers=headers).status_code == 200
    assert client.get(BASE + "/crm-pipelines", headers=headers).status_code == 403


def test_branch_settings_requires_branch_administration_not_hr_role(client, db):
    from app.branches.models import BranchPolicy
    headers, user = actor(db, permissions=["company_manage"])
    assert client.get(BASE + "/branches", headers=headers).status_code == 403
    db.add(BranchPolicy(user_id=user.id, company_id=1, manage_access=True, use_home_branch=False))
    db.commit()
    assert client.get(BASE + "/branches", headers=headers).status_code == 200
    # A delegated branch administrator does not become a company access administrator.
    assert client.get(BASE + "/users", headers=headers).status_code == 403


def test_view_only_and_disabled_grants_never_offer_configuration():
    for definition in SYSTEM_ROLES:
        ctx={"super":False,"admin":False,"managed":True,"permissions":set(),"grants":{m:{"enabled":True,"scope":"organization","actions":["view"],"permissions":definition["permissions"]} for m in ["hrms","crm","project_management","srm","fam","ai","interns_hub"]}}
        assert {o[0] for o in OPTIONS if allows(o,ctx)}=={"account","preferences","company-profile"}
