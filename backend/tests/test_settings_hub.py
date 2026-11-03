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
    for name in dict.fromkeys(permissions):
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


def test_settings_catalog_statuses_are_real_and_permission_scoped(client, db):
    headers, user = actor(db, admin=True)
    company = db.get(Company, 1)
    company.email = None
    company.country = None
    db.commit()
    response = client.get(BASE, headers=headers)
    assert response.status_code == 200, response.text
    options = {o["id"]: o for o in response.json()["options"]}
    assert options["company-profile"]["status"]["state"] == "attention"
    assert options["company-profile"]["historyAvailable"] is True
    assert "connections" not in options
    company.email = "company@example.com"
    company.country = "India"
    db.commit()
    options = {o["id"]: o for o in client.get(BASE, headers=headers).json()["options"]}
    assert options["company-profile"]["status"]["state"] == "ready"


def test_settings_change_history_is_tenant_scoped_and_omits_values(client, db):
    from app.access.models import AccessAudit
    headers, user = actor(db, admin=True)
    response = client.patch(BASE+"/company-profile", headers=headers, json={"name":"History company", "default_currency":"INR"})
    assert response.status_code == 200, response.text
    db.add(Company(id=78, name="Other history tenant")); db.flush()
    db.add(AccessAudit(actor_id=user.id,company_id=78,operation="settings.company.updated",reason="Other tenant",after_json={"name":"Private other tenant"}))
    db.commit()
    response = client.get(BASE+"/history/company-profile", headers=headers)
    assert response.status_code == 200, response.text
    entries = response.json()["items"]
    assert len(entries) == 1
    assert entries[0]["fields"] == ["name"]
    assert entries[0]["actor"] == user.email
    assert "Private other tenant" not in response.text and "History company" not in response.text
    defaults = client.get(BASE+"/history/business-defaults", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json()["items"][0]["fields"] == ["default_currency"]
    assert client.get(BASE+"/history/security", headers=headers).status_code == 403


def test_read_only_settings_user_cannot_read_company_change_history(client, db):
    headers, user = actor(db)
    options = client.get(BASE, headers=headers).json()["options"]
    assert all(o["historyAvailable"] is False for o in options)
    assert client.get(BASE+"/history/company-profile", headers=headers).status_code == 403


def test_connection_configuration_badge_counts_current_company_only(client, db):
    from app.models.platform import IntegrationCredential
    headers, user = actor(db, superuser=True)
    db.add(Company(id=79, name="Other connection tenant")); db.flush()
    db.add(IntegrationCredential(provider="preview",credential_name="Other active",organization_id=79,secret_ref="private-not-for-output",status="Active"))
    db.commit()
    options = {o["id"]:o for o in client.get(BASE,headers=headers).json()["options"]}
    assert options["connections"]["status"]["label"] == "Not configured"
    db.add(IntegrationCredential(provider="preview",credential_name="Local active",organization_id=1,secret_ref="private-not-for-output",status="Active")); db.commit()
    response=client.get(BASE,headers=headers)
    options={o["id"]:o for o in response.json()["options"]}
    assert options["connections"]["status"]["label"] == "Configured"
    assert "1 active" in options["connections"]["status"]["detail"]
    assert "private-not-for-output" not in response.text


def test_email_configuration_status_does_not_claim_live_delivery(client, db, monkeypatch):
    headers, user = actor(db, superuser=True)
    monkeypatch.setattr("app.shared.communications.provider_status", lambda: [{"channel":"email", "status":"configured-unverified"}])
    response = client.get(BASE, headers=headers)
    assert response.status_code == 200
    option = next(o for o in response.json()["options"] if o["id"] == "communication")
    assert option["status"]["label"] == "Configured"
    assert "not been verified" in option["status"]["detail"]
    monkeypatch.setattr("app.shared.communications.provider_status", lambda: [{"channel":"email", "status":"unconfigured"}])
    option = next(o for o in client.get(BASE, headers=headers).json()["options"] if o["id"] == "communication")
    assert option["status"]["label"] == "Not configured"
