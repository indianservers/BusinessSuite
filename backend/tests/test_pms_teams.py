from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE


def test_workspace_teams_permissions_membership_and_scope(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/teams"
    payload = {"name": "Audit reviewers", "alias": "audit-reviewers", "member_ids": [owner.id, member.id]}
    for headers in [mh, gh]:
        assert client.post(path, headers=headers, json=payload).status_code == 403
    response = client.post(path, headers=ah, json=payload)
    assert response.status_code == 201, response.text
    team = response.json()
    assert set(team["member_ids"]) == {owner.id, member.id}
    assert client.get(path, headers=mh).json()["can_manage"] is False
    assert client.post(path, headers=oh, json=payload).status_code == 409
    assert client.put(path + f"/{team['id']}", headers=oh, json={**payload, "member_ids": [guest.id]}).status_code == 422
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other teams"}).json()["id"]
    assert client.get(f"{BASE}/workspaces/{other}/teams", headers=mh).status_code == 404
    assert client.put(f"{BASE}/workspaces/{other}/teams/{team['id']}", headers=oh, json=payload).status_code == 404
    updated = client.put(path + f"/{team['id']}", headers=oh, json={**payload, "name": "Audit leads", "member_ids": [owner.id]})
    assert updated.status_code == 200 and updated.json()["member_ids"] == [owner.id]
