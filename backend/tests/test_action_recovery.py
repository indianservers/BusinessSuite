"""Server-selected inverses require current access, unchanged records and fresh review."""
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_suite_conversations import create,say,ROOT
from tests.test_pms_agent import complete
from app.ai_operator.action_recovery import intent
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask
from app.apps.project_management.models import PMSTask
from app.models.employee import Employee
from datetime import date


@pytest.mark.parametrize('text',['undo the last change','Undo last action!','revert my last update','roll back that change','undo run #12',
    'undo','Please undo that action.','Can you revert the last update?','Could you please roll back my last edit?', 'undo   the   last   change'])
def test_exact_recovery_commands(text):
    assert intent(text) is not None


@pytest.mark.parametrize('text',['Create a task called undo last change','undo all CRM work','undo run #-1','Please quote "undo the last change"','Delete the last task',
    'undo run #2147483648','undo run #'+('9'*5000)])
def test_recovery_does_not_guess_from_embedded_or_destructive_requests(text):
    assert intent(text) is None


def updated(client,db):
    h,user,p,t=setup_suite(client,db);chat=create(client,h)
    created=client.post('/api/v1/crm/tasks',headers=h,json={'title':'Synthetic recovery task','priority':'Medium'})
    assert created.status_code in (200,201),created.text
    ident=created.json()['id']
    draft=say(client,h,chat,'Raise this CRM task priority',module='CRM',local_plan={'summary':'Review priority',
        'steps':[{'tool':'crm.update_task','record_id':ident,'payload':{'priority':'High'}}]})
    approve(client,h,draft);tick(client,db)
    run=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert run['status']=='succeeded',run
    return h,user,chat,ident,run


def test_conversation_prepares_exact_inverse_and_executes_only_after_review(client,db):
    h,user,chat,ident,source=updated(client,db)
    assert source['result']['recovery_evidence']['1']['before']=={'priority':'Medium'}
    request={'conversation_id':chat,'provider':'local','text':'Undo the last change','request_key':str(uuid4())}
    response=client.post(ROOT+'/commands',headers=h,json=request);assert response.status_code==200,response.text
    inverse=response.json();assert inverse['status']=='awaiting_approval',inverse
    assert inverse['plan']['steps'][0]['payload']=={'priority':'Medium'}
    assert inverse['result']['recovery']['source_run_id']==source['id']
    assert inverse['result']['recovery']['targets'][0]['changes']==[{'field':'priority','current':'High','restore':'Medium'}]
    assert db.get(CRMTask,ident).priority=='High' and not inverse['receipts']
    assert client.post(ROOT+'/commands',headers=h,json=request).json()['id']==inverse['id']
    edit=client.post(ROOT+f'/runs/{inverse["id"]}/revise',headers=h,json={'request_key':str(uuid4()),
        'plan_hash':inverse['plan_hash'],'changes':[{'step':1,'field':'priority','value':'Low'}]})
    assert edit.status_code==409,edit.text
    duplicate=client.post(ROOT+'/commands',headers=h,json={**request,'request_key':str(uuid4())})
    assert duplicate.status_code==409,duplicate.text
    approve(client,h,inverse);tick(client,db);db.refresh(db.get(CRMTask,ident))
    assert db.get(CRMTask,ident).priority=='Medium'
    final=client.get(ROOT+f'/runs/{inverse["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==1
    assert tick(client,db)==0


def test_external_edit_prevents_inverse_preparation(client,db):
    h,_,chat,ident,source=updated(client,db)
    changed=client.patch(f'/api/v1/crm/tasks/{ident}',headers=h,json={'title':'Manual external edit'})
    assert changed.status_code==200,changed.text
    response=client.post(ROOT+'/commands',headers=h,json={'conversation_id':chat,'provider':'local',
        'text':'undo last change','request_key':str(uuid4())})
    assert response.status_code==409,response.text
    db.refresh(db.get(CRMTask,ident));assert db.get(CRMTask,ident).priority=='High'
    assert not db.get(SuiteRun,source['id']).result.get('recovery_preview_id')


def test_external_edit_after_preview_is_not_overwritten(client,db):
    h,_,chat,ident,source=updated(client,db)
    inverse=say(client,h,chat,'undo last change')
    assert client.patch(f'/api/v1/crm/tasks/{ident}',headers=h,json={'title':'Latest manual title'}).status_code==200
    approve(client,h,inverse);tick(client,db)
    final=client.get(ROOT+f'/runs/{inverse["id"]}',headers=h).json()
    assert final['status'] in {'paused','failed'} and not final['receipts'],final
    assert final['error_code']=='CANONICAL_STEP_409'
    db.refresh(db.get(CRMTask,ident));assert db.get(CRMTask,ident).priority=='High'
    assert db.get(CRMTask,ident).title=='Latest manual title'


def test_cancelling_recovery_through_conversation_allows_a_fresh_preview(client,db):
    h,_,chat,ident,source=updated(client,db)
    inverse=say(client,h,chat,'undo last change')
    blocked=client.post(ROOT+'/commands',headers=h,json={'conversation_id':chat,'provider':'local',
        'text':'Make the priority Low instead','request_key':str(uuid4())})
    assert blocked.status_code==409,blocked.text
    answer=say(client,h,chat,'cancel recovery')
    assert answer['status']=='answered' and not answer['plan']['steps']
    assert db.get(SuiteRun,inverse['id']).status=='cancelled'
    again=say(client,h,chat,'undo last change')
    assert again['status']=='awaiting_approval' and again['id']!=inverse['id']
    assert db.get(CRMTask,ident).priority=='High'


def test_legacy_evidence_and_foreign_conversations_do_not_produce_inverse_actions(client,db):
    h,_,chat,ident,source=updated(client,db)
    other=create(client,h)
    invisible=client.post(ROOT+'/commands',headers=h,json={'conversation_id':other,'text':f'undo run #{source["id"]}',
        'provider':'local','request_key':str(uuid4())})
    assert invisible.status_code==404,invisible.text
    record=db.get(SuiteRun,source['id']);record.result={k:v for k,v in record.result.items() if k!='recovery_evidence'};db.commit()
    unsupported=say(client,h,chat,'undo last change')
    assert unsupported['status']=='answered' and not unsupported['plan']['steps']
    assert 'before-values' in unsupported['plan']['summary']
    assert db.get(CRMTask,ident).priority=='High'


@pytest.mark.parametrize('module,tool,payload',[
    ('CRM','crm.create_task',{'title':'Keep this created task'}),
    ('HRMS','hrms.create_ticket',{'subject':'Keep this HR ticket','description':'Synthetic request'})])
def test_creation_and_irreversible_work_are_disclosed_without_deletion(client,db,module,tool,payload):
    h,user,p,_=setup_suite(client,db);chat=create(client,h)
    if module=='HRMS':
        from app.apps.project_management.models import PMSProject
        db.add(Employee(employee_id='RECOVERY-'+str(user.id),user_id=user.id,first_name='Recovery',last_name='Owner',
            date_of_joining=date.today(),branch_id=db.get(PMSProject,p).branch_id));db.commit();db.expire_all()
    draft=say(client,h,chat,'Create reviewed synthetic work',module=module,local_plan={'summary':'Review work','steps':[{'tool':tool,'payload':payload}]})
    approve(client,h,draft);tick(client,db)
    source=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json();assert source['status']=='succeeded',source
    answer=say(client,h,chat,'undo last change')
    assert answer['status']=='answered' and not answer['plan']['steps'] and answer['approval_id'] is None
    assert tool in answer['plan']['summary'] and 'manual recovery' in answer['plan']['summary']


def test_pms_conversation_reuses_native_undo_evidence_and_independent_review(client,db):
    from app.apps.project_management.models import PMSProject
    h,user,p,t=setup_suite(client,db)
    workspace=db.get(PMSProject,p).workspace_id
    response=client.post(ROOT+'/conversations',headers=h,json={'title':'PMS recovery','workspace_id':workspace})
    assert response.status_code==201,response.text
    chat=response.json()['id'];before=db.get(PMSTask,t).priority
    draft=say(client,h,chat,'Raise task priority',module='PMS',workspace_id=workspace,project_id=p,
        local_plan={'summary':'Review one priority','steps':[{'tool':'pms.task_plan','record_id':p,
            'payload':{'plan':{'summary':'Raise priority','steps':[{'tool':'update_task','task_id':t,'changes':{'priority':'High'}}]}}}]})
    source=complete(client,db,h,draft);assert source['status']=='succeeded',source
    inverse=say(client,h,chat,'Undo last change',workspace_id=workspace)
    assert inverse['status']=='awaiting_approval' and inverse['pms_previews'],inverse
    db.refresh(db.get(PMSTask,t));assert db.get(PMSTask,t).priority=='High'
    restored=complete(client,db,h,inverse);assert restored['status']=='succeeded',restored
    db.refresh(db.get(PMSTask,t));assert db.get(PMSTask,t).priority==before


def test_last_action_recovery_survives_a_bounded_conversation_history_window(client,db,monkeypatch):
    from app.ai_operator import suite_conversations
    h,_,chat,ident,source=updated(client,db)
    answer=say(client,h,chat,'what changed?');assert answer['status']=='answered'
    original=suite_conversations.runs
    monkeypatch.setattr(suite_conversations,'runs',lambda db,user,row,limit=100:original(db,user,row,limit=1))
    inverse=say(client,h,chat,'undo last change')
    assert inverse['status']=='awaiting_approval' and inverse['result']['recovery']['source_run_id']==source['id']
    assert db.get(CRMTask,ident).priority=='High'


def test_one_conversation_recovers_a_completed_crm_and_pms_workflow_in_reverse_order(client,db):
    from app.apps.project_management.models import PMSProject
    from app.ai_operator.jobs import process_batch
    h,_,p,t=setup_suite(client,db);workspace=db.get(PMSProject,p).workspace_id
    r=client.post(ROOT+'/conversations',headers=h,json={'title':'Cross-module recovery','workspace_id':workspace})
    assert r.status_code==201,r.text
    chat=r.json()['id']
    task=client.post('/api/v1/crm/tasks',headers=h,json={'title':'CRM workflow recovery','priority':'Medium'})
    assert task.status_code in (200,201),task.text
    ident=task.json()['id'];pms_before=db.get(PMSTask,t).priority
    draft=say(client,h,chat,'Raise both priorities',module='PMS',workspace_id=workspace,project_id=p,
        local_plan={'summary':'Review cross-module priority changes','steps':[
            {'tool':'crm.update_task','record_id':ident,'payload':{'priority':'High'}},
            {'tool':'pms.task_plan','record_id':p,'payload':{'plan':{'summary':'Raise priority',
                'steps':[{'tool':'update_task','task_id':t,'changes':{'priority':'High'}}]}}}]})
    def drain(run):
        approve(client,h,run)
        for _ in range(6):
            tick(client,db);process_batch(db)
            current=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
            if current['status']=='succeeded':return current
            assert current['status'] in {'queued','executing','waiting_pms'},current
        pytest.fail('Workflow did not complete within its bounded execution steps')
    source=drain(draft)
    inverse=say(client,h,chat,'Undo last change',workspace_id=workspace)
    assert [s['tool'] for s in inverse['plan']['steps']]==['pms.task_plan','crm.update_task']
    assert inverse['result']['recovery']['source_run_id']==source['id']
    assert db.get(CRMTask,ident).priority=='High'
    result=drain(inverse);assert len(result['receipts'])==2
    db.expire_all()
    assert db.get(CRMTask,ident).priority=='Medium' and db.get(PMSTask,t).priority==pms_before


def test_recovery_preserves_explicit_null_for_previously_unset_native_fields(client,db):
    h,_,_,_=setup_suite(client,db);chat=create(client,h)
    created=client.post('/api/v1/crm/tasks',headers=h,json={'title':'Unset fields recovery'})
    assert created.status_code in (200,201),created.text
    ident=created.json()['id'];assert created.json()['description'] is None and created.json()['due_date'] is None
    draft=say(client,h,chat,'Add details and deadline',module='CRM',local_plan={'summary':'Review details',
        'steps':[{'tool':'crm.update_task','record_id':ident,'payload':{'description':'Temporary description','due_date':'2027-01-20T12:00:00+00:00'}}]})
    approve(client,h,draft);tick(client,db)
    source=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json();assert source['status']=='succeeded',source
    inverse=say(client,h,chat,'undo last change');assert inverse['status']=='awaiting_approval',inverse
    assert inverse['plan']['steps'][0]['payload']=={'description':None,'due_date':None}
    approve(client,h,inverse);tick(client,db)
    final=client.get(ROOT+f'/runs/{inverse["id"]}',headers=h).json();assert final['status']=='succeeded',final
    db.expire_all();assert db.get(CRMTask,ident).description is None and db.get(CRMTask,ident).due_date is None


def test_compound_or_ambiguous_undo_does_not_silently_become_an_unrelated_update(client,db):
    h,_,chat,ident,source=updated(client,db)
    answer=say(client,h,chat,'Please undo the last change and set the deadline tomorrow')
    assert answer['status']=='answered' and not answer['plan']['steps'] and answer['approval_id'] is None
    assert 'Request recovery separately' in answer['plan']['summary']
    assert db.get(CRMTask,ident).priority=='High'
    inverse=say(client,h,chat,'Undo last change');assert inverse['status']=='awaiting_approval'


def test_uncertain_latest_attempt_is_not_skipped_after_a_readonly_followup(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,chat,ident,source=updated(client,db)
    draft=say(client,h,chat,'Prepare a new task',module='CRM',local_plan={'summary':'Review new task',
        'steps':[{'tool':'crm.create_task','payload':{'title':'Unconfirmed recovery fixture'}}]})
    approve(client,h,draft)
    original=suite.api_call
    async def lost_response(*args,**kwargs):
        result=await original(*args,**kwargs)
        if args[2]=='POST':raise TimeoutError('Synthetic response lost after commit')
        return result
    monkeypatch.setattr(suite,'api_call',lost_response)
    tick(client,db)
    monkeypatch.setattr(suite,'api_call',original)
    uncertain=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert uncertain['status']=='needs_reconciliation' and not uncertain['receipts'],uncertain
    assert db.query(CRMTask).count()==2
    say(client,h,chat,'what changed?')
    answer=say(client,h,chat,'undo last change')
    assert answer['status']=='answered' and not answer['plan']['steps'] and 'incomplete' in answer['plan']['summary']
    assert db.get(CRMTask,ident).priority=='High' and db.query(CRMTask).count()==2


def test_explicit_native_plan_is_not_reinterpreted_from_its_conversational_caption(client,db):
    h,_,chat,ident,source=updated(client,db)
    another=create(client,h)
    draft=say(client,h,another,'Undo the last change',module='CRM',local_plan={'summary':'Review explicitly supplied update',
        'steps':[{'tool':'crm.update_task','record_id':ident,'payload':{'priority':'Medium'}}]})
    assert draft['status']=='awaiting_approval' and not draft['receipts']
    assert not draft['result'].get('recovery') and db.get(CRMTask,ident).priority=='High'
