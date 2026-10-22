"""Exercise the real API from invitation through tasks/Gantt and access removal."""
from datetime import datetime, timedelta
import pytest
from app.main import app

from app.core.security import create_access_token
from app.models.user import User
from app.apps.project_management.models import PMSWorkspaceInvitation, PMSWorkspaceMember

BASE = "/api/v1/project-management"


@pytest.fixture(autouse=True)
def middleware_database(db):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    yield
    del app.state.business_os_session_factory
    del app.state.business_os_close_session


def account(db, email, admin=False):
    user = User(email=email, hashed_password="unused", is_active=True, is_superuser=admin)
    db.add(user)
    db.commit()
    return user, {"Authorization": "Bearer " + create_access_token(str(user.id))}


def test_invitation_activation_status_and_replacement_link(client, db):
    from app.models.user import Role
    from app.core.security import verify_password
    role = Role(name="pms_team_member", is_system=True)
    db.add(role)
    db.commit()
    owner, headers = account(db, "activation-owner@test.com", True)
    wid = client.post(BASE + "/workspaces", json={"name": "Activation audit"}, headers=headers).json()["id"]
    url = f"{BASE}/workspaces/{wid}"
    payload = {"email": "activation-new@test.com", "role": "Member"}
    first = client.post(url + "/invitations", json=payload, headers=headers).json()
    second = client.post(url + "/invitations", json=payload, headers=headers).json()
    assert client.get(BASE + "/workspace-invitations/preview", params={"token": first["token"]}).status_code == 400
    preview = client.get(BASE + "/workspace-invitations/preview", params={"token": second["token"]})
    assert preview.status_code == 200
    assert preview.json()["account_exists"] is False
    assert preview.json()["email"] == payload["email"]
    password = "Audit-test-password-2026"
    activated = client.post(BASE + "/workspace-invitations/activate", json={"token": second["token"], "password": password})
    assert activated.status_code == 201, activated.text
    assert client.post(BASE + "/workspace-invitations/activate", json={"token": second["token"], "password": password}).status_code == 400
    user = db.query(User).filter_by(email=payload["email"]).one()
    assert not user.is_superuser and user.role_id == role.id
    assert verify_password(password, user.hashed_password)
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=user.id).one().role == "Member"
    invitations = client.get(url + "/invitations", headers=headers).json()
    assert invitations[0]["status"] == "accepted" and invitations[0]["account_exists"]
    assert invitations[1]["status"] == "revoked"


def test_activation_cannot_reset_an_existing_account(client, db):
    owner, headers = account(db, "activation-owner-existing@test.com", True)
    existing, _ = account(db, "activation-existing@test.com")
    wid = client.post(BASE + "/workspaces", json={"name": "Existing account"}, headers=headers).json()["id"]
    invitation = client.post(f"{BASE}/workspaces/{wid}/invitations", json={"email": existing.email}, headers=headers).json()
    result = client.post(BASE + "/workspace-invitations/activate", json={"token": invitation["token"], "password": "should-not-reset-password"})
    assert result.status_code == 409
    db.refresh(existing)
    assert existing.hashed_password == "unused"


def test_workspace_collaboration_end_to_end(client, db):
    owner, oh = account(db, "workspace-owner@test.com", True)
    teammate, th = account(db, "workspace-member@test.com")
    guest, gh = account(db, "workspace-guest@test.com", True)
    outsider, xh = account(db, "workspace-outsider@test.com", True)
    wid = client.post(BASE + "/workspaces", json={"name": "Delivery"}, headers=oh).json()["id"]
    url = f"{BASE}/workspaces/{wid}"
    assert client.get(url + "/members", headers=xh).status_code == 404
    invitation = client.post(url + "/invitations", json={"email": teammate.email.upper(), "role": "Member"}, headers=oh)
    assert invitation.status_code == 201, invitation.text
    token = invitation.json()["token"]
    assert token not in db.query(PMSWorkspaceInvitation).first().token_hash
    assert client.post(BASE + "/workspace-invitations/accept", json={"token": token}, headers=xh).status_code == 403
    assert client.post(BASE + "/workspace-invitations/accept", json={"token": token}, headers=th).status_code == 200
    assert client.post(BASE + "/workspace-invitations/accept", json={"token": token}, headers=th).status_code == 400
    assert client.get(BASE + "/workspaces", headers=th).json()[0]["role"] == "Member"
    assert client.post(url + "/invitations", json={"email": outsider.email}, headers=th).status_code == 403
    project_response = client.post(BASE + "/projects", json={"name": "Launch", "project_key": "WST", "workspace_id": wid}, headers=oh)
    assert project_response.status_code == 200, project_response.text
    pid = project_response.json()["id"]
    project_url = f"{BASE}/projects/{pid}"
    assert client.get(project_url, headers=xh).status_code == 403
    assert client.get(BASE + "/projects", headers=xh).json() == []
    assert client.post(BASE + "/projects", json={"name": "Denied", "project_key": "DEN", "workspace_id": wid}, headers=th).status_code == 403
    task = client.post(project_url + "/tasks", json={"title": "Prepare launch", "task_key": "WST-1", "assignee_user_id": teammate.id, "start_date": "2026-10-22", "due_date": "2026-10-25"}, headers=th)
    assert task.status_code == 200, task.text
    tid = task.json()["id"]
    overview_url = url + "/overview"
    overview = client.get(overview_url, headers=th)
    assert overview.status_code == 200
    assert overview.json()["tasks"][0]["id"] == tid
    assert client.get(overview_url, headers=xh).status_code == 404
    sibling = client.post(project_url + "/tasks", json={"title": "Review launch", "task_key": "WST-2"}, headers=th).json()
    assert client.patch(f"{BASE}/tasks/{tid}", json={"status": "In Progress", "position": 0}, headers=th).status_code == 200
    assert client.patch(f"{BASE}/tasks/{sibling['id']}", json={"status": "In Progress", "position": 0}, headers=th).status_code == 200
    board = client.get(project_url + "/board", headers=th).json()
    in_progress = next(c for c in board["columns"] if c["status_key"] == "IN_PROGRESS")
    assert [t["id"] for t in in_progress["tasks"]] == [sibling["id"], tid]
    assert client.post(f"{BASE}/tasks/{tid}/comments", json={"body": "Ready for the team", "body_format": "plain"}, headers=th).status_code == 200
    overview = client.get(overview_url, headers=th).json()
    assert next(t for t in overview["tasks"] if t["id"] == tid)["comments_count"] == 1
    gantt = client.get(BASE + "/gantt", params={"projectId": pid}, headers=th)
    assert gantt.status_code == 200, gantt.text
    assert any(t["id"] == tid for t in gantt.json()["tasks"])
    assert client.patch(f"{BASE}/tasks/{tid}", json={"due_date": "2026-10-28"}, headers=th).status_code == 200
    schedule_url = f"{BASE}/tasks/{tid}/schedule"
    assert client.patch(schedule_url, json={"start_date": "2026-10-23", "due_date": "2026-10-28"}, headers=th).status_code == 200
    assert client.patch(f"{BASE}/tasks/{tid}", json={"assignee_user_id": outsider.id}, headers=th).status_code == 422
    invite_guest = client.post(url + "/invitations", json={"email": guest.email, "role": "Guest"}, headers=oh).json()
    assert client.post(BASE + "/workspace-invitations/accept", json={"token": invite_guest["token"]}, headers=gh).status_code == 200
    assert client.get(project_url, headers=gh).status_code == 200
    assert client.get(BASE + "/gantt", params={"projectId": pid}, headers=gh).status_code == 200
    assert client.patch(schedule_url, json={"start_date": "2026-10-23", "due_date": "2026-10-28"}, headers=gh).status_code == 403
    assert client.patch(f"{BASE}/tasks/{tid}", json={"title": "No"}, headers=gh).status_code == 403
    assert client.post(project_url + "/clone", json={"name": "No", "project_key": "NOC"}, headers=gh).status_code == 403
    membership = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=teammate.id).one()
    mid = membership.id
    assert client.patch(url + f"/members/{mid}", json={"role": "Guest"}, headers=oh).status_code == 200
    assert client.patch(f"{BASE}/tasks/{tid}", json={"title": "No"}, headers=th).status_code == 403
    assert client.get(project_url, headers=th).status_code == 200
    assert client.patch(url + f"/members/{mid}", json={"role": "Admin"}, headers=oh).status_code == 200
    assert client.post(BASE + "/projects", json={"name": "Admin project", "project_key": "ADM", "workspace_id": wid}, headers=th).status_code == 200
    owner_mid = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=owner.id).one().id
    assert client.delete(url + f"/members/{owner_mid}", headers=th).status_code == 403
    assert client.post(url + "/invitations", json={"email": outsider.email, "role": "Admin"}, headers=th).status_code == 403
    assert client.delete(url + f"/members/{mid}", headers=oh).status_code == 200
    assert client.get(project_url, headers=th).status_code == 403
    assert client.get(overview_url, headers=th).status_code == 404
    assert client.get(f"{BASE}/tasks/{tid}", headers=th).status_code == 403
    assert client.get(BASE + "/gantt", params={"projectId": pid}, headers=th).status_code == 403


def test_invitation_revocation_expiry_and_reissue(client, db):
    _, headers = account(db, "invitation-owner@test.com", True)
    teammate, member_headers = account(db, "invitation-member@test.com")
    wid = client.post(BASE + "/workspaces", json={"name": "Invites"}, headers=headers).json()["id"]
    url = f"{BASE}/workspaces/{wid}/invitations"
    first = client.post(url, json={"email": teammate.email}, headers=headers).json()
    second = client.post(url, json={"email": teammate.email}, headers=headers).json()
    accept = BASE + "/workspace-invitations/accept"
    assert client.post(accept, json={"token": first["token"]}, headers=member_headers).status_code == 400
    assert client.delete(url + f"/{second['id']}", headers=headers).status_code == 200
    assert client.post(accept, json={"token": second["token"]}, headers=member_headers).status_code == 400
    third = client.post(url, json={"email": teammate.email}, headers=headers).json()
    db.get(PMSWorkspaceInvitation, third["id"]).expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post(accept, json={"token": third["token"]}, headers=member_headers).status_code == 400
    assert client.post(url, json={"email": teammate.email, "role": "Owner"}, headers=headers).status_code == 422
    assert client.post(BASE + "/workspaces", json={"name": "No"}, headers=member_headers).status_code == 403


def test_workspace_notes_and_chat_permissions(client, db):
    owner, headers = account(db, "notes-owner@test.com", True)
    outsider, other = account(db, "notes-outsider@test.com", True)
    guest, guest_headers = account(db, "notes-guest@test.com")
    wid = client.post(BASE + "/workspaces", json={"name": "Team"}, headers=headers).json()["id"]
    db.add(PMSWorkspaceMember(workspace_id=wid, user_id=guest.id, role="Guest"))
    db.commit()
    url = f"{BASE}/workspaces/{wid}/entries"
    assert client.post(url, json={"kind": "note", "body": "Meeting decisions"}, headers=headers).status_code == 201
    assert client.post(url, json={"kind": "chat", "body": "Ready for review"}, headers=headers).status_code == 201
    assert [e["kind"] for e in client.get(url, headers=guest_headers).json()] == ["note", "chat"]
    assert client.get(url, headers=other).status_code == 404
    assert client.post(url, json={"kind": "chat", "body": "Denied"}, headers=guest_headers).status_code == 403
    assert client.post(url, json={"kind": "note", "body": "   "}, headers=headers).status_code == 422
    assert client.post(url, json={"kind": "chat", "body": "Invalid link", "task_id": 999999}, headers=headers).status_code == 422
