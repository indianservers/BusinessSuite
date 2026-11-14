import pytest
from app.ai_operator import gemini_media
from tests.test_image_actions import setup,finish
from tests.test_artifact_templates import preview,confirm,T
from tests.test_artifact_images import persist,pixels,internal_run
from app.ai_operator import artifacts
from tests.test_suite_workspace import say,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def definition():
    return {'kind':'image_instruction','title':'{{customer}} banner','content':'A {{color}} delivery van for {{customer}}. No text.',
        'aspect_ratio':'16:9'}


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_image_template_followups_and_reviewed_generation(client,db,monkeypatch,module):
    h,user,chat,calls=setup(client,db,monkeypatch)
    # Persist a private synthetic artifact; saving an instruction template
    # neither reads its pixels nor causes model inference.
    content,manifest=pixels();source_run=internal_run(chat)
    source_run.plan['steps'][0]['tool']=f'{module.lower()}.generate_image'
    receipt=artifacts.store_revision(db,user,source_run,module,artifacts.Body(title='Synthetic source image',kind='image',image=manifest).model_dump(),1,media_content=content)
    review,_=preview(client,h,source_artifact_id=receipt['artifact_id'],source_revision=1,body=definition(),name='Delivery image instructions')
    assert not calls and 'image_b64' not in str(review)
    template=confirm(client,h,review)
    first=say(client,h,chat,f'Use template #{template["id"]}',module=module)
    assert first['status']=='needs_clarification' and 'customer' in first['plan']['question']
    second=say(client,h,chat,'Synthetic client',module=module)
    assert second['status']=='needs_clarification' and 'color' in second['plan']['question']
    draft=say(client,h,chat,'blue',module=module)
    assert draft['status']=='awaiting_approval' and not calls
    step=draft['plan']['steps'][0];assert step['tool']==f'{module.lower()}.generate_image'
    assert step['payload']['references']==[] and step['payload']['aspect_ratio']=='16:9'
    changed=say(client,h,chat,'color=red',module=module)
    assert changed['status']=='awaiting_approval' and 'red delivery' in changed['plan']['steps'][0]['payload']['prompt'] and not calls
    result=finish(client,db,h,changed);assert len(calls)==1
    artifact=client.get(ROOT+f'/artifacts/{result["receipts"][0]["artifact_id"]}',headers=h).json()
    assert artifact['provenance']['template']['id']==template['id']


def test_image_template_archive_blocks_pending_generation(client,db,monkeypatch):
    h,user,chat,calls=setup(client,db,monkeypatch);receipt,_=persist(db,user,chat)
    review,_=preview(client,h,source_artifact_id=receipt['artifact_id'],source_revision=1,body=definition())
    template=confirm(client,h,review)
    draft=say(client,h,chat,f'Use template #{template["id"]}: customer=Synthetic; color=blue',module='CRM')
    assert draft['status']=='awaiting_approval' and not calls
    assert client.delete(T+f'/{template["id"]}',headers=h).status_code==200
    denied=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert denied.status_code==404 and not calls


def test_image_template_never_grants_provider_permissions(client,db,monkeypatch):
    from app.ai_operator.models import OperatorProvider
    h,user,chat,calls=setup(client,db,monkeypatch);receipt,_=persist(db,user,chat)
    review,_=preview(client,h,source_artifact_id=receipt['artifact_id'],source_revision=1,body=definition())
    template=confirm(client,h,review)
    draft=say(client,h,chat,f'Use template #{template["id"]}: customer=Synthetic; color=blue',module='CRM')
    assert draft['status']=='awaiting_approval'
    provider=db.query(OperatorProvider).filter_by(provider='gemini').one();provider.media_settings={'image_enabled':False};db.commit()
    denied=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert denied.status_code in {403,409,422} and not calls
