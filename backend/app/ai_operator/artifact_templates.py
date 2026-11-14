"""Private versioned artifact templates over existing assistant storage.

Placeholders are literal substitutions, never Jinja, code or tool instructions.
Template copies carry no source citations, conversations or execution grants.
"""
import json
import re
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_agents.security import company,seal,verify
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
from app.ai_operator.suite_tools import Strict,TOOLS
from app.ai_operator.service import digest
from app.ai_operator import artifacts

router=APIRouter(prefix='/suite/artifact-templates',tags=['Artifact templates'])
VERSION='suite.artifact.template.version'
VARIABLE=re.compile(r'\{\{\s*([a-z][a-z0-9_]{0,39})\s*\}\}')


def now():return datetime.now(timezone.utc)


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for v in value:yield from strings(v)
    elif isinstance(value,dict):
        for v in value.values():yield from strings(v)


def variables(body):
    found=[]
    for text in strings(body):
        remainder=VARIABLE.sub('',text)
        if '{{' in remainder or '}}' in remainder:raise ValueError('Use literal placeholders such as {{customer}} with lowercase letters, numbers and underscores')
        found.extend(VARIABLE.findall(text))
    result=list(dict.fromkeys(found))
    if len(result)>20:raise ValueError('Use at most 20 template variables')
    return result


class ImageInstruction(Strict):
    kind:Literal['image_instruction']='image_instruction'
    title:str=Field(min_length=1,max_length=160)
    content:str=Field(min_length=1,max_length=3000)
    columns:list[str]=Field(default_factory=list,max_length=0)
    rows:list[list[str]]=Field(default_factory=list,max_length=0)
    aspect_ratio:Literal['1:1','16:9','9:16','4:3','3:4']='1:1'

    @model_validator(mode='after')
    def valid(self):
        # Reuse native plain-text and control-character validation, without
        # permitting a binary manifest, source references or model credentials.
        artifacts.Body(title=self.title,content=self.content)
        if not self.content.strip():raise ValueError('Provide image instructions')
        return self


class Preview(Strict):
    request_key:UUID
    name:str=Field(min_length=1,max_length=120)
    body:artifacts.Body|ImageInstruction
    source_artifact_id:int|None=Field(default=None,gt=0)
    source_revision:int|None=Field(default=None,ge=1)
    template_id:int|None=Field(default=None,gt=0)
    expected_revision:int|None=Field(default=None,ge=1)

    @model_validator(mode='after')
    def valid(self):
        if self.body.kind=='image':raise ValueError('Image templates require reviewed image-generation instructions rather than a binary manifest')
        if not self.name.strip():raise ValueError('Provide a template name')
        if re.search(r'[\x00-\x1f\ud800-\udfff\ufffe\uffff]',self.name):raise ValueError('Template names cannot contain control characters')
        if bool(self.template_id)!=bool(self.expected_revision):raise ValueError('Select the template and its current revision together')
        if bool(self.source_artifact_id)!=bool(self.source_revision):raise ValueError('Select the source artifact and revision together')
        if not self.template_id and not self.source_artifact_id:raise ValueError('Choose an authorized saved artifact')
        variables(self.body.model_dump())
        return self


class Confirmation(Strict):
    preview_hash:str=Field(min_length=64,max_length=64)


def audit(db,user,row,action):
    AiAuditService(db).log(user=user,agent_id=None,module=row.references['module'],action='artifact_template.'+action,
        input_json={'template_context_id':row.id},output_json={'revision':row.references.get('revision')},status='success')


def owned(db,user,ident,preview=False,lock=False):
    q=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None)
    row=(q.with_for_update().populate_existing() if lock else q).first()
    if not row or not row.references.get('artifact_template_preview' if preview else 'artifact_template'):raise HTTPException(404,'Artifact template not found')
    verify(db,user,row.security_context,history=True);r=row.references
    if artifacts.access(db,user,row.workspace_id,r['module'],r.get('project_id'))!=r['scope_key']:raise HTTPException(403,'Template scope changed')
    return row


def version(db,user,row,revision=None):
    revision=revision or row.references['revision']
    value=db.query(AssistantMessage).filter_by(conversation_id=row.id,tool=VERSION,status='stored').filter(AssistantMessage.arguments['revision'].as_integer()==revision).first()
    if not value:raise HTTPException(404,'Template revision not found')
    verify(db,user,value.security_context,history=True)
    if value.request_hash!=digest(value.arguments) or value.arguments['definition_hash']!=digest({k:value.arguments[k] for k in ('name','body')}):
        raise HTTPException(409,'Template definition integrity changed; prepare a new reviewed template')
    return value.arguments


def public(db,user,row,revision=None):
    value=version(db,user,row,revision)
    return {'id':row.id,'module':row.references['module'],'workspace_id':row.workspace_id,'project_id':row.references.get('project_id'),
        'current_revision':row.references['revision'],**value,'variables':variables(value['body']),
        'execution':'Private saved structure. Values and copied text are not verified business facts. Creating an artifact requires review.'}


def source_scope(db,user,data,lock=False):
    source=owned(db,user,data.template_id,lock=lock) if data.template_id else artifacts.owned(db,user,data.source_artifact_id,lock)
    r=source.references
    if data.template_id and r['revision']!=data.expected_revision:raise HTTPException(409,'Template changed; reload before reviewing an update')
    if data.source_artifact_id:
        artifact=artifacts.owned(db,user,data.source_artifact_id,lock)
        body=artifacts.public(db,user,artifact,data.source_revision)
        if (artifact.workspace_id,artifact.references['module'],artifact.references.get('project_id'))!=(source.workspace_id,r['module'],r.get('project_id')):
            raise HTTPException(403,'The source artifact is outside this template scope')
    else:body=public(db,user,source)['body']
    expected='image_instruction' if body['kind']=='image' else body['kind']
    if expected!=data.body.kind:raise HTTPException(422,'Retain the source template/artifact format')
    return source


def payload(data,source):
    return {'definition':data.model_dump(mode='json',exclude={'request_key'}),'module':source.references['module'],
        'project_id':source.references.get('project_id'),'workspace_id':source.workspace_id,'scope_key':source.references['scope_key']}


def preview_public(row):
    r=row.references
    return {'id':row.id,**r['payload'],'variables':variables(r['payload']['definition']['body']),
        'preview_hash':r['preview_hash'],'expires_at':r['expires_at'],'template_id':r.get('applied_template_id'),
        'applied_revision':r.get('applied_revision'),'state':'confirmed' if r.get('applied_template_id') else 'preview'}


@router.get('')
def listing(module:artifacts.Module,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    scope=artifacts.access(db,user,workspace_id,module)
    rows=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['artifact_template'].as_boolean()==True,AssistantConversation.references['module'].as_string()==module,
        AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.id.desc()).limit(50)
    items=[]
    for row in rows:
        try:value=public(db,user,owned(db,user,row.id))
        except HTTPException:continue
        items.append({k:value[k] for k in ('id','name','module','revision','current_revision','variables','project_id')})
    return {'items':items,'limit':50}


@router.post('/preview')
def preview(data:Preview,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    source=source_scope(db,user,data)
    db.query(User.id).filter_by(id=user.id).with_for_update().one()
    value=payload(data,source);hashed=digest(value)
    old=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
        AssistantConversation.references['artifact_template_key'].as_string()==str(data.request_key)).first()
    if old:
        row=owned(db,user,old.id,preview=True)
        if row.references['preview_hash']!=hashed:raise HTTPException(409,'Template request key belongs to a different review')
        return preview_public(row)
    count=db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
        AssistantConversation.references['artifact_template_preview'].as_boolean()==True,
        AssistantConversation.references['applied_template_id'].as_integer().is_(None),
        AssistantConversation.references['expires_at'].as_string()>now().isoformat()).count()
    if count>=20:raise HTTPException(422,'Finish existing template reviews or wait for their one-hour expiry')
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=source.workspace_id,title='Template review: '+data.name,
        references={'artifact_template_preview':True,'artifact_template_key':str(data.request_key),'scope_key':value['scope_key'],'module':value['module'],
            'project_id':value['project_id'],'payload':value,'preview_hash':hashed,'grant':seal(db,user,hashed),'expires_at':(now()+timedelta(hours=1)).isoformat()})
    db.add(row);db.flush();audit(db,user,row,'previewed');db.commit();return preview_public(row)


@router.get('/reviews/{ident}')
def get_review(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return preview_public(owned(db,user,ident,preview=True))


@router.get('/reviews')
def reviews(module:artifacts.Module,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    scope=artifacts.access(db,user,workspace_id,module);items=[]
    rows=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['artifact_template_preview'].as_boolean()==True,
        AssistantConversation.references['scope_key'].as_string()==scope,AssistantConversation.references['module'].as_string()==module,
        AssistantConversation.references['applied_template_id'].as_integer().is_(None),AssistantConversation.references['expires_at'].as_string()>now().isoformat()).order_by(AssistantConversation.id.desc()).limit(20)
    for row in rows:
        try:items.append(preview_public(owned(db,user,row.id,preview=True)))
        except HTTPException:continue
    return {'items':items}


@router.delete('/reviews/{ident}')
def discard_review(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,preview=True,lock=True);row.deleted_at=now();audit(db,user,row,'review_discarded');db.commit();return {'archived':True}


@router.post('/reviews/{ident}/confirm')
def confirm(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    review=owned(db,user,ident,preview=True,lock=True);r=review.references
    if digest(r['payload'])!=data.preview_hash or r['preview_hash']!=data.preview_hash:raise HTTPException(409,'Template review changed; preview it again')
    if r.get('applied_template_id'):
        row=owned(db,user,r['applied_template_id']);return {'template':public(db,user,row,r['applied_revision']),'review_id':review.id}
    if now()>=datetime.fromisoformat(r['expires_at']):raise HTTPException(409,'Template review expired; prepare it again')
    verify(db,user,r['grant'],payload=data.preview_hash,confirmation=True)
    definition=Preview(request_key=UUID(r['artifact_template_key']),**r['payload']['definition'])
    source=source_scope(db,user,definition,lock=True)
    if payload(definition,source)!=r['payload']:raise HTTPException(409,'Template source scope changed')
    if definition.template_id:
        row=source;revision=row.references['revision']+1
        if revision>100:raise HTTPException(422,'Template version limit reached; create a separate template')
    else:
        db.query(User.id).filter_by(id=user.id).with_for_update().one()
        count=db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(AssistantConversation.references['artifact_template'].as_boolean()==True).count()
        if count>=100:raise HTTPException(422,'Archive unused artifact templates before adding more')
        row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=source.workspace_id,title=definition.name,
            references={'artifact_template':True,'scope_key':r['scope_key'],'module':r['module'],'project_id':r.get('project_id'),'revision':1})
        db.add(row);db.flush();revision=1
    body=definition.body.model_dump(mode='json');value={'revision':revision,'name':definition.name,'body':body,'definition_hash':digest({'name':definition.name,'body':body})}
    db.add(AssistantMessage(conversation_id=row.id,request_key=f'template-version:{revision}',request_hash=digest(value),prompt='Reviewed private artifact template',tool=VERSION,arguments=value,status='stored'))
    row.references={**row.references,'revision':revision};row.title=definition.name
    review.references={**r,'applied_template_id':row.id,'applied_revision':revision}
    audit(db,user,row,'revised' if definition.template_id else 'created');db.commit()
    return {'template':public(db,user,row),'review_id':review.id}


@router.get('/{ident}/versions')
def versions(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident);items=[]
    for message in db.query(AssistantMessage).filter_by(conversation_id=row.id,tool=VERSION,status='stored').order_by(AssistantMessage.id.desc()).limit(100):
        verify(db,user,message.security_context,history=True)
        items.append({k:message.arguments[k] for k in ('revision','name','definition_hash')})
    return {'items':items,'current_revision':row.references['revision']}


@router.get('/{ident}')
def get(ident:int,revision:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return public(db,user,owned(db,user,ident),revision)


@router.delete('/{ident}')
def archive(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,lock=True);row.deleted_at=now();audit(db,user,row,'archived');db.commit();return {'archived':True}


def render(body,values):
    def replace(value):
        if isinstance(value,str):return VARIABLE.sub(lambda match:values[match[1]],value)
        if isinstance(value,list):return [replace(v) for v in value]
        if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
        return value
    model=ImageInstruction if body.get('kind')=='image_instruction' else artifacts.Body
    return model.model_validate(replace(body)).model_dump(mode='json')


def action_body(body,data):
    if body['kind']!='image_instruction':return body
    if not data.conversation_id:raise HTTPException(422,'Use image templates in a private conversation')
    return {'title':body['title'],'prompt':body['content'],'aspect_ratio':body['aspect_ratio'],
        'conversation_id':data.conversation_id,'references':[]}


def supplied(text,expected,missing):
    text=text.strip()
    try:
        def pairs(items):
            if len(dict(items))!=len(items):raise ValueError('Duplicate variable')
            return dict(items)
        if re.match(r'^\{\s*"',text):value=json.loads(text,object_pairs_hook=pairs)
        elif '=' in text:value=pairs([tuple(v.strip() for v in part.strip().split('=',1)) for part in text.split(';')])
        elif missing:value={missing[0]:text}
        else:raise ValueError('No variables expected')
    except (ValueError,TypeError):raise HTTPException(422,'Provide name=value pairs separated by semicolons, or a JSON object') from None
    if not isinstance(value,dict) or set(value)-set(expected) or any(not isinstance(v,str) or not v.strip() or len(v)>500 for v in value.values()):
        raise HTTPException(422,'Use known variable names and nonempty text values of at most 500 characters')
    return value


def prepare(db,user,data,parent):
    from app.ai_operator.suite import Plan,Step
    match=re.fullmatch(r'\s*(?:use|apply|create (?:an? )?(?:artifact|document|report|presentation) from) (?:artifact )?template\s*#?\s*(\d+)(?:\s+version\s+(\d+))?(?:\s*:\s*(.*))?\s*',data.text,re.I|re.S)
    named=re.fullmatch(r'\s*(?:use|apply) (?:artifact )?template\s+"([^"\n]{1,120})"(?:\s+version\s+(\d+))?(?:\s*:\s*(.*))?\s*',data.text,re.I|re.S)
    if named:
        if data.module not in ('CRM','PMS','HRMS'):raise HTTPException(422,'Select a module before choosing a template by name')
        scope=artifacts.access(db,user,data.workspace_id,data.module)
        candidates=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,deleted_at=None).filter(
            AssistantConversation.references['artifact_template'].as_boolean()==True,
            AssistantConversation.references['module'].as_string()==data.module,AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.id.desc()).limit(100)
        found=[]
        for candidate in candidates:
            if candidate.title.casefold()!=named[1].strip().casefold():continue
            try:owned(db,user,candidate.id)
            except HTTPException:continue
            found.append(candidate.id)
        if not found:raise HTTPException(404,'No private template with that name exists in this module and workspace')
        if len(found)>1:raise HTTPException(409,'Several private templates have that name. Choose one explicitly: '+', '.join(f'Use template #{ident}' for ident in found[:10]))
        match=(None,str(found[0]),named[2],named[3])
    prior=(parent.result or {}).get('artifact_template') if parent and parent.status in ('needs_clarification','awaiting_approval') else None
    if prior and re.fullmatch(r'\s*(?:please )?(?:cancel|stop|discard)(?: (?:this|the|my|pending)(?: draft| request| plan)?)?[.! ]*',data.text,re.I):
        return Plan(summary='Template request cancelled.',steps=[]),{'cancelled':True}
    if not match and not prior:return None,None
    if match and parent and parent.status in ('needs_clarification','awaiting_approval') and (not prior or prior['id']!=int(match[1])):
        raise HTTPException(409,'Finish or cancel the pending draft before selecting another template')
    row=owned(db,user,int(match[1]) if match else prior['id']);value=public(db,user,row)
    if row.workspace_id!=data.workspace_id:raise HTTPException(403,'Use this template in its original workspace')
    requested=int(match[2]) if match and match[2] else prior['revision'] if prior else value['revision']
    if requested!=value['current_revision']:raise HTTPException(409,'Template changed; select its current revision and prepare a fresh draft')
    if parent and parent.status in ('needs_clarification','awaiting_approval') and data.module!=value['module']:raise HTTPException(409,'Continue the template in its original module')
    data.module=value['module'];data.project_id=value['project_id']
    if match:data.context=[];data.task_ids=[]
    packet={'id':row.id,'revision':value['revision'],'definition_hash':value['definition_hash'],'values':dict(prior.get('values',{})) if prior else {}}
    missing=[key for key in value['variables'] if key not in packet['values']]
    literal=match[3] if match else data.text if parent.status=='needs_clarification' or re.match(r'\s*[a-z][a-z0-9_]*\s*=',data.text) or re.match(r'\s*\{\s*"',data.text) else None
    if literal:
        additions=supplied(literal,value['variables'],missing)
        if additions:packet['values'].update(additions)
    if not match and parent.status=='awaiting_approval' and literal is None:return None,packet
    missing=[key for key in value['variables'] if key not in packet['values']]
    if missing:return Plan(summary='I need a template value.',question=f'What value should I use for {missing[0]}? You can also supply several values as name=value; name=value.',steps=[]),packet
    try:body=render(value['body'],packet['values'])
    except ValueError:raise HTTPException(422,'Template values do not fit this artifact. Check field lengths, numeric values and chart requirements.') from None
    if prior and parent.status=='awaiting_approval' and literal:
        old=action_body(render(value['body'],prior['values']),data);steps=(parent.plan or {}).get('steps',[])
        previous={k:v for k,v in steps[0]['payload'].items() if k not in ('model','media_policy_sha256')} if steps and body['kind']=='image_instruction' else steps[0]['payload'] if steps else {}
        if len(steps)!=1 or digest(previous)!=digest(old):raise HTTPException(409,'This draft has manual edits. Continue editing it or cancel it before changing template values.')
    image=body['kind']=='image_instruction'
    summary='Review a new image-generation call from your private instruction template. No source pixels are copied. Current enabled provider settings and separate approval are required.' if image else 'Review this artifact prepared from your private template. Template text and supplied values are not freshly verified business facts.'
    return Plan(summary=summary,
        steps=[Step(tool=f'{data.module.lower()}.{"generate_image" if image else "create_artifact"}',payload=action_body(body,data))]),packet


def enforce(db,user,run,steps,lock=False):
    packet=(run.result or {}).get('artifact_template')
    if not packet:return
    row=owned(db,user,packet['id'],lock=lock);value=public(db,user,row)
    if value['revision']!=packet['revision'] or value['definition_hash']!=packet['definition_hash']:raise HTTPException(409,'Template changed since planning; prepare a fresh review')
    if row.workspace_id!=run.workspace_id or value['module']!=(run.result or {}).get('request',{}).get('module'):raise HTTPException(403,'Template scope changed')
    if value['project_id'] and value['project_id']!=(run.result or {}).get('request',{}).get('project_id'):raise HTTPException(403,'Template project scope changed')
    for step in steps:
        tool=TOOLS.get(step.tool)
        if not tool:raise HTTPException(422,'Unknown action tool')
        allowed=(f'{value["module"].lower()}.generate_image',) if value['body']['kind']=='image_instruction' else (f'{value["module"].lower()}.create_artifact',f'{value["module"].lower()}.edit_artifact')
        if tool.method!='GET' and step.tool not in allowed:
            raise HTTPException(403,'Template drafts can only save reviewed artifacts')
