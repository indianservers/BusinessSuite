import io
import json
import zipfile
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from pptx import Presentation
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_bot_artifacts import command,execute,A
from ai_test_utils import auth_headers
from app.ai_operator.artifacts import Body,Slide
from app.ai_operator.artifact_exports import pdf,powerpoint,slide_pages,WIDTH,HEIGHT


def item(**extra):
    return {'id':7,'module':'CRM','revision':1,'current_revision':1,
        **Body(title='Delivery review',kind='presentation',slides=[Slide(title='Overview',bullets=['Scope agreed.','Review the delivery date.']),
            Slide(title='Next steps',bullets=['Confirm owners.'])]).model_dump(),
        'provenance':{'note':'Reviewed content; verify business facts.','citations':[]},**extra}


def test_presentation_exports_have_editable_text_and_complete_pdf_pages():
    source=item();content=powerpoint(source);deck=Presentation(io.BytesIO(content))
    assert len(deck.slides)==2
    text='\n'.join(shape.text for slide in deck.slides for shape in slide.shapes if shape.has_text_frame)
    assert 'Scope agreed.' in text and 'Confirm owners.' in text
    assert deck.slide_width/12700==WIDTH and deck.slide_height/12700==HEIGHT
    for slide in deck.slides:
        for shape in slide.shapes:
            assert shape.left>=0 and shape.top>=0
            assert shape.left+shape.width<=deck.slide_width and shape.top+shape.height<=deck.slide_height
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert not any(b'TargetMode="External"' in archive.read(n) for n in archive.namelist() if n.endswith('.rels'))
    reader=PdfReader(io.BytesIO(pdf(source)))
    assert len(reader.pages)==2
    assert 'Scope agreed.' in reader.pages[0].extract_text()
    assert 'Confirm owners.' in reader.pages[1].extract_text()


def test_long_slides_continue_without_losing_text_or_sources():
    points=[f'Point {i} '+('delivery commitment '*10)+f'END{i}' for i in range(6)]
    source=item(slides=[{'title':'W'*160,'bullets':points}],provenance={'citations':[{'id':'crm.tasks:42','label':'Recovery task','href':'/crm/tasks'}]})
    pages=slide_pages(source);assert len(pages)>2
    text=' '.join(line for page in pages for line in page['lines'])
    for i in range(6):assert f'END{i}' in text
    assert 'crm.tasks:42' in text and '/crm/tasks' in text
    for page in pages:assert page['body_top']+len(page['lines'])*26<=HEIGHT-42
    deck=Presentation(io.BytesIO(powerpoint(source)));assert len(deck.slides)==len(pages)
    reader=PdfReader(io.BytesIO(pdf(source)));assert len(reader.pages)==len(pages)
    exported=' '.join(page.extract_text() for page in reader.pages)
    for i in range(6):assert f'END{i}' in exported


@pytest.mark.parametrize('kind',['document','checklist','table'])
def test_pdf_exports_escape_markup_and_keep_formula_like_values_inert(kind):
    body={'title':'Literal content','kind':kind,'content':'<img src="https://example.invalid/private"> & literal instructions.'}
    if kind=='table':body.update(columns=['Name','Value'],rows=[['=1+1','<b>literal</b>']])
    source=item(**Body(**body).model_dump());source.pop('slides',None)
    text='\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf(source))).pages)
    assert '<img src=' in text
    if kind=='table':assert '=1+1' in text and '<b>literal</b>' in text


def test_wide_table_pdf_splits_long_rows_and_keeps_last_cell():
    source=item(**Body(title='Wide table',kind='table',columns=[f'Column {i}' for i in range(12)],
        rows=[['W'*490+f' END{i}' for i in range(12)]]).model_dump());source.pop('slides',None)
    reader=PdfReader(io.BytesIO(pdf(source)))
    assert len(reader.pages)>1
    text=' '.join(page.extract_text() for page in reader.pages)
    assert 'END11' in text


def test_unsupported_pdf_glyphs_fail_explicitly_and_old_body_hash_shape_stays_stable():
    assert 'slides' not in Body(title='Existing',content='Existing content').model_dump()
    with pytest.raises(HTTPException) as exc:pdf(item(title='Robot \U0001f916'))
    assert exc.value.status_code==422 and 'font' in exc.value.detail
    for data in [{'title':'Invalid','kind':'presentation'},
        {'title':'Invalid','content':'Text','slides':[{'title':'Slide','bullets':[]}]},
        {'title':'Invalid','kind':'presentation','slides':[{'title':'Slide','bullets':['x'*241]}]},
        {'title':'Invalid','kind':'presentation','slides':[{'title':'Slide','bullets':['x']*7}]},
        {'title':'Invalid','content':'Unpaired \ud800'}]:
        with pytest.raises(ValueError):Body.model_validate(data)
    from types import SimpleNamespace
    from app.ai_operator.artifacts import local_plan
    plan=local_plan(SimpleNamespace(module='CRM',text='Create PDF called Review: Agreed scope'),None,None,[])
    assert plan.steps[0].payload['kind']=='document' and plan.steps[0].payload['content']=='Agreed scope'


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_reviewed_slide_creation_followup_edits_and_historical_exports(client,db,module):
    h,_,_,_=setup_suite(client,db)
    conversation=client.post(ROOT+'/conversations',headers=h,json={'title':'Presentation review'}).json()['id']
    run=command(client,h,module,'Create presentation called Delivery review: Overview | Scope agreed || Next steps | Confirm dates',conversation_id=conversation)
    assert run['status']=='awaiting_approval',run
    assert run['plan']['steps'][0]['payload']['kind']=='presentation'
    assert client.get(A,headers=h,params={'module':module}).json()['items']==[]
    rename=command(client,h,module,'Rename slide 2 to Agreed actions',conversation_id=conversation)
    body=rename['plan']['steps'][0]['payload'];assert body['title']=='Delivery review' and body['slides'][1]['title']=='Agreed actions'
    made=execute(client,db,h,rename);ident=made['receipts'][0]['artifact_id']
    updated=command(client,h,module,'Add point to slide 2: Assign an owner',conversation_id=conversation)
    assert updated['plan']['steps'][0]['payload']['expected_revision']==1
    execute(client,db,h,updated)
    current=client.get(A+f'/{ident}',headers=h).json()
    assert current['revision']==2 and current['slides'][1]['bullets']==['Confirm dates','Assign an owner']
    for format in ('pdf','pptx','docx','md'):
        response=client.get(A+f'/{ident}/download',headers=h,params={'format':format,'revision':1})
        assert response.status_code==200,response.text
        assert 'no-store' in response.headers['cache-control']
        if format=='pptx':
            text=' '.join(s.text for slide in Presentation(io.BytesIO(response.content)).slides for s in slide.shapes if s.has_text_frame)
            assert 'Agreed actions' in text and 'Assign an owner' not in text
        elif format=='pdf':assert 'Assign an owner' not in ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view','hrms_view','pms_manage_tasks'])
    assert client.get(A+f'/{ident}/download',headers=other,params={'format':'pptx'}).status_code==404
    stale=client.post(ROOT+f'/runs/{updated["id"]}/approve',headers=h,json={'plan_hash':rename['plan_hash']})
    assert stale.status_code==409
    moved=command(client,h,module,'Move slide 2 to 1',conversation_id=conversation)
    assert moved['status']=='awaiting_approval',moved
    assert moved['plan']['steps'][0]['payload']['slides'][0]['title']=='Agreed actions'


def test_inline_slide_revision_is_validated_and_needs_fresh_review(client,db):
    h,_,_,_=setup_suite(client,db);conversation=client.post(ROOT+'/conversations',headers=h,json={'title':'Inline slide review'}).json()['id']
    run=command(client,h,'CRM','Create slide deck called Launch: Overview | Scope agreed',conversation_id=conversation)
    request={'request_key':str(uuid4()),'plan_hash':run['plan_hash'],'changes':[{'step':1,'field':'slides','value':[{'title':'Updated overview','bullets':['Owner confirmed']}]}]}
    response=client.post(ROOT+f'/runs/{run["id"]}/revise',headers=h,json=request)
    assert response.status_code==200,response.text
    revised=response.json();assert revised['status']=='awaiting_approval' and revised['plan_hash']!=run['plan_hash']
    assert client.get(A,headers=h,params={'module':'CRM'}).json()['items']==[]
    assert client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==409
    assert client.post(ROOT+f'/runs/{run["id"]}/revise',headers=h,json=request).json()['id']==revised['id']
    bad=client.post(ROOT+f'/runs/{revised["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':revised['plan_hash'],'changes':[{'step':1,'field':'slides','value':[]}]})
    assert bad.status_code==422
    assert client.get(ROOT+f'/runs/{revised["id"]}',headers=h).json()['status']=='awaiting_approval'
    execute(client,db,h,revised)


def test_cloud_can_prepare_structured_slides_without_saving_them(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db);body=Body.model_validate({k:v for k,v in item().items() if k in Body.model_fields}).model_dump()
    calls=mock_provider(monkeypatch,{'summary':'Review the presentation','steps':[{'tool':'crm.create_artifact','payload':body}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':'Prepare a presentation comparing the supplied delivery findings'})
    assert response.status_code==200 and response.json()['status']=='awaiting_approval',response.text
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    assert 'structured slides' in outbound['tools'][next(i for i,t in enumerate(outbound['tools']) if t['name']=='crm.create_artifact')]['description']
    assert client.get(A,headers=h,params={'module':'CRM'}).json()['items']==[]


def test_literal_local_slide_reorder_and_removal_preserve_other_content():
    from app.ai_operator.artifact_slides import edit
    slides=[{'title':'First','bullets':['One']},{'title':'Second','bullets':['Two']}]
    moved=edit(slides,'Move slide 2 to 1');assert moved[0]['title']=='Second' and slides[0]['title']=='First'
    assert edit(moved,'Replace point 1 on slide 2: Revised')[1]['bullets']==['Revised']
    assert edit(slides,'Remove slide 2')==[slides[0]]
    with pytest.raises(HTTPException):edit(slides,'Replace slide 9: Missing')
    with pytest.raises(HTTPException):edit([slides[0]],'Remove slide 1')


def test_new_export_formats_require_native_export_permission_before_rendering(client,db,monkeypatch):
    from app.access import service
    from app.ai_operator import artifact_exports
    h,_,_,_=setup_suite(client,db)
    made=execute(client,db,h,command(client,h,'CRM','Create presentation called Review: Scope | Agreed'))
    ident=made['receipts'][0]['artifact_id'];original=service.check_background_access
    def deny(*args,**kwargs):
        if args[-1]=='export':raise HTTPException(403,'Export access is required')
        return original(*args,**kwargs)
    def unexpected(*args,**kwargs):raise AssertionError('Renderer must not run without export permission')
    monkeypatch.setattr(service,'check_background_access',deny)
    monkeypatch.setattr(artifact_exports,'pdf',unexpected);monkeypatch.setattr(artifact_exports,'powerpoint',unexpected)
    for format in ('pdf','pptx'):
        response=client.get(A+f'/{ident}/download',headers=h,params={'format':format})
        assert response.status_code==403,response.text
    from app.ai_agents import api
    monkeypatch.setattr(service,'check_background_access',original)
    def exhausted(*args,**kwargs):raise HTTPException(429,'Export rate limit reached')
    monkeypatch.setattr(api,'_require_ai_rate_limit',exhausted)
    for format in ('pdf','pptx'):
        response=client.get(A+f'/{ident}/download',headers=h,params={'format':format})
        assert response.status_code==429,response.text


def test_provider_repair_cannot_change_presentation_into_another_format(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);calls=[]
    def propose(*args,**kwargs):
        calls.append(kwargs)
        body={'title':'Presentation','kind':'presentation','content':'Invalid mixed format','slides':[{'title':'Overview','bullets':['Keep this slide']}]} if len(calls)==1 else {'title':'Presentation','kind':'document','content':'Silently changed format'}
        return {'summary':'Review artifact','steps':[{'tool':'crm.create_artifact','payload':body}]}
    monkeypatch.setattr(suite,'generate_json',propose)
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':'Create a presentation with a delivery overview'})
    assert r.status_code==200 and r.json()['status']=='failed',r.text
    assert len(calls)==2 and r.json()['approval_id'] is None
    assert client.get(A,headers=h,params={'module':'CRM'}).json()['items']==[]
