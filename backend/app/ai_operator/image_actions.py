"""Reviewed local import and Gemini image edits on existing artifact storage."""
import base64
import hashlib
import re
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_current_user,get_db
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest

router=APIRouter(prefix='/suite/media',tags=['Reviewed media'])
JOURNAL='suite.media.image'


class Reference(Strict):
    attachment_id:int=Field(gt=0)
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class ImportImage(Reference):
    title:str=Field(min_length=1,max_length=160)
    conversation_id:int=Field(gt=0)


class ImportApproved(ImportImage):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


class Generate(Strict):
    title:str=Field(min_length=1,max_length=160)
    prompt:str=Field(min_length=1,max_length=3000)
    conversation_id:int=Field(gt=0)
    model:str=Field(min_length=1,max_length=120)
    media_policy_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    aspect_ratio:Literal['1:1','16:9','9:16','4:3','3:4']='1:1'
    references:list[Reference]=Field(default_factory=list,max_length=3)

    @model_validator(mode='after')
    def bounded(self):
        if not self.prompt.strip() or not self.title.strip():raise ValueError('Use a nonempty title and image instruction')
        if len({v.attachment_id for v in self.references})!=len(self.references):raise ValueError('Use each image reference once')
        return self


class Edit(Generate):
    artifact_id:int=Field(gt=0)
    expected_revision:int=Field(ge=1,le=99)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class GenerateApproved(Generate):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


class EditApproved(Edit):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


def schema(step):return Edit if step.tool.endswith('.edit_image') else Generate


def bind_proposal(db,user,run,step):
    """Seal model-authored image proposals before hashing/displaying the plan.

    Source IDs and instructions stay explicit. Configuration nonces and source
    hashes come from authorized server state, never from model imagination.
    Approval and execution only validate the sealed payload; they never rebind.
    """
    from app.ai_operator import artifacts,suite_uploads as uploads
    from app.ai_operator.media_policy import resolve_media
    if not run:raise HTTPException(422,'Image actions require a stored review context')
    values=dict(step.payload);conversation=(run.result or {}).get('request',{}).get('conversation_id')
    if not conversation:raise HTTPException(422,'Image actions require a private conversation')
    if values.get('conversation_id') not in (None,conversation):raise HTTPException(403,'Image action selected another conversation')
    config=resolve_media(db,user,'image',run.workspace_id)
    values.update(conversation_id=conversation,model=config.model,media_policy_sha256=config.media_policy_sha256)
    proposed_references=values.get('references',[])
    if not isinstance(proposed_references,list) or len(proposed_references)>3:raise HTTPException(422,'Choose up to three image references')
    references=[]
    for value in proposed_references:
        if not isinstance(value,dict) or set(value)-{'attachment_id','sha256'} or type(value.get('attachment_id')) is not int:
            raise HTTPException(422,'Choose explicit image attachment IDs')
        row=uploads.owned(db,user,conversation,value['attachment_id'])
        if value.get('sha256') not in (None,row.arguments['sha256']):raise HTTPException(409,'Image reference changed; prepare a fresh review')
        references.append({'attachment_id':row.id,'sha256':row.arguments['sha256']})
    values['references']=references
    if step.tool.endswith('.edit_image'):
        if type(values.get('artifact_id')) is not int:raise HTTPException(422,'Choose an existing image artifact ID')
        row=artifacts.owned(db,user,values['artifact_id']);current=artifacts.public(db,user,row)
        if current['kind']!='image':raise HTTPException(422,'Choose an image artifact')
        if values.get('expected_revision') not in (None,current['revision']) or values.get('source_sha256') not in (None,current['image']['sha256']):
            raise HTTPException(409,'Image source changed; prepare a fresh review')
        values.update(expected_revision=current['revision'],source_sha256=current['image']['sha256'])
    try:step.payload=schema(step).model_validate(values).model_dump()
    except ValueError:raise HTTPException(422,'Image action proposal is incomplete or invalid') from None


def confirmed(db,user,run,step):
    """Find this exact step's committed image if its outer receipt was lost."""
    from app.ai_operator.assistant_models import AssistantMessage,AssistantConversation
    from app.ai_agents.security import company,verify
    from app.ai_operator import artifacts
    if not run.plan:return None
    index=run.active_step or len(run.receipts or [])+1
    if not 1<=index<=len(run.plan['steps']):return None
    candidate=run.plan['steps'][index-1]
    if candidate['tool']!=step.tool or digest(candidate.get('payload',{}))!=digest(step.payload):return None
    key=digest({'run':run.id,'step':index})
    msg=db.query(AssistantMessage).join(AssistantConversation,AssistantMessage.conversation_id==AssistantConversation.id).filter(
        AssistantConversation.user_id==user.id,AssistantConversation.organization_id==company(user),
        AssistantMessage.tool==artifacts.VERSION_TOOL,AssistantMessage.request_key==key).first()
    if not msg:return None
    row=artifacts.owned(db,user,msg.conversation_id);verify(db,user,msg.security_context,history=True)
    provenance=msg.arguments.get('provenance') or {}
    if provenance.get('suite_run_id')!=run.id or provenance.get('plan_hash')!=run.plan_hash or msg.arguments['body']['kind']!='image':
        raise HTTPException(409,'Confirmed image provenance changed')
    return {'artifact_id':row.id,'artifact_revision':msg.arguments['revision']}


def preflight(db,user,run,step):
    if step.tool.endswith('.import_image'):return import_source(db,user,run,step)
    from app.ai_operator import artifacts,suite_uploads as uploads,suite_conversations as chats,gemini_media
    from app.ai_operator.artifact_images import bytes_from_version
    from app.ai_operator.media_policy import resolve_media
    data=schema(step).model_validate(step.payload);module=step.tool.split('.')[0].upper()
    if not run or (run.result or {}).get('request',{}).get('conversation_id')!=data.conversation_id:
        raise HTTPException(403,'Image processing must retain its original conversation')
    chat=chats.owned(db,user,data.conversation_id)
    if chat.workspace_id!=run.workspace_id:raise HTTPException(403,'Image conversation is outside this workspace')
    artifacts.access(db,user,run.workspace_id,module,(run.result or {}).get('request',{}).get('project_id') if module=='PMS' else None)
    config=resolve_media(db,user,'image',run.workspace_id)
    if data.model!=config.model or data.media_policy_sha256!=config.media_policy_sha256:
        raise HTTPException(409,'Image provider configuration changed; prepare a fresh review')
    try:artifacts.Body(title=data.title,content=data.prompt)
    except ValueError:raise HTTPException(422,'Use valid plain text for the image title and instruction') from None
    references=[];citations=[]
    if isinstance(data,Edit):
        row=artifacts.owned(db,user,data.artifact_id)
        if row.workspace_id!=run.workspace_id or row.references['module']!=module:raise HTTPException(403,'Edit the image in its original module/workspace')
        committed=confirmed(db,user,run,step)
        own_revision=committed and committed['artifact_id']==row.id and committed['artifact_revision']==data.expected_revision+1
        if row.references['kind']!='image' or row.references['revision']!=data.expected_revision and not own_revision:raise HTTPException(409,'Image version changed; prepare a fresh review')
        msg=artifacts.version(db,user,row,data.expected_revision);content=bytes_from_version(msg)
        if hashlib.sha256(content).hexdigest()!=data.source_sha256:raise HTTPException(409,'Image source changed since review')
        references.append((content,'image/png'))
        citations.append({'id':f'artifact:{row.id}:v{data.expected_revision}','label':f'{row.title} / version {data.expected_revision}',
            'href':f'#bot-artifact-{row.id}'})
    for ref in data.references:
        row=uploads.owned(db,user,data.conversation_id,ref.attachment_id);media=row.arguments.get('media') or {}
        if media.get('kind')!='image' or row.arguments.get('sha256')!=ref.sha256:raise HTTPException(409,'Select unchanged, validated private image references')
        try:content=base64.b64decode(row.result['content_b64'],validate=True)
        except (ValueError,TypeError,KeyError):raise HTTPException(409,'Image reference unavailable') from None
        if hashlib.sha256(content).hexdigest()!=ref.sha256:raise HTTPException(409,'Image reference integrity changed')
        content,_,_=gemini_media.image_bytes(content,media['mime_type']);references.append((content,'image/png'))
        citations.append({'id':f'upload:{row.id}','label':row.arguments['name'],
            'href':f'/api/v1/ai-operator/suite/conversations/{data.conversation_id}/attachments/{row.id}/download'})
    if len(references)>3 or any(len(v)>gemini_media.MAX_INPUT for v,_ in references) or sum(len(v) for v,_ in references)>8_000_000:
        raise HTTPException(413,'Use at most three image references, up to 5 MB each and 8 MB combined after metadata removal')
    return config,references,citations


def prompt(data):
    from app.ai_operator.prompt_registry import render
    instruction,manifest=render('media_image',{'mime_type':'image/png','images':1})
    return instruction+'\nRequested image:\n'+data.prompt,manifest


def local_plan(db,user,data,parent=None):
    from app.ai_operator import artifacts,suite_uploads as uploads
    from app.ai_operator.suite import Plan,Step
    from app.ai_operator.media_policy import resolve_media
    text=data.text.strip();prefix=re.match(r'^(CRM|PMS|HRMS)\s*:\s*',text,re.I)
    explicit_module=prefix[1].upper() if prefix else None
    if prefix:text=text[prefix.end():].strip()
    imported=re.fullmatch(r'(?:save|import)\s+(?:the\s+)?image\s+(?:file\s*)?#?([1-9]\d{0,9})(?:\s+as\s+(?:an?\s+)?artifact)?(?:\s+called\s+(.+))?[.! ]*',text,re.I|re.S)
    if imported:
        if explicit_module:data.module=explicit_module
        if data.module not in {'CRM','PMS','HRMS'} or not data.conversation_id:return Plan(summary='Choose a private image destination.',question='Select CRM, PMS or HRMS and upload the image in this conversation.',steps=[])
        row=uploads.owned(db,user,data.conversation_id,int(imported[1]))
        if (row.arguments.get('media') or {}).get('kind')!='image':raise HTTPException(422,'Choose a validated image file')
        try:payload=ImportImage(title=(imported[2] or row.arguments['name']).strip(),conversation_id=data.conversation_id,attachment_id=row.id,sha256=row.arguments['sha256'])
        except ValueError:raise HTTPException(422,'Use an image artifact title up to 160 characters') from None
        return Plan(summary='Review saving this uploaded image as a private, versioned PNG artifact. Orientation is preserved and metadata removed. No image model will be called; sharing requires a separate review.',
            steps=[Step(tool=f'{data.module.lower()}.import_image',payload=payload.model_dump())])
    if re.match(r'(?i)^edit\s+(?:the\s+)?image\s+from\s+files?\b',text):text=re.sub(r'(?i)^edit\s+(?:the\s+)?image','Create image',text)
    create=re.fullmatch(r'(?:please\s+)?(?:create|generate|draw)\s+(?:an?\s+)?image(?:\s+from\s+files?\s+#?([\d,# ]+))?(?:\s+called\s+([^:]+))?\s*:\s*(.+)',text,re.I|re.S)
    natural=re.fullmatch(r'(?:please\s+)?(?:create|generate|draw)\s+(?:an?\s+)?image\s+(?:of|showing)\s+(.+)',text,re.I|re.S)
    edit=re.fullmatch(r'(?:please\s+)?(?:edit|change|update)\s+(?:the\s+)?(?:image|artifact)\s*#?([1-9]\d{0,9})\s*:\s*(.*)',text,re.I|re.S)
    implicit=re.fullmatch(r'(?:edit|change|update)\s+(?:(?:this|the)\s+)?image\s*:\s*(.+)',text,re.I|re.S)
    target=None;pending=None;instruction=None;title='Generated image';refs=[];ratio='1:1'
    if edit:
        target=artifacts.owned(db,user,int(edit[1]))
        if target.references['kind']!='image':return None
        instruction=edit[2].strip()
    elif create or natural:
        instruction=create[3].strip() if create else natural[1].strip()
        title=(create[2] or title).strip().strip('"\'') if create else title
        if create and create[1]:
            ids=re.findall(r'[1-9]\d*',create[1])
            if not ids or len(ids)>3 or len(set(ids))!=len(ids):raise HTTPException(422,'Choose up to three distinct image file IDs')
            for ident in ids:
                row=uploads.owned(db,user,data.conversation_id,int(ident))
                if (row.arguments.get('media') or {}).get('kind')!='image':raise HTTPException(422,'Choose image references, not audio or documents')
                refs.append(Reference(attachment_id=row.id,sha256=row.arguments['sha256']))
    elif implicit:
        candidates=[]
        for receipt in (parent.receipts or []) if parent else []:
            if receipt.get('artifact_id'):
                row=artifacts.owned(db,user,receipt['artifact_id'])
                if row.references['kind']=='image':candidates.append(row)
        if len(candidates)!=1:return Plan(summary='Choose the image to edit.',question='Which saved image should I edit? Use “Edit image #ID: your instructions”.',steps=[])
        target=candidates[0];instruction=implicit[1].strip()
    elif parent and not artifacts.business_request(text):
        previous=(parent.plan or {}).get('steps') or []
        if parent.status=='awaiting_approval' and len(previous)==1 and previous[0]['tool'].endswith(('.generate_image','.edit_image')) and re.match(r'(?i)^(?:make|change|add|remove|replace|recolor|turn|rename|call)\b',text):
            pending=(Edit if previous[0]['tool'].endswith('.edit_image') else Generate).model_validate(previous[0]['payload'])
            title=pending.title;instruction=pending.prompt;ratio=pending.aspect_ratio;refs=pending.references
            rename=re.fullmatch(r'(?:rename(?: it)? to|call it)\s+(.+)',text,re.I|re.S)
            if rename:title=rename[1].strip().strip('"\'')
            else:instruction+='\nAdditional requested change: '+text
            if isinstance(pending,Edit):target=artifacts.owned(db,user,pending.artifact_id)
        elif re.match(r'(?i)^(?:make|change|add|remove|replace|recolor|turn)\b',text):
            images=[]
            for receipt in parent.receipts or []:
                if receipt.get('artifact_id'):
                    candidate=artifacts.owned(db,user,receipt['artifact_id'])
                    if candidate.references['kind']=='image':images.append(candidate)
            if len(images)==1:target=images[0];instruction=text
        elif parent.status=='needs_clarification' and (parent.plan or {}).get('summary','').startswith('Image artifact needs instructions'):
            ident=(parent.result or {}).get('request',{}).get('artifact_id')
            if ident:target=artifacts.owned(db,user,ident);instruction=text
    if instruction is None:return None
    if explicit_module:data.module=explicit_module
    if not data.conversation_id:return Plan(summary='Image processing needs a private conversation.',question='Start a conversation, then describe the image you want.',steps=[])
    if target:
        if prefix and data.module!=target.references['module']:raise HTTPException(403,'Edit the image in its original module')
        data.module=target.references['module'];data.project_id=target.references.get('project_id');data.artifact_id=target.id
        if target.workspace_id!=data.workspace_id:raise HTTPException(403,'Edit the image in its original workspace')
        title=title if pending else target.title
        if not pending:
            source_image=artifacts.public(db,user,target)['image']
            ratios={'1:1':1,'16:9':16/9,'9:16':9/16,'4:3':4/3,'3:4':3/4}
            ratio=min(ratios,key=lambda key:abs(ratios[key]-source_image['width']/source_image['height']))
        if not instruction:return Plan(summary='Image artifact needs instructions.',question='What would you like to change in this image?',steps=[])
        if target.references['revision']>=100:raise HTTPException(422,'Image version limit reached; create a new image')
    if data.module not in {'CRM','PMS','HRMS'}:
        return Plan(summary='Choose an image module.',question='Select CRM, PMS or HRMS, then describe the image you want.',steps=[])
    config=resolve_media(db,user,'image',data.workspace_id)
    requested_ratio=re.search(r'(?i)\b(?:aspect(?:\s+ratio)?|ratio|format)\s*[:=]?\s*(1:1|16:9|9:16|4:3|3:4)\b',instruction)
    if requested_ratio:ratio=requested_ratio[1]
    values=dict(title=title,prompt=instruction,conversation_id=data.conversation_id,model=config.model,
        media_policy_sha256=config.media_policy_sha256,aspect_ratio=ratio,references=refs)
    if target:
        current=artifacts.public(db,user,target)
        values.update(artifact_id=target.id,expected_revision=current['revision'],source_sha256=current['image']['sha256'])
    try:payload=(Edit if target else Generate)(**values)
    except ValueError:raise HTTPException(422,'Use an image title up to 160 characters and an instruction up to 3,000 characters') from None
    return Plan(summary=f'Review {"editing" if target else "creating"} this image using Gemini / {config.model}. Your instruction and selected image pixels will be sent to Gemini. A private PNG artifact version will be saved. Cost is unknown; no business records or messages will be created.',
        steps=[Step(tool=f'{data.module.lower()}.{"edit_image" if target else "generate_image"}',payload=payload.model_dump())])



def validated_output(journal):
    from app.ai_operator.artifact_images import validate
    try:
        content=base64.b64decode(journal.result['image_b64'],validate=True)
        return validate(content,journal.result['image'],require_clean=True)
    except (ValueError,TypeError,KeyError):raise HTTPException(409,'Stored image output is invalid') from None


def execute(data,request,db,user,editing=False):
    from app.ai_operator.agent_connectors import reviewed_run
    from app.ai_operator import artifacts,gemini_media
    from app.ai_operator.artifact_images import quota
    from app.ai_operator.media_journal import output
    model=Edit if editing else Generate;suffix='edit_image' if editing else 'generate_image'
    run,step=reviewed_run(db,user,request,data,model,suffix)
    config,references,citations=preflight(db,user,run,step);instruction,manifest=prompt(data)
    # A maximum-size reservation check avoids knowingly billing a full store.
    from app.ai_operator.assistant_models import AssistantMessage
    previous=db.query(AssistantMessage).filter_by(conversation_id=data.conversation_id,
        request_key=digest({'media_run':run.id,'step':data.suite_step}),tool=JOURNAL).first()
    if not previous:quota(db,user,run.workspace_id,gemini_media.MAX_OUTPUT)
    def invoke():
        result=gemini_media.generate_image(config,instruction,model=config.model,references=references,aspect_ratio=data.aspect_ratio)
        image={'mime_type':'image/png','width':result.width,'height':result.height,'size':len(result.content),
            'sha256':hashlib.sha256(result.content).hexdigest()}
        body=artifacts.Body(title=data.title,kind='image',content=result.caption,image=image)
        return {'image_b64':base64.b64encode(result.content).decode('ascii'),'image':body.image.model_dump(),'caption':body.content},result.usage
    journal=output(db,user,run,data,step,config,JOURNAL,'media_image',manifest,invoke)
    if journal.status=='completed':return journal.result['receipt']
    content=validated_output(journal)
    run,step=reviewed_run(db,user,request,data,model,suffix);config,_,citations=preflight(db,user,run,step)
    body=artifacts.Body(title=data.title,kind='image',content=journal.result['caption'],image=journal.result['image']).model_dump()
    if editing:body.update(artifact_id=data.artifact_id,expected_revision=data.expected_revision)
    receipt=artifacts.store_revision(db,user,run,step.tool.split('.')[0].upper(),body,data.suite_step,editing=editing,media_content=content,
        provenance_extra={'citations':citations,'note':'Reviewed AI-generated image. Visual text and depicted facts require verification; no business actions were executed.',
            'media':{'kind':'image','provider':'gemini','model':config.model,'core_prompt':journal.arguments['core_prompt'],
                'prompt_sha256':digest(data.prompt),'aspect_ratio':data.aspect_ratio,'media_policy_sha256':data.media_policy_sha256}})
    journal.status='completed';journal.result={**{k:v for k,v in journal.result.items() if k!='image_b64'},'receipt':receipt}
    run.result={**(run.result or {}),'media_checkpoint':{'step':data.suite_step,'state':'completed'}}
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module=step.tool.split('.')[0].upper(),action='suite.media.image_saved',
        input_json={'suite_run_id':run.id,'step':data.suite_step},output_json={'artifact_id':receipt['artifact_id'],'revision':receipt['artifact_revision']},status='success')
    db.commit();return receipt


@router.post('/generate-image-approved')
def generate(data:GenerateApproved,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return execute(data,request,db,user)


@router.post('/edit-image-approved')
def edit(data:EditApproved,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return execute(data,request,db,user,True)


def import_source(db,user,run,step):
    from app.ai_operator import artifacts,suite_uploads as uploads,suite_conversations as chats,gemini_media
    data=ImportImage.model_validate(step.payload)
    if not run or (run.result or {}).get('request',{}).get('conversation_id')!=data.conversation_id:raise HTTPException(403,'Image import must retain its original conversation')
    chat=chats.owned(db,user,data.conversation_id)
    if chat.workspace_id!=run.workspace_id:raise HTTPException(403,'Image import is outside this workspace')
    module=step.tool.split('.')[0].upper()
    artifacts.access(db,user,run.workspace_id,module,(run.result or {}).get('request',{}).get('project_id') if module=='PMS' else None)
    row=uploads.owned(db,user,data.conversation_id,data.attachment_id);media=row.arguments.get('media') or {}
    if media.get('kind')!='image' or row.arguments.get('sha256')!=data.sha256:raise HTTPException(409,'Image import source changed')
    try:original=base64.b64decode(row.result['content_b64'],validate=True)
    except (ValueError,KeyError,TypeError):raise HTTPException(409,'Image source unavailable') from None
    if hashlib.sha256(original).hexdigest()!=data.sha256:raise HTTPException(409,'Image source integrity changed')
    content,width,height=gemini_media.image_bytes(original,media['mime_type'])
    image={'mime_type':'image/png','width':width,'height':height,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    try:body=artifacts.Body(title=data.title,kind='image',image=image).model_dump()
    except ValueError:raise HTTPException(422,'Choose a valid image artifact title') from None
    return row,content,body


@router.post('/import-image-approved')
def import_image(data:ImportApproved,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.agent_connectors import reviewed_run
    from app.ai_operator import artifacts
    run,step=reviewed_run(db,user,request,data,ImportImage,'import_image');row,content,body=import_source(db,user,run,step)
    receipt=artifacts.store_revision(db,user,run,step.tool.split('.')[0].upper(),body,data.suite_step,media_content=content,
        provenance_extra={'note':'Reviewed user-uploaded image. Imported locally without a model call; sharing is separately reviewed.',
            'citations':[{'id':f'upload:{row.id}','label':row.arguments['name'],'href':f'/api/v1/ai-operator/suite/conversations/{data.conversation_id}/attachments/{row.id}/download'}],
            'media':{'kind':'imported_image','source_sha256':data.sha256,'external_model_calls':0}})
    run.result={**(run.result or {}),'media_checkpoint':{'step':data.suite_step,'state':'completed'}}
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module=step.tool.split('.')[0].upper(),action='suite.media.image_imported',
        input_json={'suite_run_id':run.id,'step':data.suite_step},output_json={'artifact_id':receipt['artifact_id'],'revision':receipt['artifact_revision'],'external_model_calls':0},status='success')
    db.commit();return receipt
