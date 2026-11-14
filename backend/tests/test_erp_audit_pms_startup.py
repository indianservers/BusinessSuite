from datetime import datetime,timedelta
import pytest
from app.apps.project_management.models import PMSWorkspaceMember,PMSWorkspaceInvitation
from tests.test_pms_workspaces import account,middleware_database,BASE


@pytest.mark.parametrize("role",["Owner","Member","Guest"])
def test_workspace_startup_reuses_native_fields_without_invitation_leaks(client,db,role,monkeypatch):
    owner,oh=account(db,"startup-owner@example.test",True)
    wid=client.post(BASE+"/workspaces",headers=oh,json={"name":"Startup scope"}).json()["id"]
    if role=="Owner":actor,headers=owner,oh
    else:
        actor,headers=account(db,"startup-member@example.test")
        added=client.post(f"{BASE}/workspaces/{wid}/members",headers=oh,json={"user_id":actor.id,"role":role})
        assert added.status_code in {200,201},added.text
    db.add(PMSWorkspaceInvitation(workspace_id=wid,email="private-invite@example.test",role="Member",status="revoked",token_hash="synthetic-startup-fixture",expires_at=datetime.utcnow()-timedelta(days=1)))
    db.commit()
    url=f"{BASE}/workspaces/{wid}"
    ordinary=client.get(url+"/overview",headers=headers)
    assert ordinary.status_code==200
    assert "members" not in ordinary.json() and "invitations" not in ordinary.json()
    native_members=client.get(url+"/members",headers=headers)
    assert native_members.status_code==200
    from app.apps.project_management import workspaces
    checks=[];native_scope=workspaces.workspace_member
    def counted_scope(db,wid,user,manage=False):
        checks.append(manage);return native_scope(db,wid,user,manage)
    monkeypatch.setattr(workspaces,"workspace_member",counted_scope)
    bundled=client.get(url+"/overview",headers=headers,params={"include_people":True})
    assert checks==[False], "Bundle should resolve current workspace once, not repeat identical native guards"
    assert bundled.status_code==200,bundled.text
    data=bundled.json()
    assert {k:data[k] for k in ordinary.json()}==ordinary.json()
    assert data["members"]==native_members.json()
    if role=="Owner":
        native=client.get(url+"/invitations",headers=headers)
        assert native.status_code==200
        assert data["invitations"]==[{k:v for k,v in row.items() if k!="token"} for row in native.json()]
        assert all("token" not in row for row in data["invitations"])
    else:
        assert data["invitations"]==[]
        assert client.get(url+"/invitations",headers=headers).status_code==403
        membership=db.query(PMSWorkspaceMember).filter_by(workspace_id=wid,user_id=actor.id).one()
        db.delete(membership);db.commit()
        assert client.get(url+"/overview",headers=headers,params={"include_people":True}).status_code in {403,404}
