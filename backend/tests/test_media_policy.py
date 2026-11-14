"""Scoped media configuration does not authorize model or business execution."""
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.ai_operator import media_policy
from app.ai_operator.models import OperatorProvider
from tests.test_ai_operator import setup_operator,isolate_generic_http_audit
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator'


def test_media_defaults_off_and_explicit_settings_preserve_text_model_and_key(client,db):
    headers,user,_,_=setup_operator(client,db,provider='gemini')
    config=db.query(OperatorProvider).filter_by(provider='gemini').one()
    key=config.encrypted_key
    defaults=client.get(ROOT+'/providers',headers=headers).json()['items'][0]
    assert not defaults['media']['image_enabled'] and not defaults['media']['transcription_enabled']
    payload={'model':'text-model','enabled':True,'data_sharing_allowed':True,
        'media':{'image_enabled':True,'transcription_enabled':True}}
    response=client.put(ROOT+'/providers/gemini',headers=headers,json=payload)
    assert response.status_code==200
    assert response.json()['model']=='text-model' and response.json()['media']['image_enabled']
    assert 'encrypted_key' not in response.text and 'unit-test-secret-key' not in response.text
    db.refresh(config);assert config.encrypted_key==key
    image=media_policy.resolve_media(db,user,'image')
    audio=media_policy.resolve_media(db,user,'transcription')
    assert image.model=='gemini-3.1-flash-image' and audio.model=='gemini-3.5-flash-lite'
    assert image.input_price is None and image.output_price is None
    assert len(image.media_policy_sha256)==64 and image.media_policy_sha256==audio.media_policy_sha256
    # An old client saving text settings must not silently revoke media grants.
    payload.pop('media');response=client.put(ROOT+'/providers/gemini',headers=headers,json=payload)
    assert response.status_code==200 and response.json()['media']['transcription_enabled']
    # An explicit reset does revoke both grants.
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={**payload,'media':None})
    assert response.status_code==200 and not response.json()['media']['image_enabled']
    with pytest.raises(HTTPException) as caught:media_policy.resolve_media(db,user,'image')
    assert caught.value.detail=='MEDIA_CAPABILITY_DISABLED'


@pytest.mark.parametrize('media',[{'image_model':'arbitrary-model'}, {'image_enabled':'true'},
    {'transcription_model':'https://attacker.invalid'}, {'transcription_enabled':True,'unknown':True}])
def test_unknown_models_or_ambiguous_grants_are_rejected(client,db,media):
    headers,_,_,_=setup_operator(client,db,provider='gemini')
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={'model':'text-model','media':media})
    assert response.status_code==422


def test_media_requires_admin_gemini_and_existing_provider_sharing(client,db):
    headers,user,_,_=setup_operator(client,db,provider='gemini')
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    payload={'model':'text-model','enabled':True,'data_sharing_allowed':True,'media':{'image_enabled':True}}
    denied=client.put(ROOT+'/providers/gemini',headers=other,json=payload)
    assert denied.status_code==403
    wrong=client.put(ROOT+'/providers/openai',headers=headers,json=payload)
    assert wrong.status_code==422
    response=client.put(ROOT+'/providers/gemini',headers=headers,json={**payload,'data_sharing_allowed':False})
    assert response.status_code==200
    with pytest.raises(HTTPException) as caught:media_policy.resolve_media(db,user,'image')
    assert caught.value.detail=='MEDIA_PROVIDER_UNAVAILABLE'


def test_media_resolution_uses_existing_scope_and_blocks_invalid_configuration(monkeypatch):
    from app.ai_operator import provider_scope
    config=SimpleNamespace(scope_key='workspace:4',enabled=True,data_sharing_allowed=True,
        encrypted_key='synthetic',updated_at='version-1',max_tokens=2048,media_settings={'image_enabled':True})
    requests=[]
    def resolve(db,user,provider,workspace_id):
        requests.append((db,user,provider,workspace_id));return config
    monkeypatch.setattr(provider_scope,'resolve_provider',resolve)
    first=media_policy.resolve_media('db','actor','image',4)
    assert requests==[('db','actor','gemini',4)]
    config.media_settings={'image_enabled':True,'transcription_enabled':True}
    assert media_policy.resolve_media('db','actor','image',4).media_policy_sha256!=first.media_policy_sha256
    config.media_settings={'image_enabled':'yes'}
    with pytest.raises(HTTPException) as caught:media_policy.resolve_media('db','actor','image',4)
    assert caught.value.detail=='MEDIA_CONFIGURATION_INVALID'


def test_media_review_fingerprint_changes_when_core_prompt_version_changes(monkeypatch):
    from app.ai_operator import provider_scope,prompt_registry
    config=SimpleNamespace(scope_key='company:1',enabled=True,data_sharing_allowed=True,encrypted_key='synthetic',
        updated_at='version-1',max_tokens=2048,media_settings={'image_enabled':True})
    monkeypatch.setattr(provider_scope,'resolve_provider',lambda *args:config)
    original=media_policy.resolve_media('db','actor','image').media_policy_sha256
    render=prompt_registry.render
    def revised(purpose,schema):
        text,manifest=render(purpose,schema)
        return text,{**manifest,'version':manifest['version']+1}
    monkeypatch.setattr(prompt_registry,'render',revised)
    assert media_policy.resolve_media('db','actor','image').media_policy_sha256!=original


def test_media_migration_preserves_credentials_and_defaults_disabled(client,db):
    import runpy
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    headers,_,_,_=setup_operator(client,db,provider='gemini')
    config=db.query(OperatorProvider).filter_by(provider='gemini').one()
    old=(config.id,config.model,config.encrypted_key)
    connection=db.connection()
    connection.execute(sa.text('ALTER TABLE ai_operator_providers DROP COLUMN media_settings'))
    migration=runpy.run_path(str(Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261114_099_media_capabilities.py'))
    with Operations.context(MigrationContext.configure(connection)):
        migration['upgrade']();migration['upgrade']()
    record=connection.execute(sa.text('SELECT id,model,encrypted_key,media_settings FROM ai_operator_providers WHERE id=:id'),{'id':old[0]}).one()
    assert tuple(record[:3])==old and record[3]=={}
    db.expire_all()
    response=client.get(ROOT+'/providers',headers=headers)
    assert response.status_code==200 and not response.json()['items'][0]['media']['image_enabled']


def test_inherited_media_grants_are_workspace_bound_and_disabled_override_blocks(client,db):
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
    headers,user,_,_=setup_operator(client,db,provider='gemini')
    source=db.query(OperatorProvider).filter_by(provider='gemini').one()
    source.allow_workspace_inheritance=True;source.media_settings={'image_enabled':True}
    ids=[]
    for name in ['Media workspace A','Media workspace B']:
        workspace=PMSWorkspace(name=name);db.add(workspace);db.flush()
        db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Owner'));db.commit()
        workspace.organization_id=None;db.commit();ids.append(workspace.id)
    first=media_policy.resolve_media(db,user,'image',ids[0]);second=media_policy.resolve_media(db,user,'image',ids[1])
    assert first.scope_key==f'workspace:{ids[0]}' and first.configuration_scope==source.scope_key
    assert first.media_policy_sha256!=second.media_policy_sha256
    override=OperatorProvider(scope_key=first.scope_key,provider='gemini',model='text-override',encrypted_key='unused',
        enabled=False,data_sharing_allowed=False,media_settings={'image_enabled':True},updated_by=user.id)
    db.add(override);db.commit()
    with pytest.raises(HTTPException) as caught:media_policy.resolve_media(db,user,'image',ids[0])
    assert caught.value.detail=='MEDIA_PROVIDER_UNAVAILABLE'
