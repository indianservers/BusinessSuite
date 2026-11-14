"""Reviewed pixel copies in a publication-only assistant-storage namespace.

Readers never query a publisher's private artifact versions. A signed policy
references these explicit publication copies, with audience checks performed by
artifact_shares before the narrow asset reader is called.
"""
import base64
import hashlib
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,func,update,text
from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
from app.ai_operator import artifacts
from app.ai_operator.artifact_images import validate,bytes_from_version

TOOL='suite.artifact.share.image'
MAX_PUBLICATION_BYTES=8_000_000
MAX_PUBLICATION_PIXELS=24_000_000
MAX_OWNER_BYTES=32_000_000


def positions(definition):
    return {str(index):source for index,source in enumerate([definition['root'],*definition['sources']]) if source['body']['kind']=='image'}


def stage(db,user,row,definition,edition):
    sources=positions(definition)
    if not sources:return {}
    manifests={source['body']['image']['sha256']:source['body']['image'] for source in sources.values()}
    if sum(value['size'] for value in manifests.values())>MAX_PUBLICATION_BYTES:raise HTTPException(413,'Image publication exceeds 8 MB; split its image panels')
    if sum(value['width']*value['height'] for value in manifests.values())>MAX_PUBLICATION_PIXELS:raise HTTPException(413,'Image publication exceeds its pixel budget; split its image panels')
    unique={};copies={}
    for position,source in sources.items():
        original=artifacts.owned(db,user,source['source_id'])
        content=bytes_from_version(artifacts.version(db,user,original,source['source_revision']))
        manifest=source['body']['image'];validate(content,manifest)
        unique.setdefault(manifest['sha256'],(content,manifest));copies[position]=manifest['sha256']
    incoming=sum(len(content) for content,_ in unique.values())
    if incoming>MAX_PUBLICATION_BYTES:raise HTTPException(413,'Image publication exceeds 8 MB; split its image panels')
    lock_key=int.from_bytes(hashlib.sha256(f'artifact-publication-images:{row.organization_id}:{user.id}:{definition["workspace_id"]}'.encode()).digest()[:8],'big')&((1<<63)-1)
    # A separate transaction lock avoids reversing private artifact/user row
    # lock order while serializing quota checks across independent shares.
    db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':lock_key})
    messages=AssistantMessage.__table__;conversations=AssistantConversation.__table__
    used=db.connection().execute(select(func.coalesce(func.sum(messages.c.arguments['size'].as_integer()),0)).select_from(
        messages.join(conversations,messages.c.conversation_id==conversations.c.id)).where(
        conversations.c.user_id==user.id,conversations.c.organization_id==row.organization_id,
        conversations.c.workspace_id==definition['workspace_id'],messages.c.tool==TOOL,messages.c.status.in_(['staged','published']))).scalar()
    if int(used)+incoming>MAX_OWNER_BYTES:raise HTTPException(413,'Active and pending image publications exceed 32 MB in this workspace; revoke or discard an unused share')
    container=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=row.organization_id,
        workspace_id=definition['workspace_id'],deleted_at=None).filter(
        AssistantConversation.references['artifact_publication_assets'].as_boolean()==True,
        AssistantConversation.references['share_id'].as_integer()==row.id).first()
    if not container:
        container=AssistantConversation(user_id=user.id,organization_id=row.organization_id,workspace_id=definition['workspace_id'],
            title='Reviewed artifact publication assets',references={'artifact_publication_assets':True,'share_id':row.id})
        db.add(container);db.flush()
    refs={}
    for sha,(content,manifest) in unique.items():
        message=AssistantMessage(conversation_id=container.id,request_key=uuid4().hex,request_hash=sha,
            prompt='Explicitly reviewed publication image copy',tool=TOOL,status='staged',
            arguments={'share_id':row.id,'edition':edition,**manifest},result={'image_b64':base64.b64encode(content).decode('ascii')})
        db.add(message);db.flush();refs[sha]={'message_id':message.id,**manifest}
    return {position:refs[sha] for position,sha in copies.items()}


def load(db,row,definition,assets,edition,position=0,*,staged=False):
    """Only exact signed publication refs; no private source-history queries."""
    source=positions(definition).get(str(position));reference=assets.get(str(position))
    if not source or not reference:raise HTTPException(404,'Published image not found')
    manifest=source['body']['image']
    if {key:reference.get(key) for key in manifest}!=manifest:raise HTTPException(409,'Published image manifest changed')
    messages=AssistantMessage.__table__;conversations=AssistantConversation.__table__
    value=db.connection().execute(select(messages.c.result,messages.c.arguments).select_from(
        messages.join(conversations,messages.c.conversation_id==conversations.c.id)).where(
        messages.c.id==reference['message_id'],messages.c.tool==TOOL,
        messages.c.status==('staged' if staged else 'published'),messages.c.arguments['share_id'].as_integer()==row.id,
        messages.c.arguments['edition'].as_integer()==edition,conversations.c.user_id==row.values_json['source_owner'],
        conversations.c.organization_id==row.organization_id,conversations.c.workspace_id==row.values_json['workspace_id'],
        conversations.c.deleted_at.is_(None),conversations.c.references['artifact_publication_assets'].as_boolean()==True,
        conversations.c.references['share_id'].as_integer()==row.id)).first()
    if not value:raise HTTPException(404,'Published image bytes unavailable')
    if {key:value.arguments.get(key) for key in manifest}!=manifest:raise HTTPException(409,'Published image integrity changed')
    try:content=base64.b64decode(value.result['image_b64'],validate=True)
    except (ValueError,KeyError,TypeError):raise HTTPException(409,'Published image bytes invalid') from None
    return validate(content,manifest)


def transition(db,row,assets,status):
    ids={ref['message_id'] for ref in assets.values()}
    if not ids:return
    messages=AssistantMessage.__table__;conversations=AssistantConversation.__table__
    parents=select(conversations.c.id).where(conversations.c.user_id==row.values_json['source_owner'],
        conversations.c.organization_id==row.organization_id,conversations.c.references['artifact_publication_assets'].as_boolean()==True,
        conversations.c.references['share_id'].as_integer()==row.id)
    values={'status':status}
    if status=='retired':values['result']={}
    db.connection().execute(update(messages).where(messages.c.id.in_(ids),messages.c.conversation_id.in_(parents),
        messages.c.tool==TOOL,messages.c.arguments['share_id'].as_integer()==row.id).values(**values))
