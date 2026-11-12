"""Reviewed organization definitions with private, revocation-aware installs.

Publication storage reuses ServicePolicy. Runtime conversations, memories,
credentials and connector bindings always stay with their existing owners.
"""
import hmac
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.shared.models import ServicePolicy
from app.access.models import AccessMembership
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.suite_tools import Strict,TOOLS
from app.ai_operator import saved_agents as agents
from app.ai_operator.service import digest
from app.ai_agents.security import company,seal,verify,signature

router=APIRouter(prefix='/suite/agents/library',tags=['Organization agent and skill library'])
KIND='ai_asset_library'


class Audience(Strict):
    kind:Literal['organization','members','workspace_teams']='organization'
    member_ids:list[int]=Field(default_factory=list,max_length=100)
    team_ids:list[int]=Field(default_factory=list,max_length=50)

    @model_validator(mode='after')
    def valid(self):
        if any(type(i) is not int or i<1 for i in [*self.member_ids,*self.team_ids]):raise ValueError('Use existing positive audience IDs')
        if len(set(self.member_ids))!=len(self.member_ids) or len(set(self.team_ids))!=len(self.team_ids):raise ValueError('Do not duplicate audience IDs')
        if (self.kind=='members')!=bool(self.member_ids) or (self.kind=='workspace_teams')!=bool(self.team_ids):raise ValueError('Select the matching audience')
        return self


class Preview(Strict):
    request_key:UUID
    asset_type:Literal['agent','skill']
    source_id:int=Field(gt=0)
    source_revision:int=Field(ge=1)
    audience:Audience
    publication_id:int|None=Field(default=None,gt=0)
    revision:int|None=Field(default=None,ge=1)


class Confirmation(Strict):
    preview_hash:str=Field(min_length=64,max_length=64)


class Revision(Strict):
    revision:int=Field(ge=1)


class Install(Revision):
    definition_hash:str=Field(min_length=64,max_length=64)
    asset_revision:int|None=Field(default=None,ge=1)
    provider:Literal['preferred','local','gemini','openai','claude']|None=None
    component_revisions:dict[int,int]=Field(default_factory=dict,max_length=10)

    @model_validator(mode='after')
    def valid(self):
        if any(type(k) is not int or k<1 or type(v) is not int or v<1 for k,v in self.component_revisions.items()):raise ValueError('Use existing positive component revisions')
        return self


def admin(db,user):
    return bool(user.is_superuser or db.query(AccessMembership.id).filter_by(user_id=user.id,company_id=company(user),active=True,is_admin=True).first())


def require_admin(db,user):
    from app.ai_operator.suite import authorize
    authorize(db,user,None)
    if not admin(db,user):raise HTTPException(403,'Organization AI library publishing requires an organization administrator')


def signed_value(row):
    return {'id':row.id,'organization_id':row.organization_id,'revision':row.version,**{k:row.values_json.get(k) for k in
        ('asset_type','workspace_id','source_owner','source_id','source_revision','status','definition','audience','history','last_published_hash')}}


def sign(row):
    row.values_json={**row.values_json,'signature':signature(signed_value(row))}


def entry(db,user,ident,lock=False):
    q=db.query(ServicePolicy).filter_by(id=ident,organization_id=company(user),kind=KIND).populate_existing()
    row=(q.with_for_update() if lock else q).first()
    if not row:raise HTTPException(404,'Shared definition not found')
    from app.ai_operator.suite import authorize
    authorize(db,user,row.values_json['workspace_id'])
    if not hmac.compare_digest(str(row.values_json.get('signature','')),signature(signed_value(row))):raise HTTPException(409,'Shared definition integrity changed')
    return row


def audience_access(db,user,row,audience=None):
    if user.is_superuser:return True
    if not db.query(AccessMembership.id).filter_by(user_id=user.id,company_id=company(user),active=True).first():return False
    data=audience or row.values_json['audience']
    if data['kind']=='organization':return True
    if data['kind']=='members':return user.id in data['member_ids']
    from app.apps.project_management.models import PMSWorkspaceTeam,PMSWorkspaceTeamMember
    return bool(db.query(PMSWorkspaceTeamMember.user_id).join(PMSWorkspaceTeam,PMSWorkspaceTeam.id==PMSWorkspaceTeamMember.team_id).filter(
        PMSWorkspaceTeamMember.user_id==user.id,PMSWorkspaceTeam.workspace_id==row.values_json['workspace_id'],PMSWorkspaceTeam.id.in_(data['team_ids'])).first())


def visible(db,user,row,management=True):
    if management and admin(db,user):return
    if row.values_json['status']!='active' or not audience_access(db,user,row):raise HTTPException(404,'Shared definition not available to your current audience')


def audience_check(db,user,value,workspace_id):
    if value.member_ids:
        ids={i for (i,) in db.query(AccessMembership.user_id).join(User,User.id==AccessMembership.user_id).filter(
            AccessMembership.company_id==company(user),AccessMembership.active==True,User.is_active==True,AccessMembership.user_id.in_(value.member_ids))}
        if user.is_superuser and user.id in value.member_ids:ids.add(user.id)
        if ids!=set(value.member_ids):raise HTTPException(422,'Audience members must be active in this organization')
    if value.team_ids:
        if not workspace_id:raise HTTPException(422,'Workspace teams require a workspace-scoped definition')
        from app.apps.project_management.models import PMSWorkspaceTeam
        from app.apps.project_management.people_workspace import teams_query
        ids={t.id for t in teams_query(db,user).filter(PMSWorkspaceTeam.workspace_id==workspace_id,PMSWorkspaceTeam.id.in_(value.team_ids))}
        if ids!=set(value.team_ids):raise HTTPException(422,'Choose teams from this definition workspace')


def source(db,user,kind,ident,revision):
    row=agents.owned(db,user,ident) if kind=='agent' else agents.owned_skill(db,user,ident)
    if row.references['revision']!=revision:raise HTTPException(409,'Source changed; reload it before publishing')
    if row.references.get('library_origin'):raise HTTPException(422,'Publish an original private definition; linked library installs cannot be republished')
    body=row.references['config']
    definition={k:body[k] for k in ('name','instructions','tools')}
    definition.update(workspace_id=row.workspace_id,modules=body.get('modules') or sorted({TOOLS[t].module for t in body['tools']}))
    if kind=='agent':
        definition.update(provider=body['provider'],project_id=body.get('project_id'),skills=[])
        for ident in body['skill_ids']:
            skill=agents.owned_skill(db,user,ident)
            if skill.references.get('library_origin'):raise HTTPException(422,'Linked shared skills cannot be republished inside another definition')
            definition['skills'].append({k:skill.references['config'][k] for k in ('name','instructions','tools')})
        definition['omitted']={'private_memory':len(body['memory']),'connection_bindings':len(body['connection_ids']),'mcp_bindings':len(body['mcp_ids']),'conversation_history':True}
        if body.get('knowledge_files'):definition['omitted']['private_knowledge_files']=len(body['knowledge_files'])
    return definition


def installed(db,user,row,component=None,lock=False):
    component=component or row.values_json['asset_type']
    query=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=row.values_json['workspace_id'],deleted_at=None).filter(
        AssistantConversation.references['library_origin']['publication_id'].as_integer()==row.id,
        AssistantConversation.references['library_origin']['component'].as_string()==component).order_by(AssistantConversation.id.desc())
    return (query.with_for_update().populate_existing() if lock else query).first()


def public(db,user,row):
    value=row.values_json;asset=installed(db,user,row)
    pending=value.get('pending')
    components={s.id:s.references['revision'] for s in db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
        AssistantConversation.references['library_origin']['publication_id'].as_integer()==row.id,
        AssistantConversation.references['library_origin']['component'].as_string().like('agent-skill:%'))} if asset and value['asset_type']=='agent' else {}
    return {'id':row.id,'revision':row.version,'asset_type':value['asset_type'],'status':value['status'],'workspace_id':value['workspace_id'],
        'definition':value['definition'],'definition_hash':digest(value['definition']),'audience':value['audience'],
        'can_manage':admin(db,user),'can_install':value['status']=='active' and audience_access(db,user,row),
        'pending':{k:v for k,v in pending.items() if k not in {'grant','input_hash','owner_id'}} if pending and pending['owner_id']==user.id else None,
        'source_id':value['source_id'] if value['source_owner']==user.id and admin(db,user) else None,
        'can_prepare_edition':admin(db,user),
        'installed':{'id':asset.id,'revision':asset.references['revision'],'publication_revision':asset.references['library_origin']['revision'],'provider':asset.references['config'].get('provider'),'component_revisions':components} if asset else None,
        'execution':'Install a private linked configuration. Your permissions, connections, memory and conversations apply. Publication changes require reviewed updates; revocation blocks future execution.'}


def audit(db,user,row,action):
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='agent_library.'+action,
        input_json={'publication_id':row.id},output_json={'revision':row.version,'status':row.values_json['status']},status='success')


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,workspace_id);items=[]
    rows=db.query(ServicePolicy.id).filter_by(organization_id=company(user),kind=KIND).filter(
        ServicePolicy.values_json['workspace_id'].as_integer()==workspace_id if workspace_id else ServicePolicy.values_json['workspace_id'].as_integer().is_(None)).order_by(ServicePolicy.id.desc()).limit(100)
    for (ident,) in rows:
        try:
            row=entry(db,user,ident);visible(db,user,row);items.append(public(db,user,row))
        except HTTPException as exc:
            if exc.status_code not in (403,404):raise
    return {'items':items,'can_publish':admin(db,user)}


@router.get('/targets')
def targets(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user)
    from app.ai_operator.suite import authorize
    authorize(db,user,workspace_id)
    members=[{'id':u.id,'label':u.email} for u in db.query(User).join(AccessMembership,AccessMembership.user_id==User.id).filter(
        AccessMembership.company_id==company(user),AccessMembership.active==True,User.is_active==True).order_by(User.id).limit(200)]
    if user.is_superuser and not any(m['id']==user.id for m in members):members.insert(0,{'id':user.id,'label':user.email})
    teams=[]
    if workspace_id:
        from app.apps.project_management.models import PMSWorkspaceTeam
        from app.apps.project_management.people_workspace import teams_query
        teams=[{'id':t.id,'label':t.name} for t in teams_query(db,user).filter_by(workspace_id=workspace_id).order_by(PMSWorkspaceTeam.id).limit(100)]
    return {'members':members,'teams':teams}


@router.get('/{ident}')
def get(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);visible(db,user,row);return public(db,user,row)


@router.get('/{ident}/versions')
def versions(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);visible(db,user,row)
    history=[h for h in reversed(row.values_json.get('history',[])) if admin(db,user) or audience_access(db,user,row,h['audience'])]
    return {'items':[{'revision':row.version,'status':row.values_json['status'],'definition':row.values_json['definition']},*history],'retention':'Current edition and up to twenty previous publication transitions.'}


@router.post('/preview')
def preview(data:Preview,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user)
    definition=source(db,user,data.asset_type,data.source_id,data.source_revision)
    audience_check(db,user,data.audience,definition['workspace_id'])
    input_hash=digest(data.model_dump(mode='json',exclude={'request_key'}))
    key=f'company:{company(user)}:ai-library:{user.id}:{data.request_key}'
    row=entry(db,user,data.publication_id,True) if data.publication_id else db.query(ServicePolicy).filter_by(scope_key=key,kind=KIND,organization_id=company(user)).with_for_update().first()
    if row:
        pending=row.values_json.get('pending')
        if pending and pending['request_key']==str(data.request_key):
            if pending['input_hash']!=input_hash:raise HTTPException(409,'Publication request key conflicts')
            return public(db,user,row)
        if pending:raise HTTPException(409,'Publish or discard the pending review before preparing another edition')
        if data.revision!=row.version or row.values_json['asset_type']!=data.asset_type:raise HTTPException(409,'Publication type or revision changed')
        if definition['workspace_id']!=row.values_json['workspace_id']:raise HTTPException(422,'A publication edition must retain its workspace')
    else:
        if data.publication_id:raise HTTPException(404,'Shared definition not found')
        if db.query(ServicePolicy.id).filter_by(kind=KIND,organization_id=company(user)).filter(ServicePolicy.values_json['status'].as_string()!='revoked').count()>=200:raise HTTPException(422,'Revoke unused definitions before adding more')
        row=ServicePolicy(scope_key=key,organization_id=company(user),module_key='ai',kind=KIND,updated_by=user.id,version=1,
            values_json={'asset_type':data.asset_type,'workspace_id':definition['workspace_id'],'source_owner':user.id,'source_id':data.source_id,'source_revision':data.source_revision,
                'status':'draft','definition':definition,'audience':data.audience.model_dump(),'history':[]})
        db.add(row)
        try:db.flush()
        except IntegrityError:
            db.rollback();existing=db.query(ServicePolicy).filter_by(scope_key=key,kind=KIND,organization_id=company(user)).first()
            if not existing:raise HTTPException(409,'Conflicting publication request') from None
            pending=existing.values_json.get('pending')
            if not pending or pending['input_hash']!=input_hash:raise HTTPException(409,'Conflicting publication request') from None
            return public(db,user,entry(db,user,existing.id))
    review={'definition':definition,'audience':data.audience.model_dump(),'base_revision':row.version,
        'proposed_revision':row.version if row.values_json['status']=='draft' else row.version+1,
        'source_owner':user.id,'source_id':data.source_id,'source_revision':data.source_revision}
    hashed=digest(review)
    row.values_json={**row.values_json,'pending':{**review,'owner_id':user.id,'request_key':str(data.request_key),'input_hash':input_hash,'preview_hash':hashed,'grant':seal(db,user,hashed)}}
    sign(row);audit(db,user,row,'preview');db.commit();return public(db,user,row)


@router.post('/{ident}/publish')
def publish(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user);row=entry(db,user,ident,True);pending=row.values_json.get('pending')
    if not pending and row.values_json['status']=='active' and row.values_json.get('last_published_hash')==data.preview_hash:return public(db,user,row)
    if not pending or pending['preview_hash']!=data.preview_hash:raise HTTPException(409,'Review the latest publication preview')
    review={k:pending[k] for k in ('definition','audience','base_revision','proposed_revision','source_owner','source_id','source_revision')}
    if digest(review)!=data.preview_hash or pending['base_revision']!=row.version:raise HTTPException(409,'Publication review changed')
    verify(db,user,pending['grant'],payload=data.preview_hash,confirmation=True)
    current=source(db,user,row.values_json['asset_type'],pending['source_id'],pending['source_revision'])
    if current!=pending['definition']:raise HTTPException(409,'Source definition or attached skill changed; prepare a new preview')
    audience_check(db,user,Audience.model_validate(pending['audience']),row.values_json['workspace_id'])
    history=row.values_json.get('history',[])
    if row.values_json['status']!='draft':history=[*history,{'revision':row.version,'status':row.values_json['status'],'definition':row.values_json['definition'],'audience':row.values_json['audience']}] [-20:]
    row.version=pending['proposed_revision'];row.updated_by=user.id
    row.values_json={**row.values_json,'status':'active','definition':current,'audience':pending['audience'],
        'source_owner':pending['source_owner'],'source_id':pending['source_id'],'source_revision':pending['source_revision'],
        'pending':None,'history':history,'last_published_hash':data.preview_hash}
    sign(row);audit(db,user,row,'published');db.commit();return public(db,user,row)


@router.post('/{ident}/discard-preview')
def discard(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user);row=entry(db,user,ident,True);pending=row.values_json.get('pending')
    if not pending or pending['preview_hash']!=data.preview_hash:raise HTTPException(409,'Review changed')
    row.values_json={**row.values_json,'pending':None};sign(row);audit(db,user,row,'preview_discarded');db.commit();return public(db,user,row)


@router.post('/{ident}/revoke')
def revoke(ident:int,data:Revision,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user);row=entry(db,user,ident,True)
    if data.revision!=row.version:raise HTTPException(409,'Publication revision changed')
    if row.values_json['status']!='revoked':
        row.version+=1;row.updated_by=user.id;row.values_json={**row.values_json,'status':'revoked','pending':None};sign(row);audit(db,user,row,'revoked');db.commit()
    return public(db,user,row)


def validate_origin(db,user,asset):
    origin=asset.references.get('library_origin')
    if not origin:return
    row=entry(db,user,origin['publication_id'])
    if row.values_json['status']!='active' or row.version!=origin['revision'] or digest(row.values_json['definition'])!=origin['definition_hash'] or not audience_access(db,user,row):
        raise HTTPException(403,'Shared definition changed, was revoked or is outside your audience. Review an updated organization-library install before running it.')


@router.post('/{ident}/install')
def install(ident:int,data:Install,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    try:return install_private(ident,data,db,user)
    except Exception:
        db.rollback();raise


def install_private(ident,data,db,user):
    # Serialize installs by recipient; no private owner rows are read or copied.
    db.query(User.id).filter_by(id=user.id).with_for_update().one()
    row=entry(db,user,ident,True);visible(db,user,row,management=False)
    if row.version!=data.revision or digest(row.values_json['definition'])!=data.definition_hash:raise HTTPException(409,'Shared definition changed; review the latest edition')
    existing=installed(db,user,row,lock=True)
    if existing and existing.references['library_origin']['revision']==row.version:
        return {'asset_type':row.values_json['asset_type'],'asset':agents.public(existing) if row.values_json['asset_type']=='agent' else agents.public_skill(existing)}
    if existing and data.asset_revision!=existing.references['revision']:raise HTTPException(409,'Private install changed; reload before updating it')
    definition=row.values_json['definition'];base_origin={'publication_id':row.id,'revision':row.version,'definition_hash':data.definition_hash}
    if row.values_json['asset_type']=='skill':
        if data.provider is not None:raise HTTPException(422,'Provider selection applies to agents only')
        body=agents.Skill(**{k:definition[k] for k in ('name','instructions','tools','workspace_id')},revision=existing.references['revision'] if existing else None)
        asset=agents.store_skill(db,user,body,existing,origin={**base_origin,'component':'skill'})
    else:
        skill_ids=[]
        for index,skill in enumerate(definition['skills']):
            component=f'agent-skill:{index}';old=installed(db,user,row,component)
            if old:
                old=agents.owned_skill(db,user,old.id,True)
                if data.component_revisions.get(old.id)!=old.references['revision']:raise HTTPException(409,'A private bundled skill changed; reload the install review')
            body=agents.Skill(**skill,workspace_id=definition['workspace_id'],revision=old.references['revision'] if old else None)
            skill_ids.append(agents.store_skill(db,user,body,old,origin={**base_origin,'component':component}).id)
        prior=existing.references['config'] if existing else {}
        old_components=existing.references.get('library_skill_ids',[]) if existing else []
        personal_skills=[i for i in prior.get('skill_ids',[]) if i not in old_components]
        try:
            body=agents.Config(**{k:definition[k] for k in ('name','instructions','modules','tools','workspace_id','project_id')},
                provider=data.provider or prior.get('provider',definition['provider']),memory=prior.get('memory',[]),
                connection_ids=prior.get('connection_ids',[]),mcp_ids=prior.get('mcp_ids',[]),knowledge_files=prior.get('knowledge_files',[]),environment=prior.get('environment','development'),skill_ids=[*skill_ids,*personal_skills])
        except ValueError:raise HTTPException(422,'The updated definition does not fit this private configuration. Check its provider, personal skills and tool limits.') from None
        if existing:
            agents.access(db,user,body)
            existing.references={**existing.references,'revision':existing.references['revision']+1,'config':body.model_dump(exclude={'revision'})};existing.title=body.name;asset=existing
        else:asset=agents.store(db,user,body)
        asset.references={**asset.references,'library_origin':{**base_origin,'component':'agent'},'library_skill_ids':skill_ids}
    audit(db,user,row,'installed');db.commit()
    return {'asset_type':row.values_json['asset_type'],'asset':agents.public(asset) if row.values_json['asset_type']=='agent' else agents.public_skill(asset)}
