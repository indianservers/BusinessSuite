from uuid import uuid4
from io import BytesIO
import pytest
from tests.test_suite_operator import setup_suite,ROOT,approve,tick
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.rich_text_test_utils import organization_context
from ai_test_utils import auth_headers
A=ROOT+'/artifacts'


def command(client,h,module,text,**extra):
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':module,'text':text,**extra})
    assert r.status_code==200,r.text
    return r.json()


def execute(client,db,h,run):
    assert run['status']=='awaiting_approval',run
    approve(client,h,run);tick(client,db)
    result=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert result['status']=='succeeded',result
    return result


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_reviewed_artifact_create_edit_versions_and_private_access(client,db,module):
    h,u,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Artifact conversation'}).json()['id']
    run=command(client,h,module,'Create document called Launch brief: Original agreed goals.',conversation_id=chat)
    assert client.get(A,headers=h,params={'module':module}).json()['items']==[]
    result=execute(client,db,h,run);ident=result['receipts'][0]['artifact_id']
    original=client.get(A+f'/{ident}',headers=h)
    assert original.status_code==200,original.text
    assert original.json()['content']=='Original agreed goals.' and original.json()['revision']==1
    edit=command(client,h,module,'Append: Owner review is required.',conversation_id=chat)
    assert edit['plan']['steps'][0]['payload']['expected_revision']==1
    assert client.get(A+f'/{ident}',headers=h).json()['revision']==1
    execute(client,db,h,edit)
    latest=client.get(A+f'/{ident}',headers=h).json()
    assert latest['revision']==2 and 'Original agreed goals.' in latest['content'] and 'Owner review is required.' in latest['content']
    assert client.get(A+f'/{ident}',headers=h,params={'revision':1}).json()['content']=='Original agreed goals.'
    assert len(client.get(A+f'/{ident}/versions',headers=h).json()['items'])==2
    h2,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view','pms_manage_tasks','hrms_view'])
    assert client.get(A+f'/{ident}',headers=h2).status_code==404
    # Text exports contain the selected version, not executable browser content.
    export=client.get(A+f'/{ident}/download',headers=h,params={'format':'docx','revision':1})
    assert export.status_code==200,export.text
    from docx import Document
    assert 'Original agreed goals.' in '\n'.join(p.text for p in Document(BytesIO(export.content)).paragraphs)


def test_artifact_stale_edits_and_unapproved_mutations_rejected(client,db):
    h,_,_,_=setup_suite(client,db)
    made=execute(client,db,h,command(client,h,'CRM','Create document called Test: Existing content'))
    ident=made['receipts'][0]['artifact_id']
    a=command(client,h,'CRM',f'Edit artifact #{ident}: append: First change')
    b=command(client,h,'CRM',f'Edit artifact #{ident}: append: Second change')
    execute(client,db,h,a)
    stale=client.post(ROOT+f'/runs/{b["id"]}/approve',headers=h,json={'plan_hash':b['plan_hash']})
    assert stale.status_code==409,stale.text
    assert client.get(A+f'/{ident}',headers=h).json()['revision']==2
    assert 'Second change' not in client.get(A+f'/{ident}',headers=h).json()['content']
    blocked=client.post(A+'/create-approved',headers=h,json={'title':'Bypass','content':'Unsafe bypass','suite_run_id':a['id'],'suite_step':1})
    assert blocked.status_code==403
    cross=client.get(A+'/current',headers=h,params={'artifact_id':ident,'module':'HRMS'})
    assert cross.status_code==403


def test_table_edits_and_exports_keep_formula_like_cells_inert(client,db):
    h,_,_,_=setup_suite(client,db)
    first=execute(client,db,h,command(client,h,'CRM','Create table called Lead tracker with columns Name, Status'))
    ident=first['receipts'][0]['artifact_id']
    edited=command(client,h,'CRM',f'Edit artifact #{ident}: add row: =1+1, Pending')
    execute(client,db,h,edited)
    current=client.get(A+f'/{ident}',headers=h).json()
    assert current['rows']==[['=1+1','Pending']]
    export=client.get(A+f'/{ident}/download',headers=h,params={'format':'xlsx'})
    assert export.status_code==200,export.text
    from openpyxl import load_workbook
    cell=load_workbook(BytesIO(export.content)).active['A2']
    assert cell.value=='=1+1' and cell.data_type=='s'
    csv=client.get(A+f'/{ident}/download',headers=h,params={'format':'csv'})
    assert "'=1+1" in csv.content.decode('utf-8-sig')


def test_cloud_uses_current_artifact_context_and_cannot_save_without_review(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    made=execute(client,db,h,command(client,h,'CRM','Create document called Customer proposal: Scope stays unchanged.'))
    ident=made['receipts'][0]['artifact_id']
    calls=mock_provider(monkeypatch,{'summary':'Review revised proposal','steps':[{'tool':'crm.edit_artifact','payload':{'artifact_id':ident,'expected_revision':1,'title':'Customer proposal','kind':'document','content':'Scope stays unchanged. New timeline.','columns':[],'rows':[]}}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Edit artifact #{ident}: add a timeline'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='awaiting_approval',response.text
    import json
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    assert outbound['artifact_context']['content']=='Scope stays unchanged.'
    assert outbound['artifact_context']['current_revision']==1
    assert client.get(A+f'/{ident}',headers=h).json()['revision']==1


def test_missing_details_and_unapproved_followups_keep_one_artifact(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Followups'}).json()['id']
    missing=command(client,h,'CRM','Create document',conversation_id=chat)
    assert missing['status']=='needs_clarification',missing
    drafted=command(client,h,'CRM','Release brief: Keep the original content.',conversation_id=chat)
    assert drafted['status']=='awaiting_approval',drafted
    changed=command(client,h,'CRM','Rename to Reviewed release',conversation_id=chat)
    assert changed['plan']['steps'][0]['payload']['title']=='Reviewed release',changed
    assert changed['plan']['steps'][0]['payload']['content']=='Keep the original content.'
    assert client.get(A,headers=h,params={'module':'CRM'}).json()['items']==[]
    made=execute(client,db,h,changed)
    ident=made['receipts'][0]['artifact_id']
    read=command(client,h,'CRM',f'Show artifact #{ident}',conversation_id=chat)
    assert read['status']=='answered',read
    assert read['result']['artifact_context']['id']==ident
    assert len(client.get(A+f'/{ident}/versions',headers=h).json()['items'])==1


def test_uploads_are_literal_artifact_context_and_invalid_table_edits_fail(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Upload draft'}).json()['id']
    upload=client.post(ROOT+f'/conversations/{chat}/attachments',headers=h,files={'file':('source.txt',b'User supplied delivery requirements.','text/plain')})
    assert upload.status_code==201,upload.text
    run=command(client,h,'HRMS','Create document called Uploaded onboarding brief',conversation_id=chat,attachment_ids=[upload.json()['id']])
    content=run['plan']['steps'][0]['payload']['content']
    assert 'User supplied delivery requirements.' in content and 'Unverified uploaded source' in content
    assert client.get(A,headers=h,params={'module':'HRMS'}).json()['items']==[]
    execute(client,db,h,run)
    # Bounds and shape are checked before the plan can be approved.
    from app.ai_operator.artifacts import Body
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Body(title='Unsafe shape',kind='table',columns=['A'],rows=[['1','2']])
    with pytest.raises(ValidationError):Body(title='Invalid document',content='NUL\x00')


def test_repeated_reviewed_dispatch_is_idempotent(client,db):
    import asyncio
    from app.ai_operator.suite import api_call
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_agents.security import ORIGIN
    h,_,_,_=setup_suite(client,db)
    run=command(client,h,'CRM','Create document called Only once: Reviewed content')
    approve(client,h,run)
    stored=db.get(SuiteRun,run['id']);stored.status='executing';stored.active_step=1;db.commit()
    payload={**run['plan']['steps'][0]['payload'],'suite_run_id':run['id'],'suite_step':1}
    origin=ORIGIN.set({'company_id':1})
    try:
        first=asyncio.run(api_call(client.app,h['Authorization'],'POST','/ai-operator/suite/artifacts/create-approved',payload))
        second=asyncio.run(api_call(client.app,h['Authorization'],'POST','/ai-operator/suite/artifacts/create-approved',payload))
    finally:ORIGIN.reset(origin)
    assert first['artifact_id']==second['artifact_id'] and second['artifact_revision']==1
    assert len(client.get(A,headers=h,params={'module':'CRM'}).json()['items'])==1


def test_local_artifact_rewrite_reuses_server_writing_skill(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Local writing'}).json()['id']
    original='First agreed goal. Second agreed goal. Third agreed goal. Fourth agreed goal. Fifth agreed goal.'
    made=execute(client,db,h,command(client,h,'CRM','Create document called Goals: '+original,conversation_id=chat))
    ident=made['receipts'][0]['artifact_id']
    rewritten=command(client,h,'CRM','Make it shorter',conversation_id=chat)
    assert rewritten['status']=='awaiting_approval',rewritten
    assert len(rewritten['plan']['steps'][0]['payload']['content'])<len(original)
    assert client.get(A+f'/{ident}',headers=h).json()['content']==original
    execute(client,db,h,rewritten)
    assert client.get(A+f'/{ident}',headers=h,params={'revision':1}).json()['content']==original


def test_followup_business_action_is_not_appended_to_an_artifact(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Separate intents'}).json()['id']
    made=execute(client,db,h,command(client,h,'CRM','Create document called Plan: Keep the document.',conversation_id=chat))
    ident=made['receipts'][0]['artifact_id']
    task=command(client,h,'CRM','Add a CRM task called Customer followup',conversation_id=chat)
    assert task['status']=='awaiting_approval',task
    assert any(s['tool']=='crm.create_task' for s in task['plan']['steps']),task
    assert client.get(A+f'/{ident}',headers=h).json()['revision']==1


def test_cross_module_artifact_edits_use_the_target_modules_private_provider_preference(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    made=execute(client,db,h,command(client,h,'HRMS','Create document called HR note: Private HR preference test'))
    ident=made['receipts'][0]['artifact_id']
    preference=client.put(ROOT+'/intelligence',headers=h,json={'module':'HRMS','provider':'local'})
    assert preference.status_code==200,preference.text
    calls=mock_provider(monkeypatch,{'summary':'Must not send this HR artifact to the cloud','steps':[]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'preferred','module':'CRM','text':f'Edit artifact #{ident}: append: Review required.'})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='awaiting_approval',run
    assert run['result']['request']['module']=='HRMS' and run['result']['request']['provider']=='local'
    assert run['plan']['steps'][0]['tool']=='hrms.edit_artifact'
    assert not calls


def test_artifact_ids_inside_literal_content_do_not_trigger_record_reads(client,db):
    h,_,_,_=setup_suite(client,db)
    literal='The example identifier artifact #999999 is not a real record.'
    run=command(client,h,'CRM','Create document called Reference examples: '+literal)
    assert run['status']=='awaiting_approval',run
    assert run['plan']['steps'][0]['payload']['content']==literal
    assert not run['result'].get('artifact_context')


def test_document_named_tasks_uses_upload_as_text_not_task_import(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Literal uploaded document'}).json()['id']
    upload=client.post(ROOT+f'/conversations/{chat}/attachments',headers=h,files={'file':('notes.txt',b'Keep the uploaded requirements as document text.','text/plain')})
    assert upload.status_code==201,upload.text
    run=command(client,h,'CRM','Create document called Tasks from uploaded file',conversation_id=chat,attachment_ids=[upload.json()['id']])
    assert run['status']=='awaiting_approval',run
    assert run['plan']['steps'][0]['tool']=='crm.create_artifact'
    assert 'Keep the uploaded requirements as document text.' in run['plan']['steps'][0]['payload']['content']


@pytest.mark.parametrize('invalid',['\ufffe','\uffff','\x00','\x0b'])
def test_artifacts_reject_characters_that_break_document_exports(invalid):
    from app.ai_operator.artifacts import Body
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Body(title='Document',content='Invalid '+invalid)


def test_compact_append_command_keeps_existing_content(client,db):
    h,_,_,_=setup_suite(client,db)
    made=execute(client,db,h,command(client,h,'CRM','Create document called Compact editing: Preserve this.'))
    ident=made['receipts'][0]['artifact_id']
    edit=command(client,h,'CRM',f'Edit artifact #{ident}: append:New text.')
    assert edit['status']=='awaiting_approval',edit
    assert edit['plan']['steps'][0]['payload']['content']=='Preserve this.\n\nNew text.'


def test_completed_business_action_stops_implicit_selection_of_an_older_artifact(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Current conversation focus'}).json()['id']
    saved=execute(client,db,h,command(client,h,'CRM','Create document called Original: Keep unchanged.',conversation_id=chat))
    ident=saved['receipts'][0]['artifact_id']
    execute(client,db,h,command(client,h,'CRM','Create CRM task called Current task',conversation_id=chat))
    next_run=command(client,h,'CRM','Append: Unclear target.',conversation_id=chat)
    assert not next_run['result'].get('artifact_context')
    assert not any(s['tool'].endswith('.edit_artifact') for s in (next_run.get('plan') or {}).get('steps',[]))
    assert client.get(A+f'/{ident}',headers=h).json()['revision']==1


def test_cloud_artifact_schema_repair_is_bounded_and_never_executes(client,db,monkeypatch):
    import json,httpx
    from app.ai_operator import providers
    h,_,_,_=setup_suite(client,db)
    made=execute(client,db,h,command(client,h,'CRM','Create document called Repair test: Preserve the original.'))
    ident=made['receipts'][0]['artifact_id'];requests=[];real=httpx.Client
    def handler(request):
        requests.append(json.loads(request.content))
        good={'tool':'crm.edit_artifact','payload':{'artifact_id':ident,'expected_revision':1,'title':'Repair test','kind':'document','content':'Preserve the original. Added note.','columns':[],'rows':[]}}
        step=good if len(requests)>1 else {'tool':'crm.edit_artifact','record_id':ident,'payload':{k:v for k,v in good['payload'].items() if k!='artifact_id'}}
        plan={'summary':'Review artifact edit','steps':[step]}
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(plan)}]}}]})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    result=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Edit artifact #{ident}: append: Added note.'})
    assert result.status_code==200,result.text
    run=result.json();assert run['status']=='awaiting_approval',run
    assert len(requests)==2
    assert run['result']['artifact_repair']['attempts']==1
    feedback=json.loads(requests[1]['contents'][0]['parts'][0]['text'])['artifact_validation_feedback']
    assert feedback['issues'][0]['record_id_present']
    assert client.get(A+f'/{ident}',headers=h).json()['revision']==1


@pytest.mark.parametrize('substitution',['business','format'])
def test_cloud_cannot_repair_an_artifact_draft_into_a_business_mutation(client,db,monkeypatch,substitution):
    import json,httpx
    from app.ai_operator import providers
    h,_,_,_=setup_suite(client,db);requests=[];real=httpx.Client
    def handler(request):
        requests.append(request)
        replacement={'tool':'crm.create_task','payload':{'title':'Unrequested business mutation'}} if substitution=='business' else {'tool':'crm.create_artifact','payload':{'title':'Changed format','kind':'document','content':'Unrequested format change'}}
        step={'tool':'crm.create_artifact','payload':{'title':'Broken table','kind':'table','columns':[],'rows':[]}} if len(requests)==1 else replacement
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'summary':'Proposal','steps':[step]})}]}}]})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    result=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':'Create table called Pipeline tracker'})
    assert result.status_code==200,result.text
    assert result.json()['status']=='failed' and not result.json()['approval_id']
    assert len(requests)==2



@pytest.mark.parametrize('label,kind',[
 ('Excel workbook','table'),('Excel spreadsheet','table'),('Excel sheet','table'),('Excel','table'),('worksheet','table'),
 ('Word document','document'),('Word','document'),('docx','document'),('PDF document','document'),('PDF report','document'),
 ('PowerPoint presentation','presentation'),
])
def test_office_format_names_use_one_artifact_grammar(label,kind):
    from types import SimpleNamespace
    from app.ai_operator.artifacts import creation_request,local_plan
    text=f'Create {label} called Launch'
    if kind=='table':text+=' with columns Task, Owner: Review, Asha'
    assert creation_request(text)
    result=local_plan(SimpleNamespace(text=text,module='CRM'),None,None,[])
    assert result.steps[0].payload['kind']==kind
    assert result.steps[0].payload['title']=='Launch'
    if kind=='table':assert result.steps[0].payload['rows']==[['Review','Asha']]


def test_inline_csv_rows_remain_literal_and_malformed_rows_request_correction():
    from types import SimpleNamespace
    from app.ai_operator.artifacts import local_plan
    data=SimpleNamespace(text='Create Excel called Tracker with columns Task, Owner: "Review, then approve", Asha\n=1+1, Ravi',module='PMS')
    result=local_plan(data,None,None,[])
    assert result.steps[0].payload['rows']==[['Review, then approve','Asha'],['=1+1','Ravi']]
    data.text='Create Excel called Tracker with columns Task, Owner: Review'
    bad=local_plan(data,None,None,[])
    assert bad.question and not bad.steps
    parent=SimpleNamespace(status='needs_clarification',command=data.text,plan=bad.model_dump())
    data.text='Review, Asha'
    fixed=local_plan(data,parent,None,[])
    assert fixed.steps[0].payload['title']=='Tracker'
    assert fixed.steps[0].payload['rows']==[['Review','Asha']]


def test_excel_conversation_corrects_rows_then_saves_and_exports_on_server(client,db):
    from openpyxl import load_workbook
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Excel draft'}).json()['id']
    draft=command(client,h,'CRM','Create Excel workbook called Pipeline with columns Lead, Owner: Synthetic lead',conversation_id=chat)
    assert draft['status']=='needs_clarification' and not draft['plan']['steps']
    draft=command(client,h,'CRM','Synthetic lead, Asha\n=1+1, Ravi',conversation_id=chat)
    assert draft['status']=='awaiting_approval'
    assert draft['plan']['steps'][0]['payload']['rows']==[['Synthetic lead','Asha'],['=1+1','Ravi']]
    assert client.get(A,headers=h,params={'module':'CRM'}).json()['items']==[]
    result=execute(client,db,h,draft);ident=result['receipts'][0]['artifact_id']
    response=client.get(A+f'/{ident}/download',headers=h,params={'format':'xlsx'})
    assert response.status_code==200
    sheet=load_workbook(BytesIO(response.content)).active
    assert list(sheet.values)==[('Lead','Owner'),('Synthetic lead','Asha'),('=1+1','Ravi')]
    assert sheet['A3'].data_type=='s'



def test_quoted_csv_column_names_are_not_stripped_as_title_quotes():
    from types import SimpleNamespace
    from app.ai_operator.artifacts import local_plan
    data=SimpleNamespace(text='Create Excel called Tracker with columns "Task, name", "Owner": Review, Asha',module='CRM')
    result=local_plan(data,None,None,[])
    assert result.steps[0].payload['columns']==['Task, name','Owner']
    assert result.steps[0].payload['rows']==[['Review','Asha']]



def test_native_business_command_is_not_consumed_as_missing_artifact_rows():
    from types import SimpleNamespace
    from app.ai_operator.artifacts import local_plan
    parent=SimpleNamespace(status='needs_clarification',command='Create Excel called Tracker with columns Task, Owner: Review',plan={'summary':'I need valid table rows.'})
    data=SimpleNamespace(text='Update lead #12 job title: Director',module='CRM')
    assert local_plan(data,parent,None,[]) is None
