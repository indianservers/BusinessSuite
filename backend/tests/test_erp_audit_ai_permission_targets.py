import pytest
from ai_test_utils import auth_headers
from tests.rich_text_test_utils import organization_context
from app.ai_agents.models import AiAgent, AiAgentPermission

ROOT = '/api/v1/ai-agents/security'


def setup(client, db):
    headers, actor = auth_headers(client, db, 'matrix-admin@example.com', ['settings_manage'])
    _, local = auth_headers(client, db, 'literal_percent%_matrix@example.com', ['ai_assistant'])
    _, foreign = auth_headers(client, db, 'foreign-matrix@example.com', ['settings_manage'], company_id=2)
    agent = db.query(AiAgent).first()
    assert agent is not None
    return headers, actor, local, foreign, agent


def test_named_targets_are_company_scoped_searchable_and_authorized(client, db):
    headers, actor, local, foreign, _ = setup(client, db)
    response = client.get(ROOT+'/permission-targets', headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert local.id in {row['id'] for row in data['users']}
    assert foreign.id not in {row['id'] for row in data['users']}
    assert local.role_id in {row['id'] for row in data['roles']}
    assert foreign.role_id not in {row['id'] for row in data['roles']}
    for text in ['%', '_', 'LITERAL_PERCENT']:
        found = client.get(ROOT+'/permission-targets', headers=headers, params={'search':text})
        assert found.status_code == 200, found.text
        assert [row['id'] for row in found.json()['users']] == [local.id]
    reader, _ = auth_headers(client, db, 'matrix-reader@example.com', ['ai_assistant'])
    assert client.get(ROOT+'/permission-targets', headers=reader).status_code == 403
    client.cookies.clear()
    assert client.get(ROOT+'/permission-targets').status_code in {401,403}


@pytest.mark.parametrize('invalid', ['foreign_user','foreign_role','unknown_agent','foreign_rule','inactive_user'])
def test_invalid_target_batch_is_atomic(client, db, invalid):
    headers, actor, local, foreign, agent = setup(client, db)
    first = {'agent_id':agent.id, 'user_id':local.id, 'can_use':False}
    bad = {'agent_id':agent.id, 'user_id':actor.id}
    if invalid == 'foreign_user': bad['user_id'] = foreign.id
    if invalid == 'foreign_role': bad.update(user_id=None, role_id=foreign.role_id)
    if invalid == 'unknown_agent': bad['agent_id'] = 2147483647
    if invalid == 'inactive_user':
        local.is_active=False; db.commit(); bad['user_id']=local.id
        first['user_id']=actor.id
    if invalid == 'foreign_rule':
        row = AiAgentPermission(company_id=2, agent_id=agent.id, user_id=foreign.id)
        db.add(row); db.commit(); bad['id']=row.id
    before = db.query(AiAgentPermission).count()
    response = client.put(ROOT+'/permissions', headers=headers, json=[first,bad])
    assert response.status_code == (404 if invalid == 'foreign_rule' else 422), response.text
    assert db.query(AiAgentPermission).count() == before


def test_named_user_rule_persists(client, db):
    headers, _, local, _, agent = setup(client, db)
    response = client.put(ROOT+'/permissions', headers=headers,
        json=[{'agent_id':agent.id,'user_id':local.id,'can_use':False}])
    assert response.status_code == 200, response.text
    response = client.get(ROOT+'/permissions', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()[0]['user_id'] == local.id and not response.json()[0]['can_use']


def test_targets_paginate_and_resolve_saved_selection_without_leaking_company(client, db):
    from app.models.user import User
    from test_identity_utils import attach_test_identity, attach_workflow_branch
    headers, _, local, foreign, _ = setup(client, db)
    for index in range(28):
        row=User(email=f'older-{index:02d}@example.com',hashed_password='unused',role_id=local.role_id,is_active=True)
        db.add(row);db.flush();attach_test_identity(db,row,1);attach_workflow_branch(db,row,1)
    db.commit()
    first=client.get(ROOT+'/permission-targets',headers=headers).json()
    second=client.get(ROOT+'/permission-targets',headers=headers,params={'page':2}).json()
    assert len(first['users'])==25 and first['has_more']
    assert second['users'] and not second['has_more']
    assert not ({r['id'] for r in first['users']} & {r['id'] for r in second['users']})
    selected=second['users'][-1]
    found=client.get(ROOT+'/permission-targets',headers=headers,params={'search':'no-such-person','selected_user':selected['id']}).json()
    assert found['users']==[] and found['selected_user']['id']==selected['id']
    hidden=client.get(ROOT+'/permission-targets',headers=headers,params={'selected_user':foreign.id}).json()
    assert hidden['selected_user'] is None
