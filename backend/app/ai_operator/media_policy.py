"""Explicit media grants on existing scoped provider configuration.

This policy resolves server-only snapshots. It does not approve or execute a
media action; reviewed tools must bind the returned fingerprint to their input.
"""
import hashlib
import json
from types import SimpleNamespace
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,StrictBool


class MediaSettings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    image_enabled:StrictBool=False
    image_model:Literal['gemini-3.1-flash-image','gemini-3.1-flash-lite-image','gemini-3-pro-image']='gemini-3.1-flash-image'
    transcription_enabled:StrictBool=False
    transcription_model:Literal['gemini-3.5-flash-lite']='gemini-3.5-flash-lite'


def settings(config):
    try:return MediaSettings.model_validate(getattr(config,'media_settings',None) or {})
    except (ValueError,TypeError):raise HTTPException(409,'MEDIA_CONFIGURATION_INVALID') from None


def resolve_media(db,user,capability,workspace_id=None):
    from app.ai_operator.provider_scope import resolve_provider
    config=resolve_provider(db,user,'gemini',workspace_id)
    if not config or not config.enabled or not config.data_sharing_allowed:
        raise HTTPException(409,'MEDIA_PROVIDER_UNAVAILABLE')
    policy=settings(config)
    if capability=='image':enabled=policy.image_enabled;model=policy.image_model
    elif capability=='transcription':enabled=policy.transcription_enabled;model=policy.transcription_model
    else:raise HTTPException(422,'MEDIA_UNSUPPORTED_CAPABILITY')
    if not enabled:raise HTTPException(409,'MEDIA_CAPABILITY_DISABLED')
    from app.ai_operator.prompt_registry import render
    from app.ai_operator.gemini_media import Transcript
    manifests=[render('media_transcription',Transcript.model_json_schema())[1],render('media_image',{'mime_type':'image/png','images':1})[1]]
    scope=f'workspace:{workspace_id}' if workspace_id else config.scope_key
    fingerprint=hashlib.sha256(json.dumps({'scope':scope,'configuration_scope':config.scope_key,'provider':'gemini',
        'media':policy.model_dump(),'updated_at':str(config.updated_at),'max_tokens':config.max_tokens,
        'core_prompts':[{key:value[key] for key in ('key','version','instruction_sha256','schema_sha256')} for value in manifests],
        'key_epoch':hashlib.sha256(config.encrypted_key.encode()).hexdigest()},sort_keys=True).encode()).hexdigest()
    return SimpleNamespace(provider='gemini',model=model,enabled=True,data_sharing_allowed=True,
        encrypted_key=config.encrypted_key,max_tokens=config.max_tokens,scope_key=scope,configuration_scope=config.scope_key,
        media_policy_sha256=fingerprint,input_price=None,output_price=None)
