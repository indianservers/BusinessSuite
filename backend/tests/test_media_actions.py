import io
import wave
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.ai_operator import gemini_media,artifacts
from app.ai_operator.assistant_models import AssistantMessage
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_suite_workspace import chat,upload,say,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from ai_test_utils import auth_headers


def setup(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db)
    config=db.query(OperatorProvider).filter_by(provider='gemini').one()
    config.media_settings={'transcription_enabled':True};db.commit()
    ident=chat(client,h);raw=io.BytesIO()
    with wave.open(raw,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\x00\x00'*8000)
    file=upload(client,h,ident,'meeting.wav',raw.getvalue());calls=[]
    def transcribe(config,content,**kw):
        calls.append((config.model,content))
        return gemini_media.Transcript(text='Please review the delivery tomorrow.',language='English',
            segments=[{'start_seconds':0,'end_seconds':1,'text':'Please review the delivery tomorrow.'}],notes=[]),{'promptTokenCount':10,'candidatesTokenCount':20,'thoughtsTokenCount':2}
    monkeypatch.setattr(gemini_media,'transcribe_wav',transcribe)
    return h,user,ident,file,calls


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_transcription_is_reviewed_private_cited_versioned_and_never_executes_speech(client,db,monkeypatch,module):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,f'{module}: transcribe audio file #{file["id"]}',module=module)
    assert run['status']=='awaiting_approval' and not calls
    assert run['plan']['steps'][0]['tool']==f'{module.lower()}.transcribe_audio'
    payload=run['plan']['steps'][0]['payload']
    assert payload['sha256']==file['sha256'] and payload['model']=='gemini-3.5-flash-lite'
    direct=client.post(ROOT+'/media/transcribe-approved',headers=h,json={**payload,'suite_run_id':run['id'],'suite_step':1})
    assert direct.status_code==403 and not calls
    approve(client,h,run);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(calls)==1,final.get('error_code')
    receipt=final['receipts'][0];assert receipt['artifact_revision']==1
    response=client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}',headers=h)
    assert response.status_code==200
    item=response.json();assert item['content']=='Please review the delivery tomorrow.' and item['module']==module
    assert item['provenance']['citations'][0]['id']==f'upload:{file["id"]}'
    assert item['provenance']['media']['core_prompt']['key']=='audio-transcription'
    edit=say(client,h,ident,'Append: Reviewed by the owner.',module=module)
    assert edit['status']=='awaiting_approval'
    approve(client,h,edit);tick(client,db)
    edited=client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}',headers=h).json()
    assert edited['revision']==2 and edited['content'].endswith('Reviewed by the owner.')
    assert edited['provenance']['source_media']['source_sha256']==file['sha256'] and len(calls)==1
    log=db.query(OperatorApiLog).filter_by(purpose='media_transcription').one()
    assert log.model=='gemini-3.5-flash-lite' and log.status=='success' and log.estimated_cost is None
    assert (log.input_tokens,log.output_tokens)==(10,22)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    denied=client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}',headers=other);assert denied.status_code==404
    exported=client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}/download',headers=h,params={'format':'docx'})
    assert exported.status_code==200
    from app.apps.crm.models import CRMTask
    assert db.query(CRMTask).count()==0
    tick(client,db);assert len(calls)==1


def test_stored_transcript_resumes_artifact_failure_without_new_provider_call(client,db,monkeypatch):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'transcribe this audio',module='CRM');approve(client,h,run)
    original=artifacts.store_revision
    def unavailable(*args,**kw):raise HTTPException(503,'Synthetic artifact interruption')
    monkeypatch.setattr(artifacts,'store_revision',unavailable);tick(client,db)
    stopped=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume'] and len(calls)==1
    monkeypatch.setattr(artifacts,'store_revision',original)
    response=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code==200 and response.json()['status']=='queued'
    tick(client,db);final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(calls)==1
    assert db.query(OperatorApiLog).filter_by(purpose='media_transcription').count()==1
    journal=db.query(AssistantMessage).filter_by(tool='suite.media.transcription').one()
    assert journal.status=='completed'


def test_unknown_provider_outcome_never_retries_or_resumes(client,db,monkeypatch):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    def timeout(*args,**kw):calls.append('timeout');raise HTTPException(504,'MEDIA_PROVIDER_TIMEOUT')
    monkeypatch.setattr(gemini_media,'transcribe_wav',timeout)
    run=say(client,h,ident,'transcribe audio',module='CRM');approve(client,h,run);tick(client,db);tick(client,db)
    stopped=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and not stopped['can_resume'] and len(calls)==1
    response=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code==409 and len(calls)==1
    assert db.query(AssistantMessage).filter_by(tool='suite.media.transcription').one().status=='uncertain'


@pytest.mark.parametrize('change',['delete','policy','integrity'])
def test_source_and_policy_are_rechecked_at_review_and_dispatch(client,db,monkeypatch,change):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'transcribe audio',module='CRM')
    if change=='delete':
        assert client.delete(ROOT+f'/conversations/{ident}/attachments/{file["id"]}',headers=h).status_code==200
    elif change=='policy':
        config=db.query(OperatorProvider).filter_by(provider='gemini').one();config.media_settings={};db.commit()
    else:
        row=db.get(AssistantMessage,file['id']);row.result={**row.result,'content_b64':'aW52YWxpZA=='};db.commit()
    response=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code in {404,409} and not calls


def test_audio_selection_clarifies_when_multiple_sources_exist(client,db,monkeypatch):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    # Different bytes avoid the existing attachment deduplication boundary.
    from app.ai_operator.suite_uploads import owned
    import base64
    raw=bytearray(base64.b64decode(owned(db,user,ident,file['id']).result['content_b64']));raw[-1]=1
    second=upload(client,h,ident,'second.wav',bytes(raw))
    result=say(client,h,ident,'transcribe audio',module='CRM')
    assert result['status']=='needs_clarification' and not calls
    chosen=say(client,h,ident,f'file #{second["id"]}',module='CRM')
    assert chosen['status']=='awaiting_approval' and chosen['plan']['steps'][0]['payload']['attachment_id']==second['id']


def test_capability_revoked_after_approval_prevents_dispatch(client,db,monkeypatch):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'transcribe audio',module='CRM');approve(client,h,run)
    config=db.query(OperatorProvider).filter_by(provider='gemini').one();config.media_settings={};db.commit()
    tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='paused' and not calls
    assert db.query(OperatorApiLog).filter_by(purpose='media_transcription').count()==0


def test_confirmed_artifact_receipt_recovers_without_dispatching_again(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'transcribe audio',module='CRM');approve(client,h,run)
    original=suite.finish_step
    def lost_receipt(*args,**kwargs):raise RuntimeError('Synthetic receipt interruption')
    monkeypatch.setattr(suite,'finish_step',lost_receipt);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='needs_reconciliation' and final['can_resume'] and len(calls)==1
    monkeypatch.setattr(suite,'finish_step',original)
    recovered=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert recovered.status_code==200 and recovered.json()['status']=='succeeded' and len(calls)==1
    assert len(recovered.json()['receipts'])==1


def test_transcript_title_revision_requires_new_review_without_processing_audio(client,db,monkeypatch):
    h,user,ident,file,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'transcribe audio',module='CRM')
    response=client.post(ROOT+f'/runs/{run["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':run['plan_hash'],
        'changes':[{'step':1,'field':'title','value':'Delivery meeting transcript'}]})
    assert response.status_code==200 and not calls
    revised=response.json();assert revised['plan_hash']!=run['plan_hash']
    assert revised['plan']['steps'][0]['payload']['title']=='Delivery meeting transcript'
    stale=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert stale.status_code==409
