"""Inert image manifests and private version-bound binary storage."""
import base64
import hashlib
from fastapi import HTTPException
from pydantic import Field,StrictInt
from app.ai_operator.suite_tools import Strict

MAX_STORED_BYTES=32_000_000


class ImageManifest(Strict):
    mime_type:str=Field(pattern=r'^image/png$')
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    width:StrictInt=Field(ge=1,le=4096)
    height:StrictInt=Field(ge=1,le=4096)
    size:StrictInt=Field(ge=1,le=8_000_000)


def validate(content,manifest,*,require_clean=False):
    from app.ai_operator.gemini_media import image_bytes
    try:declared=ImageManifest.model_validate(manifest)
    except (ValueError,TypeError):raise HTTPException(409,'Image artifact manifest is invalid') from None
    clean,width,height=image_bytes(content,'image/png')
    if (require_clean and clean!=content) or (width,height)!=(declared.width,declared.height) or len(content)!=declared.size or hashlib.sha256(content).hexdigest()!=declared.sha256:
        raise HTTPException(409,'Image artifact integrity changed')
    return content


def quota(db,user,workspace_id,incoming):
    from sqlalchemy import func
    from app.ai_operator.assistant_models import AssistantMessage,AssistantConversation
    from app.ai_operator.artifacts import VERSION_TOOL
    from app.ai_agents.security import company
    # Retained archived versions count too: deleting metadata does not evade the
    # binary retention budget. Existing version and artifact count limits apply.
    size=AssistantMessage.arguments['body']['image']['size'].as_integer()
    used=db.query(func.coalesce(func.sum(size),0)).join(AssistantConversation,AssistantMessage.conversation_id==AssistantConversation.id).filter(
        AssistantConversation.user_id==user.id,AssistantConversation.organization_id==company(user),
        AssistantConversation.workspace_id==workspace_id,AssistantMessage.tool==VERSION_TOOL,AssistantMessage.status=='stored').scalar()
    if int(used)+incoming>MAX_STORED_BYTES:raise HTTPException(413,'Private image version storage exceeds 32 MB in this workspace')


def bytes_from_version(message):
    body=message.arguments.get('body') or {}
    if body.get('kind')!='image' or not body.get('image'):raise HTTPException(422,'Select an image artifact version')
    try:content=base64.b64decode((message.result or {})['image_b64'],validate=True)
    except (ValueError,KeyError,TypeError):raise HTTPException(409,'Image artifact bytes are unavailable') from None
    return validate(content,body['image'])
