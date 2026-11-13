"""Native project-name choices in private cited message conversations."""
import asyncio
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_agent_message_events import prepare,send
from tests.test_agent_events import control
from tests.test_bot_artifacts import command
from tests.test_suite_operator import approve,tick
from app.ai_operator import agent_events as events,agent_schedules as schedules
from app.apps.automation.models import AutomationScheduledJob as Job
from app.apps.project_management.models import PMSProject,PMSTask
ROOT='/api/v1/ai-operator/suite'


def setup(client,db,lookup=True):
    h,user,other,oh,path,review,spec=prepare(client,db,message_read=True,write_tool=True,project_lookup=lookup)
    workspace=review['workspace_id'];control(client,h,review,'activate');send(client,path,oh)
    instant=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert asyncio.run(events.dispatch(db,client.app,instant))['processed']==1
    assert asyncio.run(schedules.dispatch(db,client.app,instant+timedelta(seconds=2)))['processed']==1
    job=db.query(Job).filter_by(job_type=schedules.KIND).one()
    pending=job.payload_json.get('pending') or job.payload_json['occurrences'][0]
    conversation=pending['conversation_id']
    def say(text):
        return command(client,h,'PMS',text,workspace_id=workspace,conversation_id=conversation,agent_id=spec['agent_id'])
    first=say('Create a PMS task from this message')
    assert first['status']=='needs_clarification' and first['result']['local_nlp']['slots']['_awaiting']=='project_id',first
    return h,user,workspace,say,first


def project(db,user,workspace,name,key):
    branch=db.query(PMSProject).filter_by(workspace_id=workspace).first().branch_id
    row=PMSProject(organization_id=user.organization_id,workspace_id=workspace,name=name,project_key=key,owner_user_id=user.id,branch_id=branch)
    db.add(row);db.commit();return row


def test_message_project_name_finds_late_exact_match_and_keeps_native_workspace_filter(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,workspace,say,first=setup(client,db)
    seed=db.query(PMSProject).filter_by(workspace_id=workspace).first()
    db.add_all([PMSProject(organization_id=user.organization_id,workspace_id=workspace,name=f'Other project {i}',project_key=f'OLDER-{i}',owner_user_id=user.id,branch_id=seed.branch_id) for i in range(105)]);db.commit()
    selected=project(db,user,workspace,'Customer Launch','LATE-LAUNCH')
    observed=[];original=suite.api_call
    async def watch(*args,**kwargs):
        if args[2]=='GET' and args[3]=='/project-management/projects':observed.append(args[4])
        return await original(*args,**kwargs)
    monkeypatch.setattr(suite,'api_call',watch)
    result=say('Use project "Customer Launch"')
    assert result['status']=='needs_clarification',result
    assert result['result']['request']['project_id']==selected.id
    assert result['result']['local_nlp']['slots']['_awaiting']=='title'
    assert result['result']['citations'][0]['id']==first['result']['citations'][0]['id']
    assert observed==[{'workspace_id':workspace,'name':'Customer Launch','skip':0,'limit':6}]
    # The native exact-name filter is optional and retains normal workspace access.
    response=client.get('/api/v1/project-management/projects',headers=h,params={'workspace_id':workspace,'name':'customer launch','limit':6})
    assert response.status_code==200 and [r['id'] for r in response.json()]==[selected.id],response.text


@pytest.mark.parametrize('reply',['the second one','2'])
def test_ambiguous_project_names_use_fresh_ordinal_choice_and_create_once(client,db,reply):
    h,user,workspace,say,first=setup(client,db)
    one=project(db,user,workspace,'Delivery Recovery','RECOVERY-A');two=project(db,user,workspace,'Delivery Recovery','RECOVERY-B')
    before=db.query(PMSTask).count()
    choices=say('Delivery Recovery')
    assert choices['status']=='needs_clarification' and choices['result']['request']['project_id'] is None,choices
    assert [r['id'] for r in choices['result']['project_selection']['choices']]==[one.id,two.id]
    assert 'second' in choices['plan']['question'] and db.query(PMSTask).count()==before
    selected=say(reply)
    assert selected['status']=='needs_clarification' and selected['result']['request']['project_id']==two.id,selected
    assert selected['result']['local_nlp']['slots']['_awaiting']=='title'
    draft=say('Confirm recovery deadline')
    assert draft['status']=='awaiting_approval' and draft['plan']['steps'][0]['record_id']==two.id,draft
    assert draft['result']['citations'][0]['id']==first['result']['citations'][0]['id']
    assert db.query(PMSTask).count()==before
    approve(client,h,draft);tick(client,db);tick(client,db)
    final=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==1,final
    assert db.query(PMSTask).count()==before+1
    assert db.query(PMSTask).filter_by(project_id=two.id,title='Confirm recovery deadline').count()==1


def test_changed_project_choices_require_fresh_review_instead_of_rebinding_ordinal(client,db):
    h,user,workspace,say,first=setup(client,db)
    one=project(db,user,workspace,'Service Transition','TRANSITION-A');two=project(db,user,workspace,'Service Transition','TRANSITION-B')
    choices=say('Service Transition');assert choices['status']=='needs_clarification',choices
    two.name='Renamed Service Transition';db.commit()
    stale=say('the second one')
    assert stale['status']=='needs_clarification' and stale['result']['request']['project_id'] is None,stale
    assert 'changed' in stale['plan']['question']
    assert [r['id'] for r in stale['result']['project_selection']['choices']]==[one.id]
    selected=say('Service Transition')
    assert selected['status']=='needs_clarification' and selected['result']['request']['project_id']==one.id,selected


def test_unselected_project_lookup_never_reads_names_and_explicit_id_still_works(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,workspace,say,first=setup(client,db,False)
    selected=db.query(PMSProject).filter_by(workspace_id=workspace).first()
    original=suite.api_call
    async def watch(*args,**kwargs):
        assert not(args[2]=='GET' and args[3]=='/project-management/projects'),'Project lookup is not selected'
        return await original(*args,**kwargs)
    monkeypatch.setattr(suite,'api_call',watch)
    result=say(selected.name)
    assert result['status']=='needs_clarification' and result['result']['request']['project_id'] is None,result
    assert 'enable the project lookup' in result['plan']['question']
    direct=say(f'project #{selected.id}')
    assert direct['status']=='needs_clarification' and direct['result']['request']['project_id']==selected.id,direct



def test_project_access_epoch_change_blocks_old_choices_without_creating_a_task(client,db):
    h,user,workspace,say,first=setup(client,db)
    one=project(db,user,workspace,'Private Transition','PRIVATE-A');two=project(db,user,workspace,'Private Transition','PRIVATE-B')
    before=db.query(PMSTask).count()
    choices=say('Private Transition');assert choices['status']=='needs_clarification',choices
    two.deleted_at=datetime.now(timezone.utc);db.commit()
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'workspace_id':workspace,'conversation_id':first['result']['request']['conversation_id'],'agent_id':first['result']['request']['agent_id'],'text':'the second one'})
    assert response.status_code in (403,404),response.text
    assert db.query(PMSTask).count()==before


def test_missing_name_and_overflow_choices_never_silently_select_a_project(client,db):
    h,user,workspace,say,first=setup(client,db)
    before=db.query(PMSTask).count()
    missing=say('Unlisted customer rollout')
    assert missing['status']=='needs_clarification'
    assert missing['result']['request']['project_id'] is None
    assert 'No accessible project' in missing['plan']['question']
    projects=[project(db,user,workspace,'Regional Rollout',f'REGION-{i}') for i in range(6)]
    choices=say('Regional Rollout')
    packet=choices['result']['project_selection']
    assert choices['status']=='needs_clarification' and packet['more'] is True
    assert [row['id'] for row in packet['choices']]==[row.id for row in projects[:5]]
    outside=say('6')
    assert outside['status']=='needs_clarification'
    assert outside['result']['request']['project_id'] is None
    assert 'not in the current choices' in outside['plan']['question']
    explicit=say(f'project #{projects[5].id}')
    assert explicit['status']=='needs_clarification'
    assert explicit['result']['request']['project_id']==projects[5].id
    assert explicit['result']['local_nlp']['slots']['_awaiting']=='title'
    assert db.query(PMSTask).count()==before
