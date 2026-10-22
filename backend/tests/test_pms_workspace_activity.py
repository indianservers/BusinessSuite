from tests.test_pms_workspaces import account, middleware_database, BASE
from app.apps.project_management.models import PMSActivity, PMSWorkspaceMember


def test_workspace_activity_pagination_filters_and_private_access(client, db):
    owner, oh = account(db, "activity-owner@test.com", True)
    outsider, xh = account(db, "activity-outsider@test.com", True)
    member, mh = account(db, "activity-member@test.com")
    wid = client.post(BASE + "/workspaces", json={"name": "Activity audit"}, headers=oh).json()["id"]
    pid = client.post(BASE + "/projects", json={"name": "Audited", "project_key": "AUD", "workspace_id": wid}, headers=oh).json()["id"]
    db.add(PMSWorkspaceMember(workspace_id=wid, user_id=member.id, role="Member"))
    db.add_all([PMSActivity(project_id=pid, actor_user_id=owner.id, action="audit.first", entity_type="project", summary="First event"), PMSActivity(project_id=pid, actor_user_id=owner.id, action="audit.second", entity_type="project", summary="Second event")])
    db.commit()
    url = f"{BASE}/workspaces/{wid}/activity"
    assert client.get(url, headers=xh).status_code == 404
    assert client.get(url, headers=mh).status_code == 403
    page = client.get(url, params={"limit": 1, "action": "audit."}, headers=oh).json()
    assert page["items"][0]["summary"] == "Second event"
    older = client.get(url, params={"limit": 1, "action": "audit.", "before": page["next_cursor"]}, headers=oh).json()
    assert older["items"][0]["summary"] == "First event"
    assert older["next_cursor"] is None
    assert client.get(url, params={"limit": 1000}, headers=oh).status_code == 422
