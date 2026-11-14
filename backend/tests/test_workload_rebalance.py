from types import SimpleNamespace
import pytest
from app.ai_operator.workload_rebalance import recommend


def native(loads, capacity, efforts):
    return {'rows': [{'user_id': uid, 'cells': [
        {'week_start': week, 'planned_hours': amount, 'capacity_hours': capacity[uid, week],
         'tasks': [{'id': tid, 'planned_hours': hours}
                   for (owner, wk, tid), hours in efforts.items() if owner == uid and wk == week]}
        for (owner, week), amount in loads.items() if owner == uid]}
        for uid in sorted({uid for uid, _ in loads})]}


def test_whole_task_move_preserves_other_assignees_and_reduces_overload():
    value = native({(1,'w'): 30, (2,'w'): 5, (3,'w'): 10},
                   {(1,'w'): 20, (2,'w'): 20, (3,'w'): 20},
                   {(1,'w',7): 10, (3,'w',7): 10})
    steps, changes, skipped = recommend(value, [SimpleNamespace(id=7, assignee_user_ids=[1,3])], [2])
    assert steps[0]['changes']['assignee_user_ids'] == [2,3]
    assert changes[0]['weeks'][0]['source_after_hours'] == 20
    assert changes[0]['weeks'][0]['target_after_hours'] == 15
    assert skipped == []


def test_recipient_must_have_headroom_in_every_week():
    value = native({(1,'a'): 30, (1,'b'): 30, (2,'a'): 0, (2,'b'): 19},
        {(1,'a'): 20, (1,'b'): 20, (2,'a'): 20, (2,'b'): 20},
        {(1,'a',7): 10, (1,'b',7): 10})
    steps, changes, skipped = recommend(value, [SimpleNamespace(id=7, assignee_user_ids=[1])], [2])
    assert steps == changes == [] and skipped[0]['task_id'] == 7


def test_prior_moves_consume_recipient_headroom():
    value = native({(1,'w'): 40, (2,'w'): 5}, {(1,'w'): 20, (2,'w'): 20},
                   {(1,'w',7): 10, (1,'w',8): 10})
    steps, _, skipped = recommend(value,
        [SimpleNamespace(id=tid, assignee_user_ids=[1]) for tid in [8,7]], [2])
    assert [step['task_id'] for step in steps] == [7]
    assert skipped[0]['task_id'] == 8


def test_recommendation_endpoint_never_changes_native_tasks(client, db):
    from tests.test_workload_intelligence import setup_load
    from app.apps.project_management.models import PMSTask
    h, user, pid, _, _, tid = setup_load(client, db)
    before = list(db.get(PMSTask, tid).assignee_user_ids)
    response = client.post(f'/api/v1/ai-operator/suite/pms/workload/{pid}/rebalance', headers=h,
        json={'start':'2026-05-04', 'task_ids':[tid], 'candidate_user_ids':[user.id]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['plan'] is None and result['requires_review']
    assert len(result['workload_guard']['source_sha256']) == 64
    db.expire_all()
    assert db.get(PMSTask, tid).assignee_user_ids == before


from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


@pytest.mark.parametrize('manual_change,recovery_surface',[(False,'workbench'),(True,'workbench'),(False,'conversation'),(False,'revoked'),(False,'latest'),(False,'latest_followup')])
def test_native_recommendation_review_and_atomic_assignment(client, db, manual_change, recovery_surface):
    from datetime import date
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from app.apps.project_management.models import PMSTask, PMSProjectMember, PMSSprint
    from app.ai_operator.jobs import process_batch
    from app.ai_operator.models import OperatorRun
    h, user, pid, workspace, _, tid = setup_load(client, db)
    recipient_headers, recipient = auth_headers(client, db, email=f'rebalance-{uuid4()}@example.com',
                                permissions=['pms_view'])
    db.add(PMSProjectMember(project_id=pid, user_id=recipient.id, role='Member'))
    sprint = PMSSprint(project_id=pid, name='Tiny sprint budget', start_date=date(2026,5,4),
                       end_date=date(2026,5,8), capacity_hours=2)
    db.add(sprint)
    db.flush()
    db.get(PMSTask, tid).sprint_id = sprint.id
    db.commit()
    root = '/api/v1/ai-operator'
    response = client.post(root+f'/suite/pms/workload/{pid}/rebalance', headers=h,
        json={'start':'2026-05-04', 'task_ids':[tid], 'candidate_user_ids':[recipient.id]})
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal['plan']['steps'][0]['changes']['assignee_user_ids'] == [recipient.id]
    assert proposal['changes'][0]['weeks'][0]['target_snapshot_capacity_hours'] == 40
    assert proposal['changes'][0]['weeks'][0]['target_after_hours'] == 30
    assert db.get(PMSTask, tid).assignee_user_ids == [user.id]
    preview = client.post(root+'/workbench/plans/preview', headers=h, json={
        'project_id':pid, 'request_key':str(uuid4()), 'mode':proposal['mode'],
        'plan':proposal['plan'], 'workload_guard':proposal['workload_guard']})
    assert preview.status_code == 200, preview.text
    run = preview.json()
    assert run['status'] == 'awaiting_approval'
    assert db.get(PMSTask, tid).assignee_user_ids == [user.id]
    approved = client.post(root+f'/runs/{run["id"]}/approve', headers=h,
                          json={'plan_hash':run['plan_hash']})
    assert approved.status_code == 200, approved.text
    process_batch(db, run_ids=[run['id']], include_schedulers=False)
    db.expire_all()
    assert db.get(OperatorRun, run['id']).status == 'succeeded'
    assert db.get(PMSTask, tid).assignee_user_ids == [recipient.id]
    current = client.get(root+f'/suite/pms/workload/{pid}', headers=h, params={'start':'2026-05-04'})
    assert current.status_code == 200, current.text
    recipient_load = next(row for row in current.json()['rows'] if row['user_id']==recipient.id)
    assert recipient_load['capacity_hours'] == 40 and recipient_load['planned_hours'] == 30
    assert db.get(PMSTask, tid).sprint_id == sprint.id
    from app.ai_operator.workbench_models import AssistantArtifact
    state=db.query(AssistantArtifact).filter_by(kind='run_state',key=f'run:{run["id"]}').first()
    assert state and state.payload.get('after'), {'state_exists':bool(state),'payload_keys':list(state.payload) if state else []}
    foreign=client.post(root+f'/workbench/runs/{run["id"]}/undo-preview',headers=recipient_headers)
    assert foreign.status_code in {403,404},foreign.text
    original_context=dict(db.get(OperatorRun,run['id']).security_context)
    db.get(OperatorRun,run['id']).security_context={**original_context,'signature':'0'*64};db.commit()
    tampered=client.post(root+f'/workbench/runs/{run["id"]}/undo-preview',headers=h)
    assert tampered.status_code==409,tampered.text
    db.get(OperatorRun,run['id']).security_context=original_context;db.commit()
    if recovery_surface=='revoked':
        from app.apps.project_management.models import PMSProject
        user.is_superuser=False
        user.role.permissions=[permission for permission in user.role.permissions if not permission.name.startswith('pms_')]
        db.get(PMSProject,pid).manager_user_id=None
        db.query(PMSProjectMember).filter_by(project_id=pid,user_id=user.id).delete(synchronize_session=False)
        db.commit()
        denied=client.post(root+f'/workbench/runs/{run["id"]}/undo-preview',headers=h)
        assert denied.status_code in {403,404},denied.text
        db.expire_all()
        assert db.get(PMSTask,tid).assignee_user_ids==[recipient.id]
        return
    if recovery_surface in {'conversation','latest','latest_followup'}:
        from tests.test_suite_operator import approve as approve_suite,tick
        from app.ai_operator.suite_models import SuiteRun
        request={'request_key':str(uuid4()),'provider':'local','module':'PMS','workspace_id':workspace,
            'project_id':pid,'text':f'Undo PMS run #{run["id"]}' if recovery_surface=='conversation' else 'Undo the last PMS change'}
        if recovery_surface=='latest_followup':
            chat=client.post(root+'/suite/conversations',headers=h,json={'title':'Fresh recovery question','workspace_id':workspace})
            assert chat.status_code==201,chat.text
            request.pop('project_id');request['conversation_id']=chat.json()['id']
            question=client.post(root+'/suite/commands',headers=h,json=request)
            assert question.status_code==200,question.text
            assert question.json()['status']=='needs_clarification',question.json()
            request.update(request_key=str(uuid4()),text=f'project {pid}')
        recovered=client.post(root+'/suite/commands',headers=h,json=request)
        assert recovered.status_code==200,recovered.text
        recovery=recovered.json()
        assert recovery['status']=='awaiting_approval',recovery
        assert recovery['result']['pms_recovery_request']['run_id']==run['id']
        assert recovery['plan']['steps'][0]['tool']=='pms.task_plan'
        assert recovery['plan']['steps'][0]['payload']['workload_guard']
        assert db.get(PMSTask,tid).assignee_user_ids==[recipient.id]
        approve_suite(client,h,recovery);tick(client,db)
        process_batch(db,include_schedulers=False)
        waiting=client.get(root+f'/suite/runs/{recovery["id"]}',headers=h)
        assert waiting.status_code==200,waiting.text
        assert waiting.json()['status']=='waiting_pms' and waiting.json()['receipts']==[]
        tick(client,db)
        db.expire_all()
        assert db.get(SuiteRun,recovery['id']).status=='succeeded'
        assert db.get(PMSTask,tid).assignee_user_ids==[user.id]
        visible=client.get(root+f'/suite/runs/{recovery["id"]}',headers=h)
        assert visible.status_code==200,visible.text
        assert visible.json()['status']=='succeeded'
        projected=visible.json()
        assert projected['result']['history_restricted'] is True
        assert projected['plan']['steps']==[] and not projected['approval_id']
        assert 'pms_recovery_request' not in projected['result']
        assert recovery['command'] not in visible.text
        foreign=client.get(root+f'/suite/runs/{recovery["id"]}',headers=recipient_headers)
        assert foreign.status_code in {403,404}
        if recovery_surface=='conversation':
            from app.apps.project_management.models import PMSProject
            user.is_superuser=False
            user.role.permissions=[permission for permission in user.role.permissions if not permission.name.startswith('pms_')]
            db.get(PMSProject,pid).manager_user_id=None
            db.query(PMSProjectMember).filter_by(project_id=pid,user_id=user.id).delete(synchronize_session=False)
            db.commit()
            revoked=client.get(root+f'/suite/runs/{recovery["id"]}',headers=h)
            assert revoked.status_code in {403,404},revoked.text
        return
    if manual_change:
        changed=client.patch(f'/api/v1/project-management/tasks/{tid}',headers=h,json={'assignee_user_ids':[user.id]})
        assert changed.status_code==200,changed.text
    inverse=client.post(root+f'/workbench/runs/{run["id"]}/undo-preview',headers=h)
    if manual_change:
        assert inverse.status_code==409,inverse.text
        return
    assert inverse.status_code==200,inverse.text
    undo=inverse.json()['run']
    assert undo['status']=='awaiting_approval'
    assert undo['workload_guard']['source_sha256']!=proposal['workload_guard']['source_sha256']
    assert undo['plan']['steps'][0]['changes']['assignee_user_ids']==[user.id]
    assert db.get(PMSTask,tid).assignee_user_ids==[recipient.id]
    approved=client.post(root+f'/runs/{undo["id"]}/approve',headers=h,json={'plan_hash':undo['plan_hash']})
    assert approved.status_code==200,approved.text
    process_batch(db,run_ids=[undo['id']],include_schedulers=False)
    db.expire_all()
    assert db.get(OperatorRun,undo['id']).status=='succeeded'
    assert db.get(PMSTask,tid).assignee_user_ids==[user.id]
    replay=client.post(root+f'/workbench/runs/{run["id"]}/undo-preview',headers=h)
    assert replay.status_code==200,replay.text
    assert replay.json()['run']['id']==undo['id']


def test_recommendation_rejects_unavailable_candidate_and_other_project_task(client, db):
    from uuid import uuid4
    from tests.test_workload_intelligence import setup_load
    h, user, pid, _, _, tid = setup_load(client, db)
    endpoint = f'/api/v1/ai-operator/suite/pms/workload/{pid}/rebalance'
    body = {'start':'2026-05-04', 'task_ids':[tid], 'candidate_user_ids':[9223372036854775807]}
    assert client.post(endpoint, headers=h, json=body).status_code == 422
    project = client.post('/api/v1/project-management/projects', headers=h,
        json={'name':'Other rebalance project', 'project_key':uuid4().hex[:12]})
    assert project.status_code == 200, project.text
    other = client.post(f'/api/v1/project-management/projects/{project.json()["id"]}/tasks',
        headers=h, json={'title':'Other project task', 'task_key':uuid4().hex[:12]})
    assert other.status_code == 200, other.text
    response = client.post(endpoint, headers=h,
        json={**body, 'task_ids':[other.json()['id']], 'candidate_user_ids':[user.id]})
    assert response.status_code == 422, response.text


def test_local_rebalance_conversation_retains_inputs_across_followups(client, db):
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    first = say(client, h, chat, 'Rebalance workload', module='PMS',
                project_id=pid, task_ids=[tid], workspace_id=workspace)
    assert first['status'] == 'needs_clarification', first
    assert 'collaborators' in first['plan']['question']
    second = say(client, h, chat, f'candidates={user.id}', module='PMS', workspace_id=workspace)
    assert second['status'] == 'needs_clarification', second
    assert 'Monday' in second['plan']['question']
    third = say(client, h, chat, 'start=2026-05-04', module='PMS', workspace_id=workspace)
    assert third['status'] == 'answered', third
    assert 'No whole-task reassignment' in third['plan']['summary']
    assert third['result']['rebalance_request']['task_ids'] == [tid]
    assert third['result']['rebalance_request']['candidate_user_ids'] == [user.id]


def test_local_rebalance_conversation_prepares_reviewed_action(client, db):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    from tests.test_suite_operator import approve, tick
    from app.apps.project_management.models import PMSProjectMember, PMSTask
    from app.ai_operator.suite_models import SuiteRun
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    _, recipient = auth_headers(client, db, email=f'rebalance-chat-{uuid4()}@example.com',
        permissions=['pms_view'])
    db.add(PMSProjectMember(project_id=pid, user_id=recipient.id, role='Member'))
    db.commit()
    run = say(client, h, chat,
        f'Rebalance workload: tasks=Synthetic open work; candidates={recipient.id}; start=2026-05-04',
        module='PMS', project_id=pid, workspace_id=workspace)
    assert run['status'] == 'awaiting_approval', run
    assert run['plan']['steps'][0]['tool'] == 'pms.task_plan'
    assert run['plan']['steps'][0]['payload']['workload_guard']['source_sha256']
    review = run['result']['rebalance_request']['review']
    assert review['source_sha256'] == run['plan']['steps'][0]['payload']['workload_guard']['source_sha256']
    assert review['changes'][0]['before_assignee_user_ids'] == [user.id]
    assert review['changes'][0]['after_assignee_user_ids'] == [recipient.id]
    assert review['changes'][0]['weeks'][0]['target_after_hours'] == 30
    db.expire_all()
    assert db.get(PMSTask, tid).assignee_user_ids == [user.id]
    approve(client, h, run)
    tick(client, db)
    from app.ai_operator.jobs import process_batch
    process_batch(db, include_schedulers=False)
    tick(client, db)
    db.expire_all()
    assert db.get(SuiteRun, run['id']).status == 'succeeded'
    assert db.get(PMSTask, tid).assignee_user_ids == [recipient.id]


def test_named_recipient_and_ambiguous_name_followup(client, db):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    from app.apps.project_management.models import PMSProjectMember
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    _, first = auth_headers(client, db, email=f'rebalance-name-{uuid4()}@example.com', permissions=['pms_view'])
    first.person.display_name = 'Ravi Sharma'
    db.add(PMSProjectMember(project_id=pid, user_id=first.id, role='Member'))
    db.commit()
    initial = say(client, h, chat, 'Rebalance workload with Ravi', module='PMS',
        project_id=pid, task_ids=[tid], workspace_id=workspace)
    assert initial['status'] == 'needs_clarification', initial
    assert initial['result']['rebalance_request']['candidate_user_ids'] == [first.id]
    # A second eligible person with the same first name must prevent guessing.
    _, second = auth_headers(client, db, email=f'rebalance-name-{uuid4()}@example.com', permissions=['pms_view'])
    second.person.display_name = 'Ravi Rao'
    db.add(PMSProjectMember(project_id=pid, user_id=second.id, role='Member'))
    db.commit()
    ambiguous = say(client, h, chat, 'start=2026-05-04', module='PMS', workspace_id=workspace)
    assert ambiguous['status'] == 'needs_clarification', ambiguous
    assert 'More than one' in ambiguous['plan']['question']
    assert str(first.id) in ambiguous['plan']['question'] and str(second.id) in ambiguous['plan']['question']
    final = say(client, h, chat, 'Ravi Sharma', module='PMS', workspace_id=workspace)
    assert final['status'] == 'awaiting_approval', final
    payload = final['plan']['steps'][0]['payload']
    assert payload['plan']['steps'][0]['changes']['assignee_user_ids'] == [first.id]


def test_name_resolution_does_not_offer_noncollaborators(client, db):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, _, pid, workspace, chat, tid = setup_load(client, db)
    _, outsider = auth_headers(client, db, email=f'nonmember-{uuid4()}@example.com', permissions=['pms_view'])
    outsider.person.display_name = 'Unique Outside Collaborator'
    db.commit()
    run = say(client, h, chat, 'Rebalance workload with Unique Outside Collaborator',
        module='PMS', project_id=pid, task_ids=[tid], workspace_id=workspace)
    assert run['status'] == 'needs_clarification', run
    assert 'No eligible project collaborator' in run['plan']['question']
    assert not run['result']['rebalance_request']['candidate_user_ids']


def test_duplicate_task_titles_require_selection_and_task_key_resolves(client, db):
    from tests.test_workload_intelligence import setup_load, task
    from tests.test_suite_workspace import say
    from app.apps.project_management.models import PMSTask
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    duplicate = task(client, h, pid, user.id, 'Synthetic open work', 5)
    ambiguous = say(client, h, chat,
        f'Rebalance workload: tasks=Synthetic open work; candidates={user.id}; start=2026-05-04',
        module='PMS', project_id=pid, workspace_id=workspace)
    assert ambiguous['status'] == 'needs_clarification', ambiguous
    assert 'More than one project task' in ambiguous['plan']['question']
    assert str(tid) in ambiguous['plan']['question'] and str(duplicate) in ambiguous['plan']['question']
    key = db.get(PMSTask, tid).task_key
    final = say(client, h, chat, key, module='PMS', workspace_id=workspace)
    assert final['status'] == 'answered', final
    assert final['result']['rebalance_request']['task_ids'] == [tid]


def test_task_titles_are_resolved_only_in_selected_project(client, db):
    from uuid import uuid4
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, _ = setup_load(client, db)
    project = client.post('/api/v1/project-management/projects', headers=h,
        json={'name':'Other title scope', 'project_key':uuid4().hex[:12]})
    assert project.status_code == 200, project.text
    value = client.post(f'/api/v1/project-management/projects/{project.json()["id"]}/tasks',
        headers=h, json={'title':'Outside selected project only', 'task_key':uuid4().hex[:12]})
    assert value.status_code == 200, value.text
    run = say(client, h, chat,
        f'Rebalance workload: tasks=Outside selected project only; candidates={user.id}; start=2026-05-04',
        module='PMS', project_id=pid, workspace_id=workspace)
    assert run['status'] == 'needs_clarification', run
    assert 'No current task in this project' in run['plan']['question']
    assert not run['result']['rebalance_request']['task_ids']


def test_missing_project_and_task_can_be_collected_in_separate_followups(client, db):
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    first = say(client, h, chat, 'Rebalance workload', module='PMS', workspace_id=workspace)
    assert first['status'] == 'needs_clarification'
    assert 'Which project' in first['plan']['question']
    second = say(client, h, chat, f'project={pid}', module='PMS', workspace_id=workspace)
    assert second['status'] == 'needs_clarification', second
    assert second['result']['request']['project_id'] == pid
    third = say(client, h, chat, f'tasks={tid}', module='PMS', workspace_id=workspace)
    assert third['status'] == 'needs_clarification', third
    assert third['result']['request']['task_ids'] == [tid]
    final = say(client, h, chat, f'candidates={user.id}; start=2026-05-04', module='PMS', workspace_id=workspace)
    assert final['status'] == 'answered', final


def test_selected_tasks_cannot_switch_during_rebalance_clarification(client, db):
    from uuid import uuid4
    from tests.test_workload_intelligence import setup_load, task
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    other = task(client, h, pid, user.id, 'Other candidate task', 5)
    first = say(client, h, chat, f'Rebalance workload: tasks={tid}',
                module='PMS', project_id=pid, workspace_id=workspace)
    assert first['status'] == 'needs_clarification', first
    response = client.post('/api/v1/ai-operator/suite/commands', headers=h, json={
        'request_key':str(uuid4()), 'provider':'local', 'conversation_id':chat, 'module':'PMS',
        'workspace_id':workspace, 'text':f'tasks={other}; candidates={user.id}; start=2026-05-04'})
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'A follow-up must retain its selected tasks'


def test_plain_answers_fill_only_the_pending_rebalance_question(client, db):
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    user.person.display_name='Arjun Rao'
    db.commit()
    run = say(client, h, chat, 'Rebalance workload', module='PMS', workspace_id=workspace)
    assert run['result']['rebalance_request']['_awaiting'] == 'project'
    run = say(client, h, chat, f'project {pid}', module='PMS', workspace_id=workspace)
    assert run['result']['rebalance_request']['_awaiting'] == 'tasks'
    run = say(client, h, chat, 'Synthetic open work', module='PMS', workspace_id=workspace)
    assert run['result']['rebalance_request']['_awaiting'] == 'candidates'
    run = say(client, h, chat, 'Arjun', module='PMS', workspace_id=workspace)
    assert run['result']['rebalance_request']['_awaiting'] == 'start'
    run = say(client, h, chat, '2026-05-04', module='PMS', workspace_id=workspace)
    assert run['status'] == 'answered', run
    draft = run['result']['rebalance_request']
    assert draft['task_ids'] == [tid] and draft['candidate_user_ids'] == [user.id]
    assert draft['start'] == '2026-05-04' and '_awaiting' not in draft


@pytest.mark.parametrize('reply,offset', [('this week',0), ('next week',1)])
def test_relative_week_reply_uses_conversation_timezone(client, db, reply, offset):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    timezone='Pacific/Kiritimati'
    initial = say(client, h, chat, f'Rebalance workload: tasks={tid}; candidates={user.id}',
        module='PMS', project_id=pid, workspace_id=workspace, timezone=timezone)
    assert initial['result']['rebalance_request']['_awaiting'] == 'start'
    today = datetime.now(ZoneInfo(timezone)).date()
    monday = today-timedelta(days=today.weekday())+timedelta(weeks=offset)
    final = say(client, h, chat, reply, module='PMS', workspace_id=workspace)
    assert final['status'] == 'answered', final
    assert final['result']['rebalance_request']['start'] == monday.isoformat()
    assert final['result']['request']['timezone'] == timezone


def test_invalid_initial_week_can_be_corrected_with_plain_date(client, db):
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h, user, pid, workspace, chat, tid = setup_load(client, db)
    initial = say(client, h, chat,
        f'Rebalance workload: tasks={tid}; candidates={user.id}; start=2026-05-05',
        module='PMS', project_id=pid, workspace_id=workspace)
    assert initial['status'] == 'needs_clarification'
    assert initial['result']['rebalance_request']['_awaiting'] == 'start'
    final = say(client, h, chat, '2026-05-04', module='PMS', workspace_id=workspace)
    assert final['status'] == 'answered', final
    assert final['result']['rebalance_request']['start'] == '2026-05-04'


def test_planner_can_read_rebalance_tool_without_creating_an_action(client, db, monkeypatch):
    import json
    from uuid import uuid4
    from tests.test_workload_intelligence import setup_load
    from tests.test_ai_operator import mock_provider
    from app.ai_operator.planning_catalog import available
    from app.apps.project_management.models import PMSTask
    h, user, pid, workspace, _, tid = setup_load(client, db)
    offered = available(db, user, workspace, module='PMS')
    tool = next(item for item in offered if item['name']=='pms.rebalance_workload')
    assert tool['approval_required'] is False
    calls = mock_provider(monkeypatch, {'summary':'There is no alternate recipient in this selection.',
        'question':'Which other collaborator may receive work?', 'steps':[]})
    response = client.post('/api/v1/ai-operator/suite/commands', headers=h, json={
        'request_key':str(uuid4()), 'provider':'gemini', 'module':'PMS', 'workspace_id':workspace,
        'text':'Inspect assignment recommendations and ask about an alternate recipient.',
        'context':[{'tool':'pms.rebalance_workload', 'record_id':pid, 'payload':{
            'start':'2026-05-04', 'task_ids':[tid], 'candidate_user_ids':[user.id]}}]})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'needs_clarification', response.json()
    outbound = json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    source = next(item['records'] for item in outbound['authorized_context'] if item['tool']=='pms.rebalance_workload')
    assert source['plan'] is None and source['requires_review'] is True
    assert len(source['workload_guard']['source_sha256']) == 64
    db.expire_all()
    assert db.get(PMSTask, tid).assignee_user_ids == [user.id]


@pytest.mark.parametrize('drop_guard', [False, True])
def test_gemini_recommendation_action_preserves_guard_before_execution(client, db, monkeypatch, drop_guard):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from tests.test_ai_operator import mock_provider
    from tests.test_suite_operator import approve, tick
    from app.apps.project_management.models import PMSProjectMember, PMSTask
    from app.ai_operator.jobs import process_batch
    from app.ai_operator.suite_models import SuiteRun
    h, user, pid, workspace, _, tid = setup_load(client, db)
    _, recipient = auth_headers(client, db, email=f'planner-rebalance-{uuid4()}@example.com', permissions=['pms_view'])
    db.add(PMSProjectMember(project_id=pid,user_id=recipient.id,role='Member'))
    db.commit()
    payload={'start':'2026-05-04','task_ids':[tid],'candidate_user_ids':[recipient.id]}
    source=client.get(f'/api/v1/ai-operator/suite/pms/workload/{pid}/rebalance',headers=h,params=payload)
    assert source.status_code==200,source.text
    value=source.json()
    action={'plan':value['plan'],'mode':'atomic'}
    if not drop_guard:action['workload_guard']=value['workload_guard']
    mock_provider(monkeypatch,{'summary':'Review estimated-workload reassignment',
        'steps':[{'tool':'pms.task_plan','record_id':pid,'payload':action}]})
    response=client.post('/api/v1/ai-operator/suite/commands',headers=h,json={
        'request_key':str(uuid4()),'provider':'gemini','module':'PMS','workspace_id':workspace,
        'text':'Prepare the recommended assignment for review.',
        'context':[{'tool':'pms.rebalance_workload','record_id':pid,'payload':payload}]})
    assert response.status_code==200,response.text
    run=response.json()
    db.expire_all()
    assert db.get(PMSTask,tid).assignee_user_ids==[user.id]
    if drop_guard:
        assert run['status']=='failed',run
        assert not db.get(SuiteRun,run['id']).approval_id
        return
    assert run['status']=='awaiting_approval',run
    assert run['result']['rebalance_review']['changes'][0]['after_assignee_user_ids']==[recipient.id]
    assert run['result']['rebalance_review']['source_sha256']==value['workload_guard']['source_sha256']
    approve(client,h,run)
    tick(client,db)
    process_batch(db,include_schedulers=False)
    tick(client,db)
    db.expire_all()
    assert db.get(SuiteRun,run['id']).status=='succeeded'
    assert db.get(PMSTask,tid).assignee_user_ids==[recipient.id]


@pytest.mark.parametrize('tool',['pms.run_playbook','pms.undo'])
def test_recommendation_guard_cannot_be_bypassed_through_assignment_alias(tool):
    from fastapi import HTTPException
    from app.ai_operator.workload_rebalance import enforce_source_guards
    guard={'start':'2026-05-04','weeks':1,'scope':'project','source_sha256':'a'*64}
    context=[{'tool':'pms.rebalance_workload','record_id':1,'records':{'workload_guard':guard}}]
    plan=SimpleNamespace(steps=[SimpleNamespace(tool=tool,record_id=1,payload={})])
    with pytest.raises(HTTPException) as error:enforce_source_guards(plan,context)
    assert error.value.status_code==422


def test_every_task_action_in_a_multi_step_plan_must_retain_its_source_guard():
    from fastapi import HTTPException
    from app.ai_operator.workload_rebalance import enforce_source_guards
    guard={'start':'2026-05-04','weeks':1,'scope':'project','source_sha256':'a'*64}
    context=[{'tool':'pms.rebalance_workload','record_id':1,'records':{'workload_guard':guard}}]
    first=SimpleNamespace(tool='pms.task_plan',record_id=1,payload={'workload_guard':guard})
    second=SimpleNamespace(tool='pms.task_plan',record_id=1,payload={})
    with pytest.raises(HTTPException) as error:
        enforce_source_guards(SimpleNamespace(steps=[first,second]),context)
    assert error.value.status_code==422
    second.payload['workload_guard']=guard
    assert enforce_source_guards(SimpleNamespace(steps=[first,second]),context) is None


@pytest.mark.parametrize('stage',['parent_approval','child_approval','child_execution'])
def test_stale_workload_stops_parent_child_workflow_without_assignments(client, db, stage):
    from uuid import uuid4
    from datetime import date
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    from tests.test_suite_operator import tick
    from app.apps.project_management.models import PMSProjectMember, PMSUserCapacity, PMSTask
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.models import OperatorRun
    from app.ai_operator.jobs import process_batch
    h,user,pid,workspace,chat,tid=setup_load(client,db)
    _,recipient=auth_headers(client,db,email=f'stale-parent-{uuid4()}@example.com',permissions=['pms_view'])
    db.add(PMSProjectMember(project_id=pid,user_id=recipient.id,role='Member'));db.commit()
    run=say(client,h,chat,f'Rebalance workload: tasks={tid}; candidates={recipient.id}; start=2026-05-04',
        module='PMS',project_id=pid,workspace_id=workspace)
    assert run['status']=='awaiting_approval',run
    child=run['pms_previews']['1']['id']
    def approve_parent():
        return client.post(f'/api/v1/ai-operator/suite/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    if stage!='parent_approval':
        response=approve_parent();assert response.status_code==200,response.text
    if stage=='child_execution':
        tick(client,db)
        assert db.get(SuiteRun,run['id']).status=='waiting_pms'
    capacity=db.query(PMSUserCapacity).filter_by(user_id=user.id,week_start_date=date(2026,5,4)).one()
    capacity.capacity_hours=5;db.commit()
    if stage=='parent_approval':
        response=approve_parent();assert response.status_code==409,response.text
        assert db.get(SuiteRun,run['id']).status=='awaiting_approval'
        assert db.get(OperatorRun,child).status=='awaiting_approval'
    else:
        if stage=='child_execution':process_batch(db,run_ids=[child],include_schedulers=False)
        tick(client,db)
        db.expire_all()
        parent=db.get(SuiteRun,run['id'])
        assert parent.status=='paused',parent.error_code
        assert not parent.receipts
        resumed=client.post(f'/api/v1/ai-operator/suite/runs/{run["id"]}/resume',headers=h,
            json={'plan_hash':run['plan_hash']})
        assert resumed.status_code==409,resumed.text
        db.expire_all()
        assert db.get(SuiteRun,run['id']).status=='paused'
    db.expire_all()
    assert db.get(PMSTask,tid).assignee_user_ids==[user.id]
    if stage=='child_approval':
        capacity=db.query(PMSUserCapacity).filter_by(user_id=user.id,week_start_date=date(2026,5,4)).one()
        capacity.capacity_hours=20;db.commit()
        resumed=client.post(f'/api/v1/ai-operator/suite/runs/{run["id"]}/resume',headers=h,
            json={'plan_hash':run['plan_hash']})
        assert resumed.status_code==200,resumed.text
        tick(client,db)
        process_batch(db,run_ids=[child],include_schedulers=False)
        tick(client,db)
        db.expire_all()
        assert db.get(SuiteRun,run['id']).status=='succeeded'
        assert db.get(PMSTask,tid).assignee_user_ids==[recipient.id]


@pytest.mark.parametrize('can_manage',[False,True])
def test_rebalance_discovery_matches_task_assignment_capability(client, db, can_manage):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load
    from app.ai_operator.planning_catalog import available
    from app.ai_operator.suite import check_tool_access
    from fastapi import HTTPException
    setup_load(client,db)
    permissions=['ai_assistant','pms_view']+(['pms_manage_tasks'] if can_manage else [])
    _,actor=auth_headers(client,db,email=f'rebalance-access-{uuid4()}@example.com',permissions=permissions)
    # Fixture requests share one Session; the new permission was inserted after
    # setup_load cached its catalog. Real requests receive a fresh Session.
    db.info.pop('suite_access_catalog',None)
    names={item['name'] for item in available(db,actor,None,module='PMS')}
    assert 'pms.workload' in names
    assert ('pms.rebalance_workload' in names)==can_manage
    assert ('pms.task_plan' in names)==can_manage
    if not can_manage:
        with pytest.raises(HTTPException) as error:check_tool_access(db,actor,None,'pms.rebalance_workload')
        assert error.value.status_code==403


def test_latest_recovery_uses_completion_time_and_excludes_other_users_and_projects(client, db):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load, task
    from tests.test_suite_workspace import say
    from app.ai_operator.jobs import process_batch
    h,user,pid,workspace,chat,first_task=setup_load(client,db)
    other_headers,_=auth_headers(client,db,email=f'other-executor-{uuid4()}@example.com',
        permissions=['ai_assistant','ai_manage_settings','pms_manage_tasks','pms_manage_projects','settings_manage'])
    second_task=task(client,h,pid,user.id,'Independent second task',1)
    def draft(headers,project,tid,priority):
        response=client.post('/api/v1/ai-operator/workbench/plans/preview',headers=headers,json={
            'project_id':project,'request_key':str(uuid4()),'mode':'atomic',
            'plan':{'summary':'Synthetic ordering case','steps':[{'tool':'update_task','task_id':tid,'changes':{'priority':priority}}]}})
        assert response.status_code==200,response.text
        return response.json()
    def finish(headers,run):
        response=client.post(f'/api/v1/ai-operator/runs/{run["id"]}/approve',headers=headers,json={'plan_hash':run['plan_hash']})
        assert response.status_code==200,response.text
        process_batch(db,run_ids=[run['id']],include_schedulers=False)
        from app.ai_operator.models import OperatorRun
        db.expire_all()
        assert db.get(OperatorRun,run['id']).status=='succeeded'
    older_id=draft(h,pid,first_task,'High')
    newer_id=draft(h,pid,second_task,'Urgent')
    finish(h,newer_id);finish(h,older_id)
    assert older_id['id']<newer_id['id']
    foreign=draft(other_headers,pid,second_task,'Low');finish(other_headers,foreign)
    project=client.post('/api/v1/project-management/projects',headers=h,
        json={'name':'Separate latest scope','project_key':uuid4().hex[:12]})
    assert project.status_code==200,project.text
    other_pid=project.json()['id']
    other_task=task(client,h,other_pid,user.id,'Other project change',1)
    elsewhere=draft(h,other_pid,other_task,'Urgent');finish(h,elsewhere)
    fresh=client.post('/api/v1/ai-operator/suite/conversations',headers=h,
        json={'title':'Fresh latest-execution selection','workspace_id':workspace})
    assert fresh.status_code==201,fresh.text
    chat=fresh.json()['id']
    selected=say(client,h,chat,'Undo the last PMS change',module='PMS',project_id=pid,workspace_id=workspace)
    assert selected['status']=='awaiting_approval',selected
    assert selected['result']['pms_recovery_request']['run_id']==older_id['id']


def test_latest_recovery_without_completed_execution_retains_project_and_makes_no_action(client, db):
    from tests.test_workload_intelligence import setup_load
    from tests.test_suite_workspace import say
    h,_,pid,workspace,chat,_=setup_load(client,db)
    first=say(client,h,chat,'Undo the last PMS change',module='PMS',workspace_id=workspace)
    assert first['status']=='needs_clarification'
    result=say(client,h,chat,str(pid),module='PMS',workspace_id=workspace)
    assert result['status']=='answered',result
    assert not result['plan']['steps'] and not result['approval_id']
    assert result['result']['request']['project_id']==pid
    assert 'No completed AI task execution' in result['plan']['summary']


@pytest.mark.parametrize('remaining_tool',['priority','comment','queued','inactive_assignee','race_cancelled','race_plan_changed'])
def test_partial_pms_workflow_exposes_only_confirmed_receipt_after_acl_change(client, db, remaining_tool, monkeypatch):
    from uuid import uuid4
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load, task
    from tests.test_suite_operator import prepare,approve,tick
    from app.ai_operator.jobs import process_batch
    from app.ai_operator.models import OperatorRun
    from app.ai_operator.suite_models import SuiteRun
    from app.apps.project_management.models import PMSProjectMember,PMSTask
    h,user,pid,workspace,_,tid=setup_load(client,db)
    # Receipt-only history is the ordinary owner's contract. Company/platform
    # administrators now have a separate company-wide GET inspection policy.
    user.is_superuser=False;db.commit()
    _,recipient=auth_headers(client,db,email=f'partial-receipt-{uuid4()}@example.com',permissions=['pms_view'])
    db.add(PMSProjectMember(project_id=pid,user_id=recipient.id,role='Member'));db.commit()
    second=task(client,h,pid,user.id,'Private unfinished task intention',1)
    before=db.get(PMSTask,second).priority
    source=client.get(f'/api/v1/ai-operator/suite/pms/workload/{pid}/rebalance',headers=h,
        params={'start':'2026-05-04','task_ids':[tid],'candidate_user_ids':[recipient.id]})
    assert source.status_code==200,source.text
    value=source.json()
    remaining_step={'tool':'update_task','task_id':second,'changes':{'priority':'Urgent'}} if remaining_tool!='comment' else {
        'tool':'add_comment','task_id':second,'body':'Restricted unposted source content'}
    if remaining_tool=='inactive_assignee':remaining_step['changes']={'assignee_user_ids':[recipient.id]}
    run=prepare(client,h,[{'tool':'pms.task_plan','record_id':pid,'payload':{
        'plan':value['plan'],'mode':'atomic','workload_guard':value['workload_guard']}},
        {'tool':'pms.task_plan','record_id':pid,'depends_on':[1],'payload':{'plan':{
            'summary':'Private unfinished task intention','steps':[remaining_step]},'mode':'atomic'}}],
        project_id=pid,task_ids=[tid,second],workspace_id=workspace)
    assert run['status']=='awaiting_approval',run
    approve(client,h,run);tick(client,db)
    child=run['pms_previews']['1']['id'];pending=run['pms_previews']['2']['id']
    if remaining_tool=='queued':
        pending_row=db.get(OperatorRun,pending)
        queued=client.post(f'/api/v1/ai-operator/runs/{pending}/approve',headers=h,json={'plan_hash':pending_row.plan_hash})
        assert queued.status_code==200,queued.text
    process_batch(db,run_ids=[child],include_schedulers=False);tick(client,db)
    db.expire_all()
    assert db.get(SuiteRun,run['id']).status=='paused'
    response=client.get(f'/api/v1/ai-operator/suite/runs/{run["id"]}',headers=h)
    assert response.status_code==200,response.text
    safe=response.json()
    assert safe['status']=='paused' and safe['result']['history_restricted']
    assert len(safe['receipts'])==1 and safe['receipts'][0]['pms_run_id']==child
    assert len(safe['result_cards'])==1
    assert safe['workflow_steps'][0]['status']=='succeeded'
    assert safe['workflow_steps'][1]['status']=='not_confirmed'
    assert '1 of 2' in safe['plan']['summary'] and 'Remaining workflow completion is not confirmed' in safe['plan']['summary']
    assert 'Private unfinished task intention' not in response.text
    assert not safe['can_resume'] and safe['approval_id'] is None
    if remaining_tool in {'priority','inactive_assignee','race_cancelled','race_plan_changed'}:
        assert safe['result']['remaining_review_prompt']==f'Review remaining PMS workflow #{run["id"]}'
    else:assert 'remaining_review_prompt' not in safe['result']
    expected='queued' if remaining_tool=='queued' else 'awaiting_approval'
    assert db.get(OperatorRun,pending).status==expected
    assert db.get(PMSTask,second).priority==before
    if remaining_tool=='inactive_assignee':recipient.is_active=False;db.commit()
    request={'request_key':str(uuid4()),'provider':'local','module':'PMS','workspace_id':workspace,
        'project_id':pid,'text':f'Review remaining PMS workflow #{run["id"]}'}
    if remaining_tool.startswith('race_'):
        from sqlalchemy import update
        from app.ai_operator import remaining_tasks
        reserve=remaining_tasks.reserve
        def changed_before_lock(session,actor,replacement,packet):
            # Deterministically emulate a write committed after prepare read the
            # source. SQL bypasses this request's identity map, as another
            # transaction would. This is not a parallel load test.
            cached=session.get(SuiteRun,run['id'])
            assert cached.status=='paused'
            change={'status':'cancelled'} if remaining_tool=='race_cancelled' else {'plan_hash':'f'*64}
            session.execute(update(SuiteRun).where(SuiteRun.id==cached.id).values(**change),
                            execution_options={'synchronize_session':False})
            assert cached.status=='paused' and cached.plan_hash==run['plan_hash']
            reserve(session,actor,replacement,packet)
        monkeypatch.setattr(remaining_tasks,'reserve',changed_before_lock)
    replacement=client.post('/api/v1/ai-operator/suite/commands',headers=h,json=request)
    if remaining_tool.startswith('race_'):
        assert replacement.status_code==200,replacement.text
        failed=replacement.json()
        assert failed['status']=='failed',failed
        assert failed['error_code']=='AI_POLICY_HTTP_409'
        db.expire_all()
        source_row=db.get(SuiteRun,run['id'])
        # The injected SQL belongs to the reservation savepoint and is rolled
        # back with it. A real competing transaction retains its own change.
        assert source_row.status=='paused' and source_row.plan_hash==run['plan_hash']
        assert 'remaining_review_id' not in source_row.result
        assert db.get(OperatorRun,pending).status=='awaiting_approval'
        for preview in failed['pms_previews'].values():
            assert db.get(OperatorRun,preview['id']).status=='cancelled'
        assert db.get(PMSTask,second).priority==before
        return
    if remaining_tool in {'comment','queued','inactive_assignee'}:
        assert replacement.status_code in {409,422},replacement.text
        assert 'Restricted unposted source content' not in replacement.text
        assert db.get(SuiteRun,run['id']).status=='paused'
        assert db.get(OperatorRun,pending).status==expected
        return
    assert replacement.status_code==200,replacement.text
    fresh=replacement.json()
    assert fresh['status']=='awaiting_approval',fresh
    assert len(fresh['plan']['steps'])==1
    assert fresh['plan']['steps'][0]['payload']['plan']['steps'][0]['task_id']==second
    db.expire_all()
    assert db.get(SuiteRun,run['id']).status=='superseded'
    assert db.get(OperatorRun,pending).status=='cancelled'
    assert db.get(PMSTask,second).priority==before
    duplicate=client.post('/api/v1/ai-operator/suite/commands',headers=h,json={**request,'request_key':str(uuid4())})
    assert duplicate.status_code==409,duplicate.text
    old=client.get(f'/api/v1/ai-operator/suite/runs/{run["id"]}',headers=h)
    assert old.status_code==200,old.text
    assert len(old.json()['receipts'])==1 and old.json()['status']=='superseded'
    approve(client,h,fresh);tick(client,db)
    fresh_child=fresh['pms_previews']['1']['id']
    process_batch(db,run_ids=[fresh_child],include_schedulers=False);tick(client,db)
    db.expire_all()
    assert db.get(SuiteRun,fresh['id']).status=='succeeded'
    assert db.get(PMSTask,second).priority=='Urgent'
    assert db.get(PMSTask,tid).assignee_user_ids==[recipient.id]
