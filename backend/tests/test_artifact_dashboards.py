import io
from uuid import uuid4
import pytest
from pypdf import PdfReader
from docx import Document
from app.ai_operator.artifacts import Body
from app.ai_operator import artifact_dashboards as dashboards
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_bot_artifacts import command,execute,A
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from ai_test_utils import auth_headers


def source(client,db,h,module='CRM'):
    return execute(client,db,h,command(client,h,module,'Create document called Delivery notes: Original source content.'))['receipts'][0]['artifact_id']


def definition(ident,**changes):
    return {'title':'Delivery dashboard','kind':'dashboard','content':'Pinned illustrative report.','columns':[],'rows':[],
        'panels':[{'artifact_id':ident,'revision':1,'display':'summary','label':'Notes','wide':False}],**changes}


def prepare(client,h,module,payload,**extra):
    return command(client,h,module,'Prepare this dashboard',local_plan={'summary':'Review pinned sources','steps':[{'tool':module.lower()+'.create_artifact','payload':payload}]},**extra)


@pytest.mark.parametrize('change',[{'panels':[]},{'panels':[{'artifact_id':1,'revision':1}]*7},
    {'panels':[{'artifact_id':True,'revision':1}]},{'panels':[{'artifact_id':1,'revision':0}]},
    {'columns':['Wrong']},{'chart':{'aggregation':'count'}},{'kind':'document'}])
def test_dashboard_shape_is_bounded_and_does_not_change_legacy_hashes(change):
    with pytest.raises(ValueError):Body.model_validate(definition(1,**change))
    assert 'panels' not in Body(title='Legacy',content='Text').model_dump()


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_reviewed_dashboards_pin_cross_module_sources_and_versioned_exports(client,db,module):
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h,'HRMS' if module!='HRMS' else 'CRM')
    draft=prepare(client,h,module,definition(ident));assert draft['status']=='awaiting_approval'
    before=client.get(A,headers=h,params={'module':module}).json()['items']
    assert all(a['kind']!='dashboard' for a in before)
    made=execute(client,db,h,draft);dashboard=made['receipts'][0]['artifact_id']
    execute(client,db,h,command(client,h,'HRMS' if module!='HRMS' else 'CRM',f'Edit artifact #{ident}: append: New source revision.'))
    pinned=client.get(A+f'/{dashboard}/panels/1',headers=h);assert pinned.status_code==200,pinned.text
    assert pinned.json()['source']['revision']==1 and pinned.json()['source']['current_revision']==2
    assert 'New source revision' not in pinned.json()['source']['content']
    assert pinned.json()['citation']['id']==f'artifact:{ident}:v1'
    for fmt in ('md','docx','pdf'):
        response=client.get(A+f'/{dashboard}/download',headers=h,params={'format':fmt});assert response.status_code==200,response.text[:500]
        text=response.text if fmt=='md' else '\n'.join(p.text for p in Document(io.BytesIO(response.content)).paragraphs) if fmt=='docx' else '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
        assert 'Original source content' in text and 'New source revision' not in text
    revised=command(client,h,module,f'Edit artifact #{dashboard}: refresh panel 1 to v2')
    execute(client,db,h,revised)
    assert client.get(A+f'/{dashboard}/panels/1',headers=h).json()['source']['revision']==2
    assert client.get(A+f'/{dashboard}/panels/1',headers=h,params={'revision':1}).json()['source']['revision']==1
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view','hrms_view','pms_manage_tasks'])
    assert client.get(A+f'/{dashboard}/panels/1',headers=other).status_code==404
    assert client.post(A+'/panel-preview',headers=other,json={'module':module,'panel':definition(ident)['panels'][0]}).status_code==404


def test_local_dashboard_followups_inline_edits_and_templates_preserve_pins(client,db):
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Dashboard follow-ups'}).json()['id']
    ask=command(client,h,'CRM','Create dashboard called Delivery',conversation_id=chat)
    assert ask['status']=='needs_clarification' and 'versions' in ask['plan']['question']
    draft=command(client,h,'CRM',f'artifact #{ident} v1 as summary',conversation_id=chat)
    assert draft['status']=='awaiting_approval',draft
    added=command(client,h,'CRM',f'Add panel: artifact #{ident} v1',conversation_id=chat)
    assert len(added['plan']['steps'][0]['payload']['panels'])==2
    renamed=command(client,h,'CRM','Rename panel 2 to Team notes',conversation_id=chat)
    assert renamed['plan']['steps'][0]['payload']['panels'][1]['label']=='Team notes'
    panels=renamed['plan']['steps'][0]['payload']['panels'];panels[0]['wide']=True
    response=client.post(ROOT+f'/runs/{renamed["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':renamed['plan_hash'],
        'changes':[{'step':1,'field':'panels','value':panels}]});assert response.status_code==200,response.text
    dashboard=execute(client,db,h,response.json())['receipts'][0]['artifact_id']
    assert client.get(A+f'/{dashboard}',headers=h).json()['panels'][0]['wide']
    execute(client,db,h,command(client,h,'CRM','Move panel 2 to 1',conversation_id=chat))
    item=client.get(A+f'/{dashboard}',headers=h).json();assert item['panels'][0]['label']=='Team notes'
    preview=client.post(ROOT+'/artifact-templates/preview',headers=h,json={'request_key':str(uuid4()),'name':'Pinned dashboard template',
        'source_artifact_id':dashboard,'source_revision':2,'body':{k:item[k] for k in ('title','kind','content','columns','rows','panels')}})
    assert preview.status_code==200,preview.text
    review=preview.json();confirmed=client.post(ROOT+f'/artifact-templates/reviews/{review["id"]}/confirm',headers=h,json={'preview_hash':review['preview_hash']})
    assert confirmed.status_code==200,confirmed.text
    template=confirmed.json()['template']
    copied=command(client,h,'CRM',f'Use template #{template["id"]}')
    assert copied['status']=='awaiting_approval' and copied['plan']['steps'][0]['payload']['panels']==item['panels']


def test_source_archive_rechecks_preview_approval_worker_and_exports(client,db):
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h)
    dashboard=execute(client,db,h,prepare(client,h,'CRM',definition(ident)))['receipts'][0]['artifact_id']
    pending=prepare(client,h,'CRM',definition(ident,title='Second dashboard'))
    assert client.delete(A+f'/{ident}',headers=h).status_code==200
    assert client.post(ROOT+f'/runs/{pending["id"]}/approve',headers=h,json={'plan_hash':pending['plan_hash']}).status_code==404
    assert client.get(A+f'/{dashboard}/panels/1',headers=h).status_code==404
    assert client.get(A+f'/{dashboard}/download',headers=h,params={'format':'md'}).status_code==404
    assert client.post(A+'/panel-preview',headers=h,json={'module':'CRM','panel':definition(ident)['panels'][0]}).status_code==404
    # The dashboard configuration remains inspectable without leaked source content.
    config=client.get(A+f'/{dashboard}',headers=h).json();assert 'Original source content' not in str(config)


def test_dashboard_source_disappearing_after_approval_fails_without_creating_artifact(client,db):
    from tests.test_suite_operator import approve,tick
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h)
    pending=prepare(client,h,'CRM',definition(ident));approve(client,h,pending)
    assert client.delete(A+f'/{ident}',headers=h).status_code==200
    tick(client,db)
    run=client.get(ROOT+f'/runs/{pending["id"]}',headers=h).json()
    assert run['status']!='succeeded' and not run['receipts']
    assert not client.get(A,headers=h,params={'module':'CRM'}).json()['items']


def test_dashboard_chart_pdf_and_excel_reuse_server_totals_and_inert_source_rows(client,db):
    from tests.test_artifact_charts import body
    from openpyxl import load_workbook
    h,_,_,_=setup_suite(client,db)
    table=execute(client,db,h,command(client,h,'CRM','Prepare chart',local_plan={'summary':'Review table','steps':[{'tool':'crm.create_artifact','payload':body()}]}))['receipts'][0]['artifact_id']
    dashboard=execute(client,db,h,prepare(client,h,'CRM',definition(table,panels=[{'artifact_id':table,'revision':1,'display':'chart'}])))['receipts'][0]['artifact_id']
    response=client.get(A+f'/{dashboard}/download',headers=h,params={'format':'xlsx'});assert response.status_code==200,response.text[:200]
    book=load_workbook(io.BytesIO(response.content));assert book.active.title=='Dashboard'
    assert len(book['Chart analysis']._charts)==2
    assert book['Source 1']['B8'].value=='=2+2' and book['Source 1']['B8'].data_type=='s'
    assert book['Dashboard']['D6'].value=='1'
    assert book['Dashboard'].page_setup.fitToWidth==1
    response=client.get(A+f'/{dashboard}/download',headers=h,params={'format':'pdf'});assert response.status_code==200,response.text[:200]
    text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    assert '1250.75' in text and f'artifact #{table}' in text


def test_dashboard_rejects_recursive_sources_wrong_display_and_workspace(client,db):
    from app.apps.project_management.models import PMSWorkspace
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h)
    dashboard=execute(client,db,h,prepare(client,h,'CRM',definition(ident)))['receipts'][0]['artifact_id']
    for source_id,display in ((ident,'chart'),(ident,'table'),(dashboard,'auto')):
        response=client.post(A+'/panel-preview',headers=h,json={'module':'CRM','panel':{'artifact_id':source_id,'revision':1,'display':display}})
        assert response.status_code==422,response.text
    workspace=db.query(PMSWorkspace).first();assert workspace
    response=client.post(A+'/panel-preview',headers=h,json={'module':'CRM','workspace_id':workspace.id,'panel':definition(ident)['panels'][0]})
    assert response.status_code==403,response.text


def test_gemini_structured_dashboard_proposal_uses_existing_reviewed_tools(client,db,monkeypatch):
    from tests.test_ai_operator import mock_provider
    from app.ai_operator.models import OperatorApiLog
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h,'HRMS')
    mock_provider(monkeypatch,{'summary':'Review the pinned staffing dashboard','steps':[{'tool':'crm.create_artifact','payload':definition(ident)}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'module':'CRM','provider':'gemini',
        'text':f'Please assemble a staffing overview dashboard with saved artifact #{ident} version 1. Use a summary panel and propose for review.'})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='awaiting_approval',run
    assert db.query(OperatorApiLog).filter_by(suite_run_id=run['id'],provider='gemini',status='success').count()==1
    dashboard=execute(client,db,h,run)['receipts'][0]['artifact_id']
    assert client.get(A+f'/{dashboard}/panels/1',headers=h).json()['source']['id']==ident


def test_dashboard_export_checks_each_source_module_export_permission(client,db,monkeypatch):
    from fastapi import HTTPException
    from app.access import service
    from app.ai_operator.suite import MODULES
    h,_,_,_=setup_suite(client,db);ident=source(client,db,h,'HRMS')
    dashboard=execute(client,db,h,prepare(client,h,'CRM',definition(ident)))['receipts'][0]['artifact_id']
    original=service.check_background_access
    def guarded(db,user,module,action,*args,**kwargs):
        if module==MODULES['HRMS'] and action=='export':raise HTTPException(403,'Source module export is not permitted')
        return original(db,user,module,action,*args,**kwargs)
    monkeypatch.setattr(service,'check_background_access',guarded)
    assert client.get(A+f'/{dashboard}/panels/1',headers=h).status_code==200
    for fmt in ('md','docx','pdf','xlsx'):
        assert client.get(A+f'/{dashboard}/download',headers=h,params={'format':fmt}).status_code==403
