import base64
import pytest
from app.ai_operator import artifacts,artifact_shares as shares
from app.ai_operator.artifact_share_images import TOOL
from app.ai_operator.assistant_models import AssistantMessage
from app.shared.models import ServicePolicy
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_suite_workspace import chat
from tests.test_agent_library import member
from tests.test_artifact_shares import review,publish,S
from tests.test_artifact_images import persist
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def setup(client,db):
    owner,user,_,_=setup_suite(client,db);recipient,reader=member(client,db);outsider,_=member(client,db)
    ident=chat(client,owner);receipt,blue=persist(db,user,ident)
    return owner,user,recipient,reader,outsider,ident,receipt,blue


def test_image_publication_reviews_pixels_and_never_exposes_private_history(client,db):
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    draft=review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]})
    assert draft['pending']['image_positions']==['0'] and 'assets' not in draft['pending']
    assert 'image_b64' not in str(draft)
    url=S+f'/{draft["id"]}'
    unavailable=client.get(url+'/image',headers=recipient);assert unavailable.status_code==404
    denied=client.get(url+'/preview-image',headers=recipient,params={'preview_hash':draft['pending']['preview_hash']});assert denied.status_code==403
    preview=client.get(url+'/preview-image',headers=owner,params={'preview_hash':draft['pending']['preview_hash']})
    assert preview.status_code==200 and preview.content==blue
    share=publish(client,owner,draft)
    response=client.get(url+'/image',headers=recipient,params={'revision':share['revision']})
    assert response.status_code==200 and response.content==blue
    assert response.headers['cache-control']=='private, no-store' and response.headers['content-type']=='image/png'
    metadata=client.get(url+'/content',headers=recipient);assert metadata.status_code==200 and 'image_b64' not in metadata.text
    assert not {'source_id','conversation_id','security_context','assets'}&set(metadata.json()['item'])
    private=client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}/image',headers=recipient);assert private.status_code==404
    denied=client.get(url+'/image',headers=outsider);assert denied.status_code==404
    exported=client.get(url+'/download',headers=recipient,params={'revision':share['revision'],'format':'png'})
    assert exported.status_code==200 and exported.content==blue


def test_image_editions_and_audiences_change_only_after_exact_review(client,db):
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    first=publish(client,owner,review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]}))
    next_headers,next_user=member(client,db)
    second_receipt,red=persist(db,user,ident,'red',receipt)
    url=S+f'/{first["id"]}'
    current=client.get(url+'/image',headers=recipient);assert current.content==blue
    pending=review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[next_user.id]},
        source_revision=2,share_id=first['id'],revision=first['revision'])
    assert client.get(url+'/image',headers=recipient).content==blue
    assert client.get(url+'/image',headers=next_headers).status_code==404
    assert client.get(url+'/preview-image',headers=owner,params={'preview_hash':pending['pending']['preview_hash']}).content==red
    second=publish(client,owner,pending);assert second['revision']==2
    assert client.get(url+'/image',headers=recipient).status_code==404
    assert client.get(url+'/image',headers=next_headers).content==red
    assert client.get(url+'/image',headers=next_headers,params={'revision':1}).status_code==409
    revoked=client.post(url+'/revoke',headers=owner,json={'revision':2});assert revoked.status_code==200
    assert client.get(url+'/image',headers=next_headers).status_code==404
    assert client.get(url+'/download',headers=next_headers,params={'format':'png'}).status_code==404
    rows=db.query(AssistantMessage).filter_by(tool=TOOL).all()
    assert rows and all(row.status=='retired' and not row.result for row in rows)
    assert client.get(ROOT+f'/artifacts/{receipt["artifact_id"]}/image',headers=owner).content==red


def test_discarding_image_review_preserves_the_active_copy(client,db):
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    first=publish(client,owner,review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]}))
    persist(db,user,ident,'red',receipt)
    pending=review(client,owner,receipt['artifact_id'],{'kind':'organization'},source_revision=2,share_id=first['id'],revision=1)
    url=S+f'/{first["id"]}'
    discarded=client.post(url+'/discard',headers=owner,json={'preview_hash':pending['pending']['preview_hash']})
    assert discarded.status_code==200
    assert client.get(url+'/preview-image',headers=owner,params={'preview_hash':pending['pending']['preview_hash']}).status_code==409
    assert client.get(url+'/image',headers=recipient).content==blue
    rows=db.query(AssistantMessage).filter_by(tool=TOOL).all()
    assert sorted(row.status for row in rows)==['published','retired']
    assert all(row.result for row in rows if row.status=='published')
    assert all(not row.result for row in rows if row.status=='retired')


@pytest.mark.parametrize('tamper',['copy_bytes','private_message_reference'])
def test_publication_integrity_rejects_corrupt_pixels_and_private_message_refs(client,db,tamper):
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    share=publish(client,owner,review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]}))
    policy=db.get(ServicePolicy,share['id']);ref=policy.values_json['assets']['0']
    if tamper=='copy_bytes':
        row=db.get(AssistantMessage,ref['message_id']);row.result={'image_b64':base64.b64encode(b'not pixels').decode()};db.commit()
    else:
        private=db.query(AssistantMessage).filter_by(conversation_id=receipt['artifact_id'],tool=artifacts.VERSION_TOOL).one()
        policy.values_json={**policy.values_json,'assets':{'0':{**ref,'message_id':private.id}}};shares.sign(policy);db.commit()
    response=client.get(S+f'/{share["id"]}/image',headers=recipient)
    assert response.status_code in {404,409,422}


def test_source_archive_revokes_copied_image_and_purges_publication_bytes(client,db):
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    share=publish(client,owner,review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]}))
    assert client.delete(ROOT+f'/artifacts/{receipt["artifact_id"]}',headers=owner).status_code==200
    assert client.get(S+f'/{share["id"]}/image',headers=recipient).status_code==404
    row=db.query(AssistantMessage).filter_by(tool=TOOL).one();assert row.status=='retired' and not row.result


def test_corrupt_staged_copy_cannot_be_published(client,db):
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    draft=review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]})
    row=db.query(AssistantMessage).filter_by(tool=TOOL,status='staged').one();row.result={};db.commit()
    response=client.post(S+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':draft['pending']['preview_hash']})
    assert response.status_code==409
    assert client.get(S+f'/{draft["id"]}/image',headers=recipient).status_code==404


def test_image_dashboard_publication_embeds_exact_snapshot_in_office_and_pdf(client,db):
    import io
    import zipfile
    from pypdf import PdfReader
    from tests.test_bot_artifacts import command,execute
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    body={'title':'Illustrated status','kind':'dashboard','content':'Pinned illustration.',
        'panels':[{'artifact_id':receipt['artifact_id'],'revision':1,'display':'auto'}]}
    result=execute(client,db,owner,command(client,owner,'CRM','Prepare illustrated dashboard',local_plan={
        'summary':'Review the pinned image dashboard','steps':[{'tool':'crm.create_artifact','payload':body}]}))
    dashboard=result['receipts'][0]['artifact_id']
    share=publish(client,owner,review(client,owner,dashboard,{'kind':'members','member_ids':[reader.id]}))
    url=S+f'/{share["id"]}'
    image=client.get(url+'/image',headers=recipient,params={'revision':1,'position':1});assert image.content==blue
    panel=client.get(url+'/panels/1',headers=recipient);assert panel.status_code==200 and panel.json()['item']['kind']=='image'
    download=client.get(url+'/download',headers=recipient,params={'format':'png','position':1,'revision':1})
    assert download.status_code==200 and download.content==blue
    # Editing the private original must not change exported publication pixels.
    persist(db,user,ident,'red',receipt)
    for fmt in ('docx','pdf','xlsx'):
        exported=client.get(url+'/download',headers=recipient,params={'format':fmt,'revision':1})
        assert exported.status_code==200,fmt
        if fmt=='pdf':
            images=[image.image.convert('RGBA') for page in PdfReader(io.BytesIO(exported.content)).pages for image in page.images]
            assert len(images)==1 and images[0].getpixel((0,0))==(0,0,255,255)
        else:
            with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                names=[name for name in archive.namelist() if '/media/' in name]
                assert len(names)==1 and archive.read(names[0])==blue
    assert client.post(url+'/revoke',headers=owner,json={'revision':1}).status_code==200
    for fmt in ('docx','pdf','xlsx'):
        assert client.get(url+'/download',headers=recipient,params={'format':fmt,'revision':1}).status_code==404


def test_image_publication_storage_limit_and_discard_cleanup(client,db,monkeypatch):
    from app.ai_operator import artifact_share_images as copies
    owner,user,recipient,reader,outsider,ident,receipt,blue=setup(client,db)
    monkeypatch.setattr(copies,'MAX_OWNER_BYTES',len(blue))
    first=review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]})
    rejected=client.post(S+'/preview',headers=owner,json={'request_key':str(__import__('uuid').uuid4()),
        'source_id':receipt['artifact_id'],'source_revision':1,'audience':{'kind':'organization'}})
    assert rejected.status_code==413
    discarded=client.post(S+f'/{first["id"]}/discard',headers=owner,json={'preview_hash':first['pending']['preview_hash']})
    assert discarded.status_code==200
    retry=review(client,owner,receipt['artifact_id'],{'kind':'members','member_ids':[reader.id]})
    assert retry['pending']['image_positions']==['0']
