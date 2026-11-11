import io
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_suite_workspace import chat,upload,say
from app.apps.crm.models import CRMTask
from app.ai_operator.suite_uploads import parse,spreadsheet_plan

ROOT='/api/v1/ai-operator/suite'

def test_inline_edit_then_conversation_keeps_edited_fields_and_executes(client,db):
    from app.ai_operator.pms_agent import resolve_date
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Create tasks for Review warranty, Confirm coverage',module='CRM')
    changes=[{'step':2,'field':'title','value':'Review revised coverage'},{'step':2,'field':'description','value':'Keep the agreed commercial terms'},
        {'step':2,'field':'due_date','value':resolve_date('tomorrow')},{'step':2,'field':'owner_user_id','value':user.id}]
    r=client.post(f'{ROOT}/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':changes})
    assert r.status_code==200,r.text
    revised=r.json()
    continued=say(client,h,ident,'push "Review revised coverage" back by one day',module='CRM',parent_run_id=revised['id'])
    assert continued['status']=='awaiting_approval',continued
    payload=continued['plan']['steps'][1]['payload']
    assert payload['title']=='Review revised coverage' and payload['due_date']==resolve_date('in 2 days')
    assert payload['description']=='Keep the agreed commercial terms' and payload['owner_user_id']==user.id
    assert client.post(f'{ROOT}/runs/{revised["id"]}/approve',headers=h,json={'plan_hash':revised['plan_hash']}).status_code==409
    approve(client,h,continued);tick(client,db)
    saved=db.query(CRMTask).filter_by(title='Review revised coverage').one()
    assert saved.description==payload['description'] and saved.owner_user_id==user.id

def test_history_question_preserves_pending_actions_and_clarification(client,db):
    h,_,project,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Create tasks for Review terms, Confirm renewal',module='CRM')
    history=say(client,h,ident,'what changed',module='CRM',parent_run_id=draft['id'])
    assert history['status']=='awaiting_approval' and len(history['plan']['steps'])==2,history
    final=say(client,h,ident,'make them all low priority',module='CRM',parent_run_id=history['id'])
    assert all(s['payload']['priority']=='Low' for s in final['plan']['steps'])
    approve(client,h,final);tick(client,db)
    assert db.query(CRMTask).count()==2
    other=chat(client,h)
    pending=say(client,h,other,'Create project tasks for Design, Verify',module='PMS')
    assert pending['status']=='needs_clarification'
    history=say(client,h,other,'show receipts',module='PMS',parent_run_id=pending['id'])
    assert history['status']=='needs_clarification' and history['plan']['question']==pending['plan']['question']
    resolved=say(client,h,other,f'project #{project}',module='PMS',parent_run_id=history['id'])
    assert resolved['status']=='awaiting_approval' and len(resolved['plan']['steps'])==2

def test_uploaded_draft_followup_retains_fields_and_source_authorization(client,db):
    h,_,_,_=setup_suite(client,db);ident=chat(client,h)
    file=upload(client,h,ident,'actions.csv',b'module,title,description\nCRM,Confirm renewal,Retain the original scope\n')
    draft=say(client,h,ident,'create tasks from uploaded spreadsheet',module='CRM',attachment_ids=[file['id']])
    final=say(client,h,ident,'make it high priority',module='CRM',parent_run_id=draft['id'])
    assert final['status']=='awaiting_approval',final
    assert final['plan']['steps'][0]['payload']['description']=='Retain the original scope'
    assert final['result']['request']['attachment_ids']==[file['id']]
    assert client.delete(f'{ROOT}/conversations/{ident}/attachments/{file["id"]}',headers=h).status_code==200
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','conversation_id':ident,'parent_run_id':final['id'],'module':'CRM','text':'make it low priority'})
    assert r.status_code==404,r.text
    assert db.query(CRMTask).count()==0

@pytest.mark.parametrize('content',[b'module,title\nCRM,Call client,unmapped value\n',
    (','.join(['module','title']+[f'column{i}' for i in range(30)])+'\nCRM,Call client\n').encode()])
def test_csv_action_import_never_ignores_extra_columns(content):
    value=parse(content,'actions.csv')
    row=SimpleNamespace(result=value,arguments={'notes':value['notes']})
    with pytest.raises(HTTPException):spreadsheet_plan(row,str(uuid4()))

def test_xlsx_parser_reports_content_outside_preview_and_preserves_time():
    from datetime import datetime
    from openpyxl import Workbook
    book=Workbook();sheet=book.active
    sheet.append(['module','title','due_date']);sheet.append(['CRM','Timed follow-up',datetime(2026,11,15,15,30)])
    sheet.cell(205,1,'CRM');sheet.cell(205,2,'Hidden action');sheet.cell(1,33,'Unseen column')
    out=io.BytesIO();book.save(out);book.close()
    value=parse(out.getvalue(),'actions.xlsx')
    assert value['notes'],'Omitted rows/columns must be reported'
    assert value['rows'][1][2]=='2026-11-15T15:30:00'
    with pytest.raises(HTTPException):spreadsheet_plan(SimpleNamespace(result=value,arguments={'notes':value['notes']}),str(uuid4()))

def test_pending_project_can_be_edited_before_answering_the_question(client,db):
    h,_,project,_=setup_suite(client,db);ident=chat(client,h)
    pending=say(client,h,ident,'Create project tasks for Draft scope, Review scope',module='PMS')
    assert pending['status']=='needs_clarification'
    priority=say(client,h,ident,'make them all high priority',module='PMS',parent_run_id=pending['id'])
    assert priority['status']=='needs_clarification'
    named=say(client,h,ident,'rename item 2 to Final scope',module='PMS',parent_run_id=priority['id'])
    assert named['status']=='needs_clarification'
    resolved=say(client,h,ident,f'project #{project}',module='PMS',parent_run_id=named['id'])
    assert resolved['status']=='awaiting_approval',resolved
    assert [s['payload']['title'] for s in resolved['plan']['steps']]==['Draft scope','Final scope']
    assert all(s['payload']['priority']=='High' for s in resolved['plan']['steps'])

def test_recovered_new_project_keeps_parent_references_and_complete_payloads():
    from app.ai_operator.suite import Plan
    from app.ai_operator.suite_workspace import draft_workflow
    from app.ai_operator.conversational_actions import amend
    from app.ai_operator.workflows import local_plan
    plan=Plan(summary='Nested draft',steps=[
        {'tool':'pms.create_project','payload':{'name':'Rollout','project_key':'CUSTOM-KEY','description':'Keep project notes'}},
        {'tool':'pms.create_task','record_id':{'$step':1,'field':'id'},'payload':{'title':'Parent','task_key':'PARENT','description':'Keep task notes','assignee_user_id':5}},
        {'tool':'pms.create_task','record_id':{'$step':1,'field':'id'},'payload':{'title':'Child','task_key':'CHILD','parent_task_id':{'$step':2,'field':'id'}}}])
    state=draft_workflow(plan);assert state
    unchanged,q=amend(state,'remove "Parent"','Asia/Kolkata','PMS')
    assert q and unchanged==state
    parent=SimpleNamespace(status='awaiting_approval',result={'workflow':state})
    data=SimpleNamespace(text='rename "Child" to Verify rollout',module='PMS',project_id=None,request_key=str(uuid4()),timezone='Asia/Kolkata')
    revised,_=local_plan(data,parent,None)
    assert revised['steps'][0]['payload']['project_key']=='CUSTOM-KEY'
    assert revised['steps'][1]['payload']['description']=='Keep task notes'
    assert revised['steps'][1]['payload']['assignee_user_id']==5
    assert revised['steps'][2]['payload']['parent_task_id']=={'$step':2,'field':'id'}
    assert revised['steps'][2]['payload']['title']=='Verify rollout'

def test_recovered_multiple_project_ids_are_not_collapsed_into_one_project():
    from app.ai_operator.suite import Plan
    from app.ai_operator.suite_workspace import draft_workflow
    from app.ai_operator.workflows import local_plan
    plan=Plan(summary='Separate projects',steps=[{'tool':'pms.create_task','record_id':p,'payload':{'title':t,'task_key':t}} for p,t in [(12,'Design'),(15,'Verify')]])
    state=draft_workflow(plan);assert state and state['project_id'] is None
    data=SimpleNamespace(text='make them all low priority',module='PMS',project_id=None,request_key=str(uuid4()),timezone='Asia/Kolkata')
    revised,_=local_plan(data,SimpleNamespace(status='awaiting_approval',result={'workflow':state}),None)
    assert [s['record_id'] for s in revised['steps']]==[12,15]

def test_ticket_description_and_project_only_drafts_survive_recovery():
    from app.ai_operator.suite import Plan
    from app.ai_operator.suite_workspace import draft_workflow
    from app.ai_operator.workflows import local_plan
    def revise(plan,text):
        state=draft_workflow(plan);assert state
        data=SimpleNamespace(text=text,module='HRMS',project_id=None,request_key=str(uuid4()),timezone='Asia/Kolkata')
        return local_plan(data,SimpleNamespace(status='awaiting_approval',result={'workflow':state}),None)[0]
    ticket=Plan(summary='HR',steps=[{'tool':'hrms.create_ticket','payload':{'subject':'Check allowance','description':'Detailed agreed explanation','category_id':2,'priority':'Medium'}}])
    revised=revise(ticket,'make it high priority')
    assert revised['steps'][0]['payload']['description']=='Detailed agreed explanation'
    assert revised['steps'][0]['payload']['category_id']==2
    project=Plan(summary='Project',steps=[{'tool':'pms.create_project','payload':{'name':'New rollout','project_key':'ROLLOUT'}}])
    revised=revise(project,'rename it to Regional rollout')
    assert revised['steps'][0]['payload']['name']=='Regional rollout'
    assert revised['steps'][0]['payload']['project_key']=='ROLLOUT'

def test_summary_only_history_keeps_workflow_resumable_without_action_steps(client,db):
    h,_,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Create tasks for Review warranty, Confirm coverage',module='CRM')
    summary=say(client,h,ident,'what changed',module='CRM',mode='summary',parent_run_id=draft['id'])
    assert summary['status']=='needs_clarification' and not summary['plan']['steps'],summary
    revised=say(client,h,ident,'make them all high priority',module='CRM',parent_run_id=summary['id'])
    assert revised['status']=='awaiting_approval' and len(revised['plan']['steps'])==2
    assert all(s['payload']['priority']=='High' for s in revised['plan']['steps'])
    assert db.query(CRMTask).count()==0

def test_history_is_server_grounded_with_connected_provider_selected(client,db,monkeypatch):
    from tests.test_ai_operator import mock_provider
    h,_,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Create tasks for Review warranty, Confirm coverage',module='CRM')
    calls=mock_provider(monkeypatch,{'summary':'Untrusted generated history','steps':[]})
    history=say(client,h,ident,'show receipts',module='CRM',provider='gemini',parent_run_id=draft['id'])
    assert history['status']=='awaiting_approval' and len(history['plan']['steps'])==2,history
    assert not calls,'Receipt history should come from server records, without a model call'
    assert 'Untrusted generated history' not in history['plan']['summary']

def test_non_table_documents_cannot_turn_partial_previews_into_actions():
    row=SimpleNamespace(arguments={'format':'.docx','notes':[]},result={'rows':[['module','title'],['CRM','Only the previewed row']]})
    with pytest.raises(HTTPException):spreadsheet_plan(row,str(uuid4()))
