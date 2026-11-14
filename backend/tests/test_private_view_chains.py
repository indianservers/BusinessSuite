from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite,prepare,approve,tick,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from tests.test_private_view_changes import view_case,get
from app.ai_operator import suite
from app.ai_operator.suite_models import SuiteRun
from app.models.user import User


def chain(client,h,module,path,view):
    baseline=client.get(path,headers=h).json()['revision']
    first={'tool':module.lower()+'.update_saved_view','payload':{'view_id':view['id'],'revision':baseline,'name':'First revision','filters':{**view['filters'],'priority':'Low'}}}
    second={'tool':module.lower()+'.update_saved_view','payload':{'view_id':view['id'],'revision':baseline,'name':'Final revision','filters':{**view['filters'],'priority':'Medium'}}}
    return prepare(client,h,[first,second]),baseline


def test_same_target_projection_freezes_sequential_before_after_and_dependencies(client,db,view_case):
    h,module,path,view,_=view_case;draft,baseline=chain(client,h,module,path,view)
    assert draft['status']=='awaiting_approval'
    assert draft['plan']['steps'][1]['depends_on']==[1]
    changes=draft['result']['view_changes']['2']['changes']
    assert {'field':'priority','before':'Low','after':'Medium'} in changes
    approve(client,h,draft);tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded',done.get('error_code')
    assert [r['view_revision'] for r in done['receipts']]==[baseline+1,baseline+2]
    assert client.get(path,headers=h).json()['items'][0]['name']=='Final revision'
    approve(client,h,done);tick(client,db);assert client.get(path,headers=h).json()['revision']==baseline+2


@pytest.mark.parametrize('lost_step',[1,2])
def test_chain_recovers_committed_step_then_continues_without_duplicate(client,db,monkeypatch,view_case,lost_step):
    h,module,path,view,_=view_case;draft,baseline=chain(client,h,module,path,view);approve(client,h,draft)
    original=suite.finish_step
    def lost(db,run,index,tool,response):
        if index==lost_step:raise RuntimeError('Synthetic lost chained view receipt')
        return original(db,run,index,tool,response)
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    stopped=get(client,h,draft);assert stopped['status']=='needs_reconciliation' and stopped['can_resume']
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']});assert response.status_code==200,response.text
    tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded' and len(done['receipts'])==2,done.get('error_code')
    assert client.get(path,headers=h).json()['revision']==baseline+2


@pytest.mark.parametrize('tamper',['change','remove'])
def test_tampered_projection_cannot_be_approved(client,db,view_case,tamper):
    h,module,path,view,_=view_case;draft,baseline=chain(client,h,module,path,view)
    row=db.get(SuiteRun,draft['id']);value={**row.snapshots['private_views']};value['2']={**value['2'],'expected_revision':baseline+50}
    row.snapshots={**row.snapshots,'private_views':value if tamper=='change' else {}};db.commit()
    response=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==409
    assert client.get(path,headers=h).json()['revision']==baseline


def test_external_collection_change_between_steps_blocks_later_write(client,db,monkeypatch,view_case):
    h,module,path,view,_=view_case;draft,baseline=chain(client,h,module,path,view);approve(client,h,draft)
    original=suite.finish_step;done=False
    def external(db,run,index,tool,response):
        nonlocal done
        result=original(db,run,index,tool,response)
        if index==1 and not done:
            done=True
            # Use the same canonical service in the existing transaction so the
            # next dispatch observes an independent collection revision.
            from app.apps.crm import task_views
            from app.apps.hrms import ticket_views
            native=task_views if module=='CRM' else ticket_views
            user=db.get(User,run.user_id)
            native.create_record(db,user,native.Create(name='External independent view'),commit=False)
        return result
    monkeypatch.setattr(suite,'finish_step',external);tick(client,db)
    stopped=get(client,h,draft);assert stopped['status']!='succeeded' and len(stopped['receipts'])==1,stopped.get('error_code')
    target=next(v for v in client.get(path,headers=h).json()['items'] if v['id']==view['id'])
    assert target['name']=='First revision' and target['filters']['priority']=='Low'


def test_duplicate_projected_names_and_removed_targets_fail_before_approval(client,db,view_case):
    h,module,path,view,_=view_case;revision=client.get(path,headers=h).json()['revision'];prefix=module.lower()
    scenarios=[
        [{'tool':prefix+'.create_saved_view','payload':{'name':'Duplicate','filters':{}}}]*2,
        [{'tool':prefix+'.remove_saved_view','payload':{'view_id':view['id'],'revision':revision}},
         {'tool':prefix+'.update_saved_view','payload':{'view_id':view['id'],'revision':revision,'name':'Gone','filters':view['filters']}}]
    ]
    for steps in scenarios:
        draft=prepare(client,h,steps);assert draft['status']=='failed' and not draft['approval_id'] and not draft['receipts']
    assert client.get(path,headers=h).json()['revision']==revision


def test_local_compound_followups_and_inline_edit_preserve_projected_state(client,db,view_case):
    from tests.test_suite_workspace import say
    h,module,path,view,ident=view_case
    draft=say(client,h,ident,'Update saved view called Focus: priority=Low then rename that view to Final focus',module=module)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert len(draft['plan']['steps'])==2 and draft['plan']['steps'][1]['payload']['filters']['priority']=='Low'
    revised=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':2,'field':'name','value':'Inline final focus'}]})
    assert revised.status_code==200,revised.text
    corrected=say(client,h,ident,'step=1; priority=Medium',module=module)
    assert corrected['status']=='awaiting_approval',corrected.get('error_code')
    assert corrected['plan']['steps'][1]['payload']['name']=='Inline final focus'
    assert all(step['payload']['filters']['priority']=='Medium' for step in corrected['plan']['steps'])
    approve(client,h,corrected);tick(client,db);done=get(client,h,corrected)
    assert done['status']=='succeeded',done.get('error_code')
    saved=client.get(path,headers=h).json()['items'][0]
    assert saved['name']=='Inline final focus' and saved['filters']['priority']=='Medium'


def test_compound_clarification_retains_the_whole_plan(client,db,view_case):
    from tests.test_suite_workspace import say
    h,module,path,view,ident=view_case
    draft=say(client,h,ident,'Update saved view called Focus: priority=Low then rename that view to Final focus',module=module)
    question=say(client,h,ident,'priority=Medium',module=module);assert question['status']=='needs_clarification'
    bool_field='mine' if module=='CRM' else 'assigned_to_me'
    invalid=say(client,h,ident,f'step=1; {bool_field}=maybe',module=module);assert invalid['status']=='needs_clarification'
    corrected=say(client,h,ident,'step=2; name=Corrected final',module=module)
    assert corrected['status']=='awaiting_approval' and len(corrected['plan']['steps'])==2
    assert all(step['payload']['filters']['priority']=='Low' for step in corrected['plan']['steps'])
    assert corrected['plan']['steps'][1]['payload']['name']=='Corrected final'
    cancelled=say(client,h,ident,'Cancel',module=module)
    assert cancelled['status']=='answered' and client.get(path,headers=h).json()['items'][0]['name']=='Focus'


def test_compound_boundaries_inside_quoted_view_names_are_literal(client,db,view_case):
    from tests.test_suite_workspace import say
    h,module,path,view,ident=view_case;current=client.get(path,headers=h).json()
    name='Focus then rename view literal'
    assert client.put(path+'/'+view['id'],headers=h,json={'name':name,'filters':view['filters'],'revision':current['revision']}).status_code==200
    draft=say(client,h,ident,f'Update saved view called "{name}": priority=Low then rename that view to Final focus',module=module)
    assert draft['status']=='awaiting_approval' and len(draft['plan']['steps'])==2,draft.get('error_code')
    assert all(step['payload']['view_id']==view['id'] for step in draft['plan']['steps'])


def test_explicit_module_switch_controls_following_compound_reference(client,db):
    from tests.test_suite_workspace import chat,say
    h,user,_,_=setup_suite(client,db)
    crm=client.post('/api/v1/crm/task-views',headers=h,json={'name':'CRM focus','filters':{'priority':'High'}}).json()['items'][0]
    hrms=client.post('/api/v1/helpdesk/ticket-views',headers=h,json={'name':'HR focus','filters':{'priority':'High'}}).json()['items'][0]
    ident=chat(client,h)
    draft=say(client,h,ident,'CRM: Update saved view called CRM focus: priority=Low then HRMS: Update saved view called HR focus: priority=Medium then remove that view',module='CRM')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert [step['tool'] for step in draft['plan']['steps']]==['crm.update_saved_view','hrms.update_saved_view','hrms.remove_saved_view']
    assert draft['plan']['steps'][2]['payload']['view_id']==hrms['id']
    approve(client,h,draft);tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded',done.get('error_code')
    assert client.get('/api/v1/helpdesk/ticket-views',headers=h).json()['items']==[]
    assert client.get('/api/v1/crm/task-views',headers=h).json()['items'][0]['id']==crm['id']


def test_remove_then_recreate_name_uses_projected_uniqueness_and_new_receipt(client,db,view_case):
    h,module,path,view,_=view_case;baseline=client.get(path,headers=h).json()['revision'];prefix=module.lower()
    draft=prepare(client,h,[{'tool':prefix+'.remove_saved_view','payload':{'view_id':view['id'],'revision':baseline}},
        {'tool':prefix+'.create_saved_view','payload':{'name':view['name'],'filters':{'priority':'Low'}}}])
    assert draft['status']=='awaiting_approval'
    assert client.get(path,headers=h).json()['items'][0]['id']==view['id']
    approve(client,h,draft);tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded',done.get('error_code')
    current=client.get(path,headers=h).json()
    assert current['revision']==baseline+2 and len(current['items'])==1
    assert current['items'][0]['id']!=view['id'] and current['items'][0]['filters']['priority']=='Low'
    assert done['receipts'][1]['record_id']==current['items'][0]['id']


def test_cloud_proposal_chain_reuses_authorized_view_read_and_native_executor(client,db,monkeypatch,view_case):
    import json
    from tests.test_ai_operator import mock_provider
    h,module,path,view,_=view_case;baseline=client.get(path,headers=h).json()['revision'];prefix=module.lower()
    steps=[{'tool':prefix+'.update_saved_view','payload':{'view_id':view['id'],'revision':baseline,'name':'Provider first','filters':{**view['filters'],'priority':'Low'}}},
        {'tool':prefix+'.update_saved_view','payload':{'view_id':view['id'],'revision':baseline,'name':'Provider final','filters':{**view['filters'],'priority':'Low'}}}]
    calls=mock_provider(monkeypatch,{'summary':'Review two dependent private view changes','steps':steps})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':module,'text':'Prepare a two-stage private view revision with the supplied current context','context':[{'tool':prefix+'.saved_views'}]})
    assert response.status_code==200,response.text
    draft=response.json();assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert calls and b'private_view_planning_policy' in calls[0].content
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    source=next(row['records'] for row in outbound['authorized_context'] if row['tool']==prefix+'.saved_views')
    assert source['revision']==baseline and source['items'][0]['filters']==view['filters']
    assert client.get(path,headers=h).json()['revision']==baseline
    approve(client,h,draft);tick(client,db);done=get(client,h,draft)
    assert done['status']=='succeeded' and len(done['receipts'])==2,done.get('error_code')
    current=client.get(path,headers=h).json();assert current['items'][0]['name']=='Provider final' and current['revision']==baseline+2


def test_creation_rechecks_collection_under_native_lock(client,db,monkeypatch,view_case):
    h,module,path,view,_=view_case;prefix=module.lower()
    draft=prepare(client,h,[{'tool':prefix+'.create_saved_view','payload':{'name':'Reviewed new view','filters':{}}}]);approve(client,h,draft)
    from app.apps.crm import task_views
    from app.apps.hrms import ticket_views
    native=task_views if module=='CRM' else ticket_views
    original=native.create_record;inserted=False
    def concurrent(db,user,data,**kwargs):
        nonlocal inserted
        if not inserted and kwargs.get('expected_revision') is not None:
            inserted=True
            original(db,user,native.Create(name='Independent concurrent view'),commit=True)
        return original(db,user,data,**kwargs)
    monkeypatch.setattr(native,'create_record',concurrent);tick(client,db)
    stopped=get(client,h,draft);assert stopped['status']!='succeeded' and not stopped['receipts']
    assert all(view['name']!='Reviewed new view' for view in client.get(path,headers=h).json()['items'])
    assert any(view['name']=='Independent concurrent view' for view in client.get(path,headers=h).json()['items'])


@pytest.mark.parametrize('module',['crm','hrms'])
def test_view_source_preserves_typed_filters_without_widening_generic_sources(module):
    from app.ai_operator.suite_tools import minimize_source
    value={'revision':3,'items':[{'id':'a'*32,'name':'Synthetic source','filters':{'priority':'High'},'salary':'private extra value'}]}
    projected=minimize_source(module+'.saved_views',value)
    assert projected['revision']==3 and projected['items'][0]['filters']['priority']=='High'
    assert 'salary' not in str(projected)
    generic=minimize_source('hrms.employees',value)
    assert 'revision' not in generic and 'filters' not in str(generic) and 'salary' not in str(generic)
    with pytest.raises(ValueError):minimize_source(module+'.saved_views',{'revision':3,'items':[{'id':'a'*32,'name':'Synthetic source','filters':{'salary':'private extra value'}}]})
