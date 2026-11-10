import io
from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from app.apps.crm.models import CRMTask
from app.ai_operator.assistant_models import AssistantMessage
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/suite'

def chat(client,h):
    r=client.post(ROOT+'/conversations',headers=h,json={'title':'Workspace QA'})
    assert r.status_code==201,r.text
    return r.json()['id']

def upload(client,h,ident,name,content):
    r=client.post(f'{ROOT}/conversations/{ident}/attachments',headers=h,files={'file':(name,content)})
    assert r.status_code==201,r.text
    return r.json()

def say(client,h,ident,text,**kw):
    r=client.post(ROOT+'/commands',headers=h,json={'text':text,'provider':'local','conversation_id':ident,'request_key':str(uuid4()),**kw})
    assert r.status_code==200,r.text
    return r.json()

def test_private_upload_restores_downloads_and_supplies_cited_local_context(client,db):
    h,_,_,_=setup_suite(client,db);ident=chat(client,h)
    data=b'Delivery risks: customer response pending. No verified ERP facts.'
    file=upload(client,h,ident,'../../delivery.txt',data)
    assert file['name']=='delivery.txt' and 'content_b64' not in file
    duplicate=upload(client,h,ident,'delivery.txt',data);assert duplicate['id']==file['id']
    restored=client.get(f'{ROOT}/conversations/{ident}',headers=h).json()
    assert restored['attachments'][0]['id']==file['id']
    download=client.get(f'{ROOT}/conversations/{ident}/attachments/{file["id"]}/download',headers=h)
    assert download.content==data and download.headers['cache-control']=='private, no-store'
    result=say(client,h,ident,'summarize the uploaded file',attachment_ids=[file['id']])
    assert result['status']=='answered',result
    assert 'customer response pending' in result['plan']['summary']
    assert result['result']['citations'][0]['id']==f'upload:{file["id"]}'
    assert result['result_cards'][0]['kind']=='answer'
    assert db.query(CRMTask).count()==0

def test_spreadsheet_rows_become_reviewed_draft_with_no_automatic_import(client,db):
    h,_,_,_=setup_suite(client,db);ident=chat(client,h)
    from openpyxl import Workbook
    book=Workbook();book.active.append(['module','title','priority']);book.active.append(['CRM','Uploaded follow-up','High'])
    output=io.BytesIO();book.save(output)
    file=upload(client,h,ident,'tasks.xlsx',output.getvalue())
    assert file['row_count']==1 and file['preview'][1][1]=='Uploaded follow-up'
    result=say(client,h,ident,'create tasks from the uploaded spreadsheet',attachment_ids=[file['id']])
    assert result['status']=='awaiting_approval',result
    assert db.query(CRMTask).count()==0
    approve(client,h,result);tick(client,db)
    final=client.get(f'{ROOT}/runs/{result["id"]}',headers=h).json()
    assert final['status']=='succeeded' and db.query(CRMTask).one().title=='Uploaded follow-up'
    assert final['result_cards'][0]['href']=='/crm/tasks'

def test_inline_revision_revalidates_and_retires_old_approval(client,db):
    h,_,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'CRM: create task "Original title"')
    invalid=client.post(f'{ROOT}/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'title','value':''}]})
    assert invalid.status_code==422,invalid.text
    assert client.get(f'{ROOT}/conversations/{ident}',headers=h).json()['runs'][-1]['id']==draft['id']
    payload={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'title','value':'Edited title'},{'step':1,'field':'priority','value':'High'}]}
    r=client.post(f'{ROOT}/runs/{draft["id"]}/revise',headers=h,json=payload)
    assert r.status_code==200,r.text
    revised=r.json();assert revised['status']=='awaiting_approval',revised
    assert revised['id']!=draft['id'] and revised['plan_hash']!=draft['plan_hash']
    assert db.query(CRMTask).count()==0
    retry=client.post(f'{ROOT}/runs/{draft["id"]}/revise',headers=h,json=payload)
    assert retry.status_code==200 and retry.json()['id']==revised['id']
    assert client.post(f'{ROOT}/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==409
    approve(client,h,revised);tick(client,db)
    assert db.query(CRMTask).one().title=='Edited title'
    assert client.post(f'{ROOT}/runs/{revised["id"]}/revise',headers=h,json={**payload,'request_key':str(uuid4()),'plan_hash':revised['plan_hash']}).status_code==409

def test_upload_and_revision_enforce_owner_conversation_and_deleted_source(client,db):
    h,_,_,_=setup_suite(client,db);ident=chat(client,h);file=upload(client,h,ident,'tasks.csv',b'module,title\nCRM,Private draft\n')
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(f'{ROOT}/conversations/{ident}/attachments/{file["id"]}/download',headers=other).status_code==404
    another=chat(client,h)
    bad=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'summarize file','provider':'local','conversation_id':another,'attachment_ids':[file['id']]})
    assert bad.status_code==404
    draft=say(client,h,ident,'create tasks from uploaded spreadsheet',attachment_ids=[file['id']])
    assert draft['status']=='awaiting_approval',draft
    assert client.post(f'{ROOT}/runs/{draft["id"]}/revise',headers=other,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'title','value':'Stolen'}]}).status_code==404
    assert client.delete(f'{ROOT}/conversations/{ident}/attachments/{file["id"]}',headers=h).status_code==200
    assert client.post(f'{ROOT}/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==404
    assert db.query(CRMTask).count()==0

def test_parser_handles_documents_and_rejects_unsupported_or_bomb_content():
    import pytest,zipfile
    from fastapi import HTTPException
    from app.ai_operator.suite_uploads import parse
    from docx import Document
    doc=Document();doc.add_paragraph('Customer delivery meeting notes');out=io.BytesIO();doc.save(out)
    assert 'meeting notes' in parse(out.getvalue(),'notes.docx')['text']
    for name,data in [('macro.xlsm',b'bad'),('broken.xlsx',b'bad'),('notes.txt',b'\xff\xfe'),('empty.txt',b'')]:
        with pytest.raises(HTTPException):parse(data,name)
    bomb=io.BytesIO()
    with zipfile.ZipFile(bomb,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('huge.xml',b'x'*25_000_001)
    with pytest.raises(HTTPException) as error:parse(bomb.getvalue(),'bomb.docx')
    assert error.value.status_code==413
    with pytest.raises(HTTPException):parse(b'x'*5_000_001,'too-large.txt')
    from reportlab.pdfgen.canvas import Canvas
    pdf=io.BytesIO();canvas=Canvas(pdf);canvas.drawString(40,700,'Server parsed delivery notes');canvas.save()
    assert 'delivery notes' in parse(pdf.getvalue(),'notes.pdf')['text']
