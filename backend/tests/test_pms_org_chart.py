from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from app.apps.project_management.models import PMSWorkspaceMember


def test_org_chart_reporting_cycles_roles_and_revision(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/org-chart"
    initial = client.get(path, headers=mh)
    assert initial.status_code == 200, initial.text
    data = initial.json()
    assert data['revision'] == 0 and not data['can_manage']
    assert len(data['people']) == 3 and all(p['manager_id'] is None for p in data['people'])
    assert guest.id not in [p['id'] for p in data['people']]
    edit = {'revision': 0, 'manager_id': owner.id, 'display_name': 'Alex Collaborator', 'job_title': 'Reviewer'}
    for headers in [mh, gh]:
        assert client.put(path + f'/{member.id}', headers=headers, json=edit).status_code == 403
    saved = client.put(path + f'/{member.id}', headers=ah, json=edit)
    assert saved.status_code == 200, saved.text
    data = saved.json()
    person = next(p for p in data['people'] if p['id'] == member.id)
    assert person['name'] == 'Alex Collaborator' and person['job_title'] == 'Reviewer'
    assert person['manager_id'] == owner.id and person['role'] == 'Member'
    assert client.put(path + f'/{member.id}', headers=oh, json=edit).status_code == 409
    assert client.put(path + f'/{owner.id}', headers=oh, json={**edit, 'revision': 1, 'manager_id': member.id}).status_code == 422
    assert client.put(path + f'/{member.id}', headers=oh, json={**edit, 'revision': 1, 'manager_id': member.id}).status_code == 422
    reset = client.put(path + f'/{member.id}', headers=oh, json={**edit, 'revision': 1, 'manager_id': None})
    assert reset.status_code == 200 and reset.json()['revision'] == 2
    assert all(p['manager_id'] is None for p in reset.json()['people'])
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=member.id).one().role == 'Member'


def test_org_chart_workspace_inactive_guest_and_stale_manager(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/org-chart"
    other, other_headers = account(db, 'outsider-chart@test.com')
    assert client.get(path, headers=other_headers).status_code == 404
    assert client.get(path).status_code in [401, 403]
    for manager in [other.id, guest.id]:
        result = client.put(path + f'/{member.id}', headers=oh, json={'revision': 0, 'manager_id': manager})
        assert result.status_code == 422
    assert client.put(path + f'/{guest.id}', headers=oh, json={'revision': 0}).status_code == 422
    result = client.put(path + f'/{member.id}', headers=oh, json={'revision': 0, 'manager_id': owner.id})
    assert result.status_code == 200
    db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=owner.id).delete()
    db.commit()
    data = client.get(path, headers=ah).json()
    assert next(p for p in data['people'] if p['id'] == member.id)['manager_id'] is None
    assert owner.id not in [p['id'] for p in data['people']]
    member.is_active = False
    db.commit()
    assert member.id not in [p['id'] for p in client.get(path, headers=ah).json()['people']]


def test_org_chart_teams_and_indirect_cycle(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/org-chart"
    admin = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role='Admin').one().user_id
    team = client.post(f'{BASE}/workspaces/{wid}/teams', headers=oh, json={'name': 'Reviewers', 'alias': 'reviewers', 'member_ids': [member.id, admin]}).json()
    client.put(path + f'/{admin}', headers=oh, json={'revision': 0, 'manager_id': owner.id})
    client.put(path + f'/{member.id}', headers=oh, json={'revision': 1, 'manager_id': admin})
    result = client.put(path + f'/{owner.id}', headers=oh, json={'revision': 2, 'manager_id': member.id})
    assert result.status_code == 422
    data = client.get(path, headers=mh).json()
    assert data['revision'] == 2
    assert next(p for p in data['people'] if p['id'] == member.id)['teams'] == [{'id': team['id'], 'name': 'Reviewers'}]
    assert client.put(path + f'/{member.id}', headers=oh, json={'revision': 2, 'display_name': 'x' * 121}).status_code == 422
