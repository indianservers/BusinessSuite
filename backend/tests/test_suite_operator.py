import asyncio
from uuid import uuid4
from datetime import timedelta
import pytest
from tests.test_ai_operator import setup_operator, mock_provider, isolate_generic_http_audit
from ai_test_utils import auth_headers
from app.ai_operator.suite import process_suite_batch, now
from app.ai_operator.suite_models import SuiteRun
from app.ai_operator.models import OperatorProvider, OperatorApiLog
from app.ai_operator.provider_scope import resolve_provider
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
from app.apps.crm.models import CRMTask
from app.apps.fam.models import FAMCostCenter

ROOT = '/api/v1/ai-operator/suite'


def setup_suite(client, db):
    h, user, p, t = setup_operator(client, db, provider="gemini")
    user.is_superuser = True
    db.commit()
    return h, user, p, t


def prepare(client, headers, steps, **extra):
    response = client.post(ROOT+'/commands', headers=headers, json={'request_key': str(uuid4()), 'text': 'Review suite work',
        'local_plan': {'summary': 'Create reviewed suite records', 'steps': steps}, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def tick(client, db):
    return asyncio.run(process_suite_batch(db, client.app))


def approve(client, h, run):
    r = client.post(ROOT+f'/runs/{run["id"]}/approve', headers=h, json={'plan_hash': run['plan_hash']})
    assert r.status_code == 200, r.text


def test_cross_module_plan_uses_canonical_apis_and_new_record_references(client, db):
    h, _, _, _ = setup_suite(client, db)
    run = prepare(client, h, [
        {'tool': 'fam.create_cost_center', 'payload': {'code': 'QA', 'name': 'QA delivery'}},
        {'tool': 'crm.create_task', 'payload': {'title': 'Review delivery'}},
        {'tool': 'crm.update_task', 'record_id': {'$step': 2, 'field': 'id'}, 'payload': {'priority': 'High'}},
    ])
    assert run['status'] == 'awaiting_approval'
    assert db.query(CRMTask).count() == 0 and db.query(FAMCostCenter).count() == 0
    assert client.post(ROOT+f'/runs/{run["id"]}/approve', headers=h, json={'plan_hash': '0'*64}).status_code == 409
    approve(client, h, run)
    assert tick(client, db) == 3
    db.expire_all()
    final = client.get(ROOT+f'/runs/{run["id"]}', headers=h).json()
    assert final['status'] == 'succeeded', final
    assert len(final['receipts']) == 3
    assert db.query(CRMTask).one().priority == 'High'
    assert db.query(FAMCostCenter).filter_by(code='QA').count() == 1
    approve(client, h, final)
    assert tick(client, db) == 0 and db.query(CRMTask).count() == 1


def test_suite_generation_uses_gemini_and_scoped_usage(client, db, monkeypatch):
    h, user, _, _ = setup_suite(client, db)
    mock_provider(monkeypatch, {'summary': 'Draft a CRM follow-up', 'steps': [{'tool': 'crm.create_task', 'payload': {'title': 'Review'}}]})
    r = client.post(ROOT+'/commands', headers=h, json={'request_key': str(uuid4()), 'text': 'Create CRM follow-up task Review'})
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'awaiting_approval', r.text
    log = db.query(OperatorApiLog).filter_by(user_id=user.id).one()
    assert log.provider == 'gemini' and log.suite_run_id == r.json()['id'] and log.module == 'CRM'
    assert db.query(CRMTask).count() == 0


def test_suite_read_context_checks_canonical_permissions(client, db, monkeypatch):
    h, _, _, _ = setup_suite(client, db)
    calls = mock_provider(monkeypatch, {'summary': 'No records', 'steps': []})
    member, _ = auth_headers(client, db, email=f'{uuid4()}@example.com', permissions=['ai_assistant'])
    r = client.post(ROOT+'/commands', headers=member, json={'request_key': str(uuid4()), 'text': 'Summarize finance',
        'context': [{'tool': 'fam.dashboard'}], 'local_plan': {'summary': 'No actions', 'steps': []}})
    assert r.status_code == 200 and r.json()['status'] == 'failed', r.text
    assert '403' in r.json()['error_code']
    assert not calls


@pytest.mark.parametrize('step', [
    {'tool': 'http.post', 'payload': {'url': 'https://example.com'}},
    {'tool': 'crm.create_task', 'payload': {'title': 'Bad', 'organization_id': 999}},
    {'tool': 'fam.create_cost_center', 'payload': {'name': 'Missing code'}},
    {'tool': 'crm.update_task', 'record_id': {'$step': 2, 'field': 'id'}, 'payload': {'priority': 'High'}},
])
def test_suite_rejects_unknown_tools_tenant_injection_missing_fields_and_forward_references(client, db, step):
    h, _, _, _ = setup_suite(client, db)
    run = prepare(client, h, [step])
    assert run['status'] == 'failed', run
    assert db.query(CRMTask).count() == 0


def test_suite_owner_cancel_and_withdrawn_permissions(client, db):
    h, _, _, _ = setup_suite(client, db)
    run = prepare(client, h, [{'tool': 'crm.create_task', 'payload': {'title': 'Review'}}])
    other, _ = auth_headers(client, db, email=f'{uuid4()}@example.com', permissions=['ai_assistant', 'crm_manage'])
    assert client.get(ROOT+f'/runs/{run["id"]}', headers=other).status_code == 404
    assert client.post(ROOT+f'/runs/{run["id"]}/cancel', headers=h).status_code == 200
    assert client.post(ROOT+f'/runs/{run["id"]}/approve', headers=h, json={'plan_hash': run['plan_hash']}).status_code == 409
    assert tick(client, db) == 0


def test_suite_lost_receipt_never_repeats_a_canonical_write(client, db, monkeypatch):
    h, _, _, _ = setup_suite(client, db)
    run = prepare(client, h, [{'tool': 'crm.create_task', 'payload': {'title': 'Write once'}}])
    approve(client, h, run)
    from app.ai_operator import suite
    original = suite.api_call
    async def lost_response(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError('Process lost response after canonical commit')
    monkeypatch.setattr(suite, 'api_call', lost_response)
    assert tick(client, db) == 1
    db.expire_all()
    assert db.query(CRMTask).count() == 1
    assert db.get(SuiteRun, run['id']).status == 'needs_reconciliation'
    assert tick(client, db) == 0 and db.query(CRMTask).count() == 1


def test_suite_stale_target_and_expired_executor_do_not_write(client, db):
    h, _, _, _ = setup_suite(client, db)
    task = client.post('/api/v1/crm/tasks', headers=h, json={'title': 'Original'}).json()
    run = prepare(client, h, [{'tool': 'crm.update_task', 'record_id': task['id'], 'payload': {'priority': 'High'}}])
    approve(client, h, run)
    client.patch(f'/api/v1/crm/tasks/{task["id"]}', headers=h, json={'title': 'Changed elsewhere'})
    tick(client, db)
    db.expire_all()
    assert db.get(SuiteRun, run['id']).status == 'paused'
    assert db.get(CRMTask, task['id']).priority != 'High'
    row = db.get(SuiteRun, run['id']);row.status='executing';row.active_step=1;row.lease_until=now()-timedelta(minutes=1);db.commit()
    assert tick(client, db) == 0
    assert db.get(SuiteRun, run['id']).status == 'needs_reconciliation'


def test_workspace_inheritance_is_opt_in_owner_bound_and_override_blocks(client, db):
    h, user, _, _ = setup_suite(client, db)
    workspace = PMSWorkspace(name='QA owned workspace');db.add(workspace);db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=user.id, role='Owner'));db.commit()
    assert resolve_provider(db, user, 'gemini', workspace.id) is None
    source = db.query(OperatorProvider).filter_by(provider='gemini').one();source.allow_workspace_inheritance=True;db.commit()
    assert resolve_provider(db, user, 'gemini', workspace.id).id == source.id
    member, invited = auth_headers(client, db, email=f'{uuid4()}@example.com', permissions=['ai_assistant'])
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=invited.id, role='Member'));db.commit()
    assert resolve_provider(db, invited, 'gemini', workspace.id).id == source.id
    other = PMSWorkspace(name='Unrelated');db.add(other);db.flush();db.add(PMSWorkspaceMember(workspace_id=other.id,user_id=invited.id,role='Owner'));db.commit()
    assert resolve_provider(db, invited, 'gemini', other.id) is None
    override = OperatorProvider(scope_key=f'workspace:{workspace.id}',provider='gemini',model='override',encrypted_key='unused',enabled=False,data_sharing_allowed=False,updated_by=user.id)
    db.add(override);db.commit()
    assert resolve_provider(db,user,'gemini',workspace.id).id == override.id
    rows=client.get('/api/v1/ai-operator/providers',headers=member,params={'workspace_id':workspace.id}).json()['items']
    assert rows[0]['enabled'] is False and not rows[0]['inherited']


def test_suite_minimization_omits_sensitive_fields():
    from app.ai_operator.suite_tools import minimize
    result=minimize({'items':[{'id':1,'name':'QA','bank_account':'secret','salary':999,'tax_id':'secret','description':'private'}]})
    assert result=={'items':[{'id':1,'name':'QA'}]}


def test_revoked_action_permission_pauses_queued_work(client, db):
    h, user, _, _ = setup_suite(client, db)
    run = prepare(client, h, [{'tool':'crm.create_task','payload':{'title':'Must not create'}}])
    approve(client, h, run)
    user.is_superuser=False
    db.commit()
    tick(client, db)
    db.expire_all()
    assert db.get(SuiteRun, run['id']).status=='paused'
    assert db.query(CRMTask).count()==0


def test_pms_workspace_commands_use_inherited_provider_and_workspace_usage(client, db, monkeypatch):
    from tests.test_ai_operator import plan_for
    h,user,_,_=setup_suite(client,db)
    source=db.query(OperatorProvider).filter_by(provider='gemini').one()
    source.allow_workspace_inheritance=True
    workspace=PMSWorkspace(name='Inherited PMS');db.add(workspace);db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Owner'));db.commit()
    project=client.post('/api/v1/project-management/projects',headers=h,json={'name':'Scoped','project_key':'SCOPED','workspace_id':workspace.id}).json()['id']
    task=client.post(f'/api/v1/project-management/projects/{project}/tasks',headers=h,json={'title':'Scoped task','task_key':'SC-1'}).json()['id']
    mock_provider(monkeypatch,plan_for(task))
    response=client.post('/api/v1/ai-operator/commands',headers=h,json={'project_id':project,'task_ids':[task],
        'provider':'gemini','command':'Set priority high and add QA','request_key':str(uuid4())})
    assert response.status_code==200 and response.json()['status']=='awaiting_approval',response.text
    assert db.query(OperatorApiLog).one().scope_key==f'workspace:{workspace.id}'
    # A suite context read cannot select that project under a different scope.
    blocked=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Read other workspace',
        'context':[{'tool':'pms.tasks','record_id':project}],'local_plan':{'summary':'No changes','steps':[]}})
    assert blocked.status_code==200 and blocked.json()['status']=='failed'


def test_suite_preserves_session_for_case_insensitive_bearer_header(client,db):
    h,_,_,_=setup_suite(client,db)
    token=h['Authorization'].split(' ')[1]
    from app.core.security import verify_access_token
    claims=verify_access_token(token)
    run=prepare(client,{'Authorization':'bearer '+token},[{'tool':'crm.create_task','payload':{'title':'Session bound'}}])
    assert run['status']=='awaiting_approval'
    assert db.get(SuiteRun,run['id']).session_id==int(claims['sid'])


def test_summary_mode_omits_action_catalog_and_cannot_mutate(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    calls=mock_provider(monkeypatch,{'summary':'There are no selected records.'})
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Summarize selected records','mode':'summary'})
    assert r.status_code==200 and r.json()['status']=='answered',r.text
    import json
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    assert outbound['tools']==[]
    assert db.query(OperatorApiLog).one().purpose=='suite_summary'
    blocked=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Summary cannot write','mode':'summary',
        'local_plan':{'summary':'Invalid summary action','steps':[{'tool':'crm.create_task','payload':{'title':'Do not create'}}]}})
    assert blocked.json()['status']=='failed'
    assert db.query(CRMTask).count()==0


def test_suite_does_not_override_a_withdrawn_approval(client,db):
    from app.ai_agents.models import AiActionApproval
    h,_,_,_=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Withdrawn'}}])
    approval=db.get(AiActionApproval,run['approval_id']);approval.status='rejected';db.commit()
    r=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert r.status_code==409
    assert tick(client,db)==0 and db.query(CRMTask).count()==0
