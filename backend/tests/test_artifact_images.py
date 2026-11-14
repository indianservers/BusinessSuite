"""Binary artifact persistence contracts; not a generation/approval benchmark."""
import base64
import hashlib
import io
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from PIL import Image
from app.ai_operator import artifacts,artifact_images
from app.ai_operator.gemini_media import image_bytes
from app.ai_operator.service import digest
from app.ai_operator.assistant_models import AssistantMessage
from tests.test_suite_operator import setup_suite
from tests.test_suite_workspace import chat,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from ai_test_utils import auth_headers


def pixels(color='blue'):
    raw=io.BytesIO();Image.new('RGB',(4,3),color).save(raw,format='PNG')
    content,width,height=image_bytes(raw.getvalue(),'image/png')
    return content,{'mime_type':'image/png','width':width,'height':height,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}


def internal_run(ident,editing=False):
    plan={'summary':'Synthetic internal image persistence fixture','steps':[{'tool':'crm.edit_image' if editing else 'crm.generate_image','payload':{}}]}
    return SimpleNamespace(id=int(uuid4().hex[:7],16),workspace_id=None,plan=plan,plan_hash=digest(plan),
        result={'request':{'conversation_id':ident},'citations':[]})


def persist(db,user,ident,color='blue',previous=None):
    content,manifest=pixels(color)
    body=artifacts.Body(title='Synthetic image',kind='image',image=manifest).model_dump()
    if previous:body.update(artifact_id=previous['artifact_id'],expected_revision=previous['artifact_revision'])
    receipt=artifacts.store_revision(db,user,internal_run(ident,bool(previous)),'CRM',body,1,editing=bool(previous),media_content=content)
    return receipt,content


def test_private_image_versions_have_exact_authenticated_previews_and_downloads(client,db):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    first,blue=persist(db,user,ident);second,red=persist(db,user,ident,'red',first)
    assert first['artifact_id']==second['artifact_id'] and second['artifact_revision']==2
    url=ROOT+f'/artifacts/{first["artifact_id"]}'
    public=client.get(url,headers=h);assert public.status_code==200
    assert public.json()['image']['sha256']==hashlib.sha256(red).hexdigest()
    assert 'image_b64' not in public.text and base64.b64encode(red).decode() not in public.text
    for revision,expected in [(1,blue),(2,red)]:
        response=client.get(url+'/image',headers=h,params={'revision':revision})
        assert response.status_code==200 and response.content==expected
        assert response.headers['content-type']=='image/png' and response.headers['cache-control']=='private, no-store'
        download=client.get(url+'/download',headers=h,params={'format':'png','revision':revision})
        assert download.status_code==200 and download.content==expected
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    denied=client.get(url+'/image',headers=other);assert denied.status_code==404
    unavailable=client.get(url+'/download',headers=h,params={'format':'docx'});assert unavailable.status_code==422
    archived=client.delete(url,headers=h);assert archived.status_code==200
    gone=client.get(url+'/image',headers=h);assert gone.status_code==404


def test_image_bytes_and_manifest_cannot_diverge_or_use_active_formats(client,db):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    receipt,_=persist(db,user,ident)
    row=db.query(AssistantMessage).filter_by(conversation_id=receipt['artifact_id'],tool=artifacts.VERSION_TOOL).one()
    row.result={'image_b64':base64.b64encode(b'<svg onload="alert(1)"/>').decode()};db.commit()
    rejected=client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}/image',headers=h)
    assert rejected.status_code in {409,422}
    content,manifest=pixels()
    with pytest.raises(HTTPException):artifact_images.validate(content,{**manifest,'sha256':'0'*64})
    with pytest.raises(HTTPException) as malformed:artifact_images.validate(content,{'mime_type':'image/png'})
    assert malformed.value.status_code==409
    with pytest.raises(ValueError):artifacts.Body(title='Active format',kind='image',image={**manifest,'mime_type':'image/svg+xml'})
    with pytest.raises(ValueError):artifacts.Body(title='Mixed data',kind='document',content='Text',image=manifest)
    with pytest.raises(ValueError):artifacts.Body(title='Mixed image',kind='image',image=manifest,rows=[['not pixels']])


def test_ordinary_artifact_writes_and_text_shares_cannot_publish_binary_manifests(client,db):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    content,manifest=pixels();body=artifacts.Body(title='Image',kind='image',image=manifest).model_dump()
    with pytest.raises(HTTPException) as blocked:artifacts.validate_step(db,user,None,'CRM',body)
    assert blocked.value.status_code==422
    wrong=internal_run(ident);wrong.plan['steps'][0]['tool']='crm.create_artifact'
    with pytest.raises(HTTPException) as blocked:artifacts.store_revision(db,user,wrong,'CRM',body,1,media_content=content)
    assert blocked.value.status_code==403
    receipt,_=persist(db,user,ident)
    from app.ai_operator.artifact_shares import bundle
    snapshot=bundle(db,user,receipt['artifact_id'],1)
    assert snapshot['root']['body']['image']['sha256']==manifest['sha256']
    assert 'image_b64' not in str(snapshot)  # Pixels require a separate reviewed publication copy.


def test_private_image_storage_budget_counts_retained_versions(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    receipt,content=persist(db,user,ident)
    monkeypatch.setattr(artifact_images,'MAX_STORED_BYTES',len(content))
    with pytest.raises(HTTPException) as blocked:persist(db,user,ident,'red',receipt)
    assert blocked.value.status_code==413
    db.rollback()
    archived=client.delete(ROOT+f'/artifacts/{receipt["artifact_id"]}',headers=h);assert archived.status_code==200
    with pytest.raises(HTTPException) as retained:artifact_images.quota(db,user,None,1)
    assert retained.value.status_code==413
