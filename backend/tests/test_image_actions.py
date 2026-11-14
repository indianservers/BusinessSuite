import io
from uuid import uuid4
import pytest
from fastapi import HTTPException
from PIL import Image
from app.ai_operator import gemini_media,artifacts
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from app.ai_operator.assistant_models import AssistantMessage
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_suite_workspace import chat,upload,say,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from ai_test_utils import auth_headers


def pixels(color):
    out=io.BytesIO();Image.new('RGBA',(4,3),color).save(out,format='PNG');return out.getvalue()


def test_image_normalization_preserves_orientation_and_strips_private_metadata():
    original=Image.new('RGB',(4,3),'blue');exif=Image.Exif()
    exif[274]=6;exif[270]='Private synthetic camera note'
    raw=io.BytesIO();original.save(raw,format='JPEG',exif=exif)
    clean,width,height=gemini_media.image_bytes(raw.getvalue(),'image/jpeg')
    assert (width,height)==(3,4)
    with Image.open(io.BytesIO(clean)) as saved:
        assert saved.size==(3,4) and not saved.getexif() and not saved.info
    assert b'Private synthetic camera note' not in clean


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_local_image_import_requires_review_without_provider(client,db,monkeypatch,module):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    def forbidden(*args,**kwargs):raise AssertionError('Local import must not call an image model')
    monkeypatch.setattr(gemini_media,'generate_image',forbidden)
    file=upload(client,h,ident,'synthetic-logo.png',pixels('blue'))
    run=say(client,h,ident,f'Import image file #{file["id"]} called Synthetic logo',module=module)
    assert run['status']=='awaiting_approval'
    step=run['plan']['steps'][0];assert step['tool']==f'{module.lower()}.import_image'
    direct=client.post(ROOT+'/media/import-image-approved',headers=h,json={**step['payload'],'suite_run_id':run['id'],'suite_step':1})
    assert direct.status_code==403
    final=finish(client,db,h,run);artifact=final['receipts'][0]['artifact_id']
    image=client.get(ROOT+f'/artifacts/{artifact}/image',headers=h)
    assert image.status_code==200 and image.content==pixels('blue')
    item=client.get(ROOT+f'/artifacts/{artifact}',headers=h).json()
    assert item['provenance']['media']['external_model_calls']==0
    assert db.query(OperatorApiLog).filter_by(purpose='media_image').count()==0


def test_local_image_import_deleted_source_blocks_approval(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    file=upload(client,h,ident,'synthetic-logo.png',pixels('blue'))
    run=say(client,h,ident,f'Import image file #{file["id"]}',module='CRM')
    assert run['status']=='awaiting_approval'
    assert client.delete(ROOT+f'/conversations/{ident}/attachments/{file["id"]}',headers=h).status_code==200
    result=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert result.status_code==404


def test_local_image_import_recovers_committed_receipt_without_duplicate(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    file=upload(client,h,ident,'synthetic-logo.png',pixels('blue'))
    run=say(client,h,ident,f'Import image file #{file["id"]}',module='CRM');approve(client,h,run)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost import receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db)
    stopped=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume']
    monkeypatch.setattr(suite,'finish_step',original)
    result=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert result.status_code==200 and result.json()['status']=='succeeded'
    artifact=result.json()['receipts'][0]['artifact_id']
    again=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert again.status_code==200
    tick(client,db)
    assert client.get(ROOT+f'/artifacts/{artifact}',headers=h).json()['revision']==1


def setup(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db)
    config=db.query(OperatorProvider).filter_by(provider='gemini').one();config.media_settings={'image_enabled':True};db.commit()
    ident=chat(client,h);calls=[]
    def generate(config,prompt,**kwargs):
        calls.append({'model':config.model,'prompt':prompt,'references':kwargs.get('references',[])})
        return gemini_media.ImageResult(pixels('red' if 'red' in prompt else 'blue'),'image/png',4,3,'Synthetic generated image.',
            config.model,{'promptTokenCount':30,'candidatesTokenCount':40})
    monkeypatch.setattr(gemini_media,'generate_image',generate)
    return h,user,ident,calls


def finish(client,db,h,run):
    assert run['status']=='awaiting_approval'
    approve(client,h,run);tick(client,db)
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=h);assert response.status_code==200
    value=response.json();assert value['status']=='succeeded',value.get('error_code')
    return value


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_image_generation_and_followup_edit_preserve_private_versions_and_review(client,db,monkeypatch,module):
    h,user,ident,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,f'{module}: Create image called Delivery banner: a blue delivery van',module=module)
    assert run['status']=='awaiting_approval' and not calls
    payload=run['plan']['steps'][0]['payload'];assert payload['model']=='gemini-3.1-flash-image'
    direct=client.post(ROOT+'/media/generate-image-approved',headers=h,json={**payload,'suite_run_id':run['id'],'suite_step':1})
    assert direct.status_code==403 and not calls
    first=finish(client,db,h,run);artifact=first['receipts'][0]['artifact_id']
    assert len(calls)==1 and not calls[0]['references']
    changed=say(client,h,ident,'Make it red',module=module)
    assert changed['status']=='awaiting_approval' and len(calls)==1
    assert changed['plan']['steps'][0]['tool']==f'{module.lower()}.edit_image'
    second=finish(client,db,h,changed)
    assert second['receipts'][0]['artifact_id']==artifact and second['receipts'][0]['artifact_revision']==2
    assert len(calls)==2 and calls[1]['references'][0][0]==pixels('blue')
    url=ROOT+f'/artifacts/{artifact}'
    old=client.get(url+'/image',headers=h,params={'revision':1});new=client.get(url+'/image',headers=h)
    assert old.content==pixels('blue') and new.content==pixels('red')
    item=client.get(url,headers=h).json();assert item['kind']=='image' and item['provenance']['media']['core_prompt']['key']=='image-generation'
    logs=db.query(OperatorApiLog).filter_by(purpose='media_image').all()
    assert len(logs)==2 and all(l.estimated_cost is None and l.input_tokens==30 and l.output_tokens==40 for l in logs)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    denied=client.get(url+'/image',headers=other);assert denied.status_code==404


def test_uploaded_reference_is_exact_owned_source_and_deleted_source_blocks_approval(client,db,monkeypatch):
    h,user,ident,calls=setup(client,db,monkeypatch)
    file=upload(client,h,ident,'reference.png',pixels('blue'))
    run=say(client,h,ident,f'Create image from file #{file["id"]} called Variant: a red van',module='CRM')
    first=finish(client,db,h,run)
    assert calls[0]['references'][0][0]==pixels('blue')
    item=client.get(ROOT+f'/artifacts/{first["receipts"][0]["artifact_id"]}',headers=h).json()
    assert item['provenance']['citations'][0]['id']==f'upload:{file["id"]}'
    again=say(client,h,ident,f'Create image from file #{file["id"]}: a green van',module='CRM')
    assert client.delete(ROOT+f'/conversations/{ident}/attachments/{file["id"]}',headers=h).status_code==200
    approval=client.post(ROOT+f'/runs/{again["id"]}/approve',headers=h,json={'plan_hash':again['plan_hash']})
    assert approval.status_code==404 and len(calls)==1


def test_image_output_recovers_without_new_provider_call(client,db,monkeypatch):
    h,user,ident,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'Create image: a blue van',module='CRM');approve(client,h,run)
    original=artifacts.store_revision
    def interrupted(*args,**kwargs):raise HTTPException(503,'Synthetic storage interruption')
    monkeypatch.setattr(artifacts,'store_revision',interrupted);tick(client,db)
    stopped=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume'] and len(calls)==1
    monkeypatch.setattr(artifacts,'store_revision',original)
    response=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code==200
    tick(client,db);final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(calls)==1


def test_edited_image_receipt_can_be_recovered_after_its_version_already_changed(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,ident,calls=setup(client,db,monkeypatch)
    first=finish(client,db,h,say(client,h,ident,'Create image: a blue van',module='CRM'))
    edit=say(client,h,ident,'Make it red',module='CRM');approve(client,h,edit)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost outer receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db)
    stopped=client.get(ROOT+f'/runs/{edit["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume'] and len(calls)==2
    monkeypatch.setattr(suite,'finish_step',original)
    response=client.post(ROOT+f'/runs/{edit["id"]}/resume',headers=h,json={'plan_hash':edit['plan_hash']})
    assert response.status_code==200 and response.json()['status']=='succeeded' and len(calls)==2
    assert response.json()['receipts'][0]['artifact_revision']==2


def test_uncertain_image_call_never_replays_and_revoked_policy_never_dispatches(client,db,monkeypatch):
    h,user,ident,calls=setup(client,db,monkeypatch)
    def timeout(*args,**kwargs):calls.append('timeout');raise HTTPException(504,'MEDIA_PROVIDER_TIMEOUT')
    monkeypatch.setattr(gemini_media,'generate_image',timeout)
    run=say(client,h,ident,'Create image: a blue van',module='CRM');approve(client,h,run);tick(client,db);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='needs_reconciliation' and not final['can_resume'] and len(calls)==1
    denied=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert denied.status_code==409 and len(calls)==1
    assert db.query(AssistantMessage).filter_by(tool='suite.media.image').one().status=='uncertain'


def test_image_prompt_revision_needs_new_approval(client,db,monkeypatch):
    h,user,ident,calls=setup(client,db,monkeypatch)
    run=say(client,h,ident,'Create image: a blue van',module='CRM')
    response=client.post(ROOT+f'/runs/{run["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':run['plan_hash'],
        'changes':[{'step':1,'field':'prompt','value':'A red van'}]})
    assert response.status_code==200 and response.json()['plan_hash']!=run['plan_hash'] and not calls
    stale=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert stale.status_code==409


def test_model_authored_image_proposal_is_sealed_before_review_without_model_nonces(client,db,monkeypatch):
    h,user,ident,calls=setup(client,db,monkeypatch)
    file=upload(client,h,ident,'reference.png',pixels('blue'))
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
        'conversation_id':ident,'text':'Review this proposed image','local_plan':{'summary':'Create an illustrative image.',
            'steps':[{'tool':'crm.generate_image','payload':{'title':'Illustration','prompt':'A blue delivery van',
                'references':[{'attachment_id':file['id']}]}}]}})
    assert response.status_code==200
    run=response.json();assert run['status']=='awaiting_approval' and not calls
    sealed=run['plan']['steps'][0]['payload']
    assert sealed['conversation_id']==ident and sealed['model']=='gemini-3.1-flash-image'
    assert sealed['references'][0]['sha256']==file['sha256'] and len(sealed['media_policy_sha256'])==64
    finish(client,db,h,run);assert len(calls)==1


def test_image_tool_discovery_does_not_require_the_model_to_invent_server_hashes():
    from app.ai_operator.suite_tools import TOOLS,payload_schema
    schema=payload_schema(TOOLS['crm.edit_image'])
    assert not {'conversation_id','model','media_policy_sha256','expected_revision','source_sha256'}&set(schema['properties'])
    assert 'artifact_id' in schema['required']
    assert 'sha256' not in schema['$defs']['Reference']['properties']


def test_image_quota_rejection_has_safe_telemetry_and_no_replay(client,db,monkeypatch):
    h,user,ident,calls=setup(client,db,monkeypatch)
    def exhausted(*args,**kwargs):calls.append('rejected');raise gemini_media.MediaProviderError(429,0,61)
    monkeypatch.setattr(gemini_media,'generate_image',exhausted)
    run=say(client,h,ident,'Create image: a blue van',module='CRM');approve(client,h,run);tick(client,db);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='needs_reconciliation' and not final['can_resume'] and len(calls)==1
    assert final['result']['media_error']=={'provider_http_status':429,'quota_limit':0,'retry_after_seconds':61}
    log=db.query(OperatorApiLog).filter_by(purpose='media_image').one();assert log.http_status==429 and log.estimated_cost is None
    assert db.query(AssistantMessage).filter_by(tool='suite.media.image').one().status=='rejected'
